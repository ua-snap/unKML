#!/usr/bin/env python
import urllib2
import StringIO
import tempfile
import re
import magic
import zipfile
import lxml.etree
import os
import sys
import subprocess
import logging

class Layer:
  outputDir = None
  name = None
  url = None
  fileType = None
  data = None
  boundingBox = {}
  fileMagic = magic.Magic(mime = True)

  def __init__(self, name, url):
    self.name = name
    self.url = url

  def download(self):
    logging.info('Downloading {0} from {1}'.format(self.name, self.url))

    # Download layer from URL.
    try:
      response = urllib2.urlopen(self.url)
    except Exception, e:
      logging.exception(e)
      return False
    data = response.read()

    # Analyze file contents to determine MIME type.
    mimeType = Layer.fileMagic.from_buffer(data)

    if mimeType == 'application/xml':
      self.fileType = 'vector'
      self.data = data
    elif mimeType == 'application/zip':
      self.fileType = 'vector'
      self.extractKmz(data)
    elif mimeType in ('image/png', 'image/gif'):
      self.fileType = 'raster'
      self.data = data
    else:
      logging.warning('Unsupported MIME type: {0}'.format(mimeType))
      return False

    return True

  def extractKmz(self, kmzData):
    # ZipFile cannot read ZIP data from a string, so convert the string into a
    # file-like object using StringIO.
    kmzDataIO = StringIO.StringIO(kmzData)

    # Create and read ZIP file contents without touching the filesystem.
    kmzZip = zipfile.ZipFile(kmzDataIO)
    kmzFileList = kmzZip.namelist()

    # Find KML file(s) inside the KMZ layer.
    allKmlFiles = filter(lambda x: os.path.splitext(x)[1].lower() == '.kml', kmzFileList)

    # This script currently supports KMZ files containing only one KML file.
    if len(allKmlFiles) != 1:
      logging.error('Unexpected number of KML files found inside KMZ file for layer "{0}":'.format(self.name))
      logging.error(allKmlFiles)
    else:
      kmlFileName = allKmlFiles[0]

    # Read KML layer from ZIP file and process its contents.
    kmlData = kmzZip.read(kmlFileName)

    self.data = kmlData

  def processKml(self):
    mimeType = Layer.fileMagic.from_buffer(self.data)
    if mimeType != 'application/xml':
      return False

    # Process sublayers through recursion.
    sublayers = self.getSublayers()
    if sublayers:
      Layer.processLayerList(sublayers)

    return True

  def convertVector(self):
    kmlFile = tempfile.NamedTemporaryFile()
    kmlFile.write(self.data)
    kmlFile.seek(0)

    shapeDir = tempfile.mkdtemp()
    shapeFileName = Layer.getCleanFileName(self.name, 'shp')
    shapeFilePath = '{0}/{1}'.format(shapeDir, shapeFileName)

    ogrArguments = [
      'ogr2ogr',
      '-f',
      'ESRI Shapefile',
      shapeFilePath,
      kmlFile.name,
    ]

    ogrProcess = subprocess.Popen(ogrArguments, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    ogrOutput, ogrErrors = ogrProcess.communicate()

    if ogrProcess.returncode:
      logging.error('ogr2ogr command failed:')
      logging.error(' '.join(ogrArguments))
      logging.debug(ogrOutput)
      logging.debug(ogrErrors)
      return False

    shapeFiles = {}
    for rootDir, subDirs, files in os.walk(shapeDir):
      for shapeFile in files:
        filePrefix = os.path.splitext(shapeFile)[0]
        try:
          shapeFiles[filePrefix]
        except:
          shapeFiles[filePrefix] = []
        shapeFiles[filePrefix].append(shapeFile)

      for shapePrefix in shapeFiles.keys():
        shapeZipTemp = tempfile.NamedTemporaryFile()
        shapeZip = zipfile.ZipFile(shapeZipTemp, 'w')
        for part in shapeFiles[shapePrefix]:
          shapeZip.write('{0}/{1}'.format(rootDir, part), part)
        shapeZip.close()
        shapeZipTemp.seek(0)
        layerName = '{0}/{1}'.format(self.name, shapePrefix)
        layerFileName = Layer.getCleanFileName(layerName, 'zip')
        Layer.write(layerFileName, shapeZipTemp.read())
        shapeZipTemp.close()
        logging.info('Wrote file: {0}'.format(layerFileName))

    return True

  def convertRaster(self):
    plainImageFile = tempfile.NamedTemporaryFile()
    plainImageFile.write(self.data)
    plainImageFile.seek(0)
    geoTiffFile = tempfile.NamedTemporaryFile()

    gdalArguments = [
      'gdal_translate',
      '-of',
      'Gtiff',
      '-a_ullr',
      self.boundingBox['west'],
      self.boundingBox['north'],
      self.boundingBox['east'],
      self.boundingBox['south'],
      '-a_srs',
      'EPSG:4326',
      plainImageFile.name,
      geoTiffFile.name
    ]

    # Run gdal_transate, capturing output and errors for debugging.
    gdalProcess = subprocess.Popen(gdalArguments, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    gdalOutput, gdalErrors = gdalProcess.communicate()

    if gdalProcess.returncode:
      logging.error('gdal_translate command failed:')
      logging.error(' '.join(gdalArguments))
      logging.debug(gdalOutput)
      logging.debug(gdalErrors)
      return False

    geoTiffFile.seek(0)
    layerFileName = Layer.getCleanFileName(self.name, 'tif')
    Layer.write(layerFileName, geoTiffFile.read())
    geoTiffFile.close()
    logging.info('Wrote file: {0}'.format(layerFileName))
    return True

  @staticmethod
  def write(layerFileName, layerData):
    # Make sure we have an output directory.
    if not os.path.exists(outputDir):
      os.mkdir(outputDir)

    try:
      outputFile = open('{0}/{1}'.format(outputDir, layerFileName), 'w')
      outputFile.write(layerData)
      outputFile.close()
    except Exception, e:
      logging.exception(e)
      return False

    return layerFileName

  # Parse layer as XML and set as ElementTree root node.
  def getXmlTree(self):
    try:
      etreeElement = lxml.etree.XML(self.data)
    except Exception, e:
      logging.exception(e)
      return False
    return lxml.etree.ElementTree(etreeElement)

  @staticmethod
  def getCleanFileName(prefix, extension):
    cleanPrefix = re.sub(r'[^a-zA-Z_0-9]', '_', prefix)
    return '{0}.{1}'.format(cleanPrefix, extension)

  def getSublayers(self):
    tree = self.getXmlTree()
    if not tree:
      return False

    sublayers = []

    sublayerTypes = {
      'NetworkLink': {
        'rootXPath': './/*[local-name() = "NetworkLink"]',
        'nameXPath': './*[local-name() = "name"]/text()',
        'urlXPath': './*[local-name() = "Link"]/*[local-name() = "href"]/text()'
      },
      'GroundOverlay': {
        'rootXPath': './/*[local-name() = "GroundOverlay"]',
        'nameXPath': './*[local-name() = "name"]/text()',
        'urlXPath': './*[local-name() = "Icon"]/*[local-name() = "href"]/text()'
      }
    }

    for sublayerType, xPaths in sublayerTypes.iteritems():
      for node in tree.xpath(xPaths['rootXPath']):
        nodeName = node.xpath(xPaths['nameXPath'])
        nodeUrl = node.xpath(xPaths['urlXPath'])
        if nodeName:
          sublayerName = '{0}/{1}'.format(self.name, nodeName[0])
        if nodeUrl:
          sublayerUrl = nodeUrl[0]
          sublayers.append(Layer(sublayerName, sublayerUrl))

    for layer in sublayers:
      layer.download()
      if layer.fileType == 'raster':
        latLonBox = node.xpath('./*[local-name() = "LatLonBox"]')[0]
        layer.boundingBox['north'] = latLonBox.xpath('./*[local-name() = "north"]/text()')[0]
        layer.boundingBox['south'] = latLonBox.xpath('./*[local-name() = "south"]/text()')[0]
        layer.boundingBox['east'] = latLonBox.xpath('./*[local-name() = "east"]/text()')[0]
        layer.boundingBox['west'] = latLonBox.xpath('./*[local-name() = "west"]/text()')[0]
      
    return sublayers

  def process(self):
    if not self.data:
      self.download()

    if self.fileType == 'vector' and self.data:
      usefulKml = self.processKml()
      if usefulKml:
        self.convertVector()
    elif self.fileType == 'raster' and self.data:
      self.convertRaster()
    else:
      logging.warning('No useable content in layer "{0}" from: {1}'.format(self.name, self.url))
      return False

    return True

  # Process list of layers.
  @staticmethod
  def processLayerList(allLayers):
    for layer in allLayers:
      layer.process()
