#!/usr/bin/env python
import rfc3987
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

class Config:
  outputDir = None
  fileMagic = magic.Magic(mime = True)

  # Process list of layers.
  @staticmethod
  def processLayerList(allLayers):
    if Config.outputDir is None:
      logging.error('You must set the outputDir before processing a layer list.')
      return False

    for layer in allLayers:
      layer.process()

class Layer:
  name = None
  location = None
  fileType = None
  data = None
  kmzZip = None
  boundingBox = {}
  layerTrail = []

  def __init__(self, name, location, layerTrail = [], kmzZip = None):
    self.name = name
    self.location = location
    self.layerTrail = layerTrail
    self.layerTrail.append(self.name)
    self.kmzZip = kmzZip

  def download(self):
    logging.info('Downloading {0} from {1}'.format(self.name, self.location))

    try:
      rfc3987.parse(self.location, rule='IRI')
      isUrl = True
    except:
      isUrl = False

    if isUrl:
      # Download layer from URL.
      try:
        response = urllib2.urlopen(self.location)
        data = response.read()
      except Exception, e:
        logging.exception(e)
        return False
    elif self.kmzZip is not None:
      try:
        data = self.kmzZip.read(self.location)
      except Exception, e:
        logging.exception(e)
        return False
    else:
      logging.warning('Invalid URL or file path for layer {0}'.format(self.name))
      return False

    # Analyze file contents to determine MIME type.
    mimeType = Config.fileMagic.from_buffer(data)

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
    self.kmzZip = kmzZip

  def processKml(self):
    mimeType = Config.fileMagic.from_buffer(self.data)
    if mimeType != 'application/xml':
      return False

    # Process sublayers through recursion.
    sublayers = self.getSublayers()
    if sublayers:
      Config.processLayerList(sublayers)

    return True

  def convertVector(self):
    kmlFile = tempfile.NamedTemporaryFile()
    kmlFile.write(self.data)
    kmlFile.seek(0)

    tempDir = tempfile.mkdtemp()
    fileName = '{0}.shp'.format(self.name)
    safeFileName = Layer.fileNameFilter(fileName)
    shapeFilePath = '{0}/{1}'.format(tempDir, safeFileName)

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
    for rootDir, subDirs, files in os.walk(tempDir):
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
        fileName = '{0}.zip'.format(shapePrefix)
        fullFilePath = self.write(fileName, shapeZipTemp.read())
        shapeZipTemp.close()
        logging.info('Wrote file: {0}'.format(fullFilePath))

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
    fileName = '{0}.tif'.format(self.name)
    fullFilePath = self.write(fileName, geoTiffFile.read())
    geoTiffFile.close()
    logging.info('Wrote file: {0}'.format(fullFilePath))
    return True

  def getFullPath(self, fileName):
    safeFileName = Layer.fileNameFilter(fileName)
    directories = self.layerTrail[:]
    directories.insert(0, Config.outputDir)
    safeDirectories = map(Layer.fileNameFilter, directories)
    safeDirectoryPath = '/'.join(safeDirectories)

    if not os.path.exists(safeDirectoryPath):
      os.makedirs(safeDirectoryPath)

    return (safeDirectoryPath, safeFileName)

  def write(self, fileName, fileData):
    directoryPath, fileName = self.getFullPath(fileName)
    fullFilePath = '{0}/{1}'.format(directoryPath, fileName)

    try:
      outputFile = open(fullFilePath, 'w')
      outputFile.write(fileData)
      outputFile.close()
    except Exception, e:
      logging.exception(e)
      return False

    return fullFilePath

  # Parse layer as XML and set as ElementTree root node.
  def getXmlTree(self):
    try:
      etreeElement = lxml.etree.XML(self.data)
    except Exception, e:
      logging.exception(e)
      return False
    return lxml.etree.ElementTree(etreeElement)

  def getSublayers(self):
    tree = self.getXmlTree()
    if not tree:
      return False

    sublayers = []

    sublayerTypes = {
      'NetworkLink': {
        'rootXPath': './/*[local-name() = "NetworkLink"]',
        'nameXPath': './*[local-name() = "name"]/text()',
        'locationXPath': './*[local-name() = "Link"]/*[local-name() = "href"]/text()',
        'latlonXPath': None,
        'cardinalXPath': None
      },
      'GroundOverlay': {
        'rootXPath': './/*[local-name() = "GroundOverlay"]',
        'nameXPath': './*[local-name() = "name"]/text()',
        'locationXPath': './*[local-name() = "Icon"]/*[local-name() = "href"]/text()',
        'latlonXPath': './*[local-name() = "LatLonBox"]',
        'cardinalXPath': './*[local-name() = "{0}"]/text()'
      }
    }

    for sublayerType, xPaths in sublayerTypes.iteritems():
      for node in tree.xpath(xPaths['rootXPath']):
        nodeName = node.xpath(xPaths['nameXPath'])
        nodeLocation = node.xpath(xPaths['locationXPath'])

        if nodeName and nodeLocation:
          sublayerName = nodeName[0]
          sublayerLocation = nodeLocation[0]
          newLayer = Layer(sublayerName, sublayerLocation, [self.name], self.kmzZip)
        else:
          continue

        if xPaths['latlonXPath']:
          latLonBoxMatch = node.xpath(xPaths['latlonXPath'])
          if not latLonBoxMatch:
            continue
          latLonBox = latLonBoxMatch[0]
          for direction in ('north', 'south', 'east', 'west'):
            newLayer.boundingBox[direction] = latLonBox.xpath(xPaths['cardinalXPath'].format(direction))[0]

        sublayers.append(newLayer)

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
      logging.warning('No usable content in layer "{0}" from: {1}'.format(self.name, self.location))
      return False

    return True

  # Make strings filesystem safe.
  @staticmethod
  def fileNameFilter(string):
    fileNameParts = string.rsplit('.', 1)
    safeFileNameParts = map(lambda x: re.sub(r'[^a-zA-Z_0-9]', '_', x), fileNameParts)
    safeFileName = '.'.join(safeFileNameParts)
    return safeFileName

