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

# Configuration and utility functions.
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

# Each instance of Layer is either a KML file or raster image.
class Layer:

  # Human readable name of the layer.
  name = None

  # This is either a URL or a path inside a KMZ file.
  location = None

  # This will be set to either vector or raster.
  fileType = None

  # The actual KML content or raster data.
  data = None

  # If this layer is part of a KMZ file, keep it around in case we need it.
  kmzZip = None

  # If this is a raster, we'll need to capture a bounding box for it.
  boundingBox = {}

  # The list of nested layers leading to this one.
  # This is used for both logging purposes and to build our output directory tree.
  layerTrail = []

  # Instantiate a layer, defaulting to an empty layerTrail for first level layers.
  def __init__(self, name, location, layerTrail = [], kmzZip = None):
    self.name = name
    self.location = location
    self.layerTrail = layerTrail
    self.layerTrail.append(self.name)
    self.kmzZip = kmzZip

  # Either download the layer from a URL or extract it from a KMZ file.
  def getLayerData(self):

    # Is this a proper URL?
    try:
      rfc3987.parse(self.location, rule='IRI')
      isUrl = True
    except:
      isUrl = False

    # Download layer from URL.
    if isUrl:
      logging.info('Downloading {0} from {1}'.format(self.name, self.location))
      try:
        response = urllib2.urlopen(self.location)
        data = response.read()
      except Exception, e:
        logging.exception(e)
        return False
    # Extract layer from KMZ file.
    elif self.kmzZip is not None:
      logging.info('Extracting {0} from {1}'.format(self.name, self.location))
      try:
        data = self.kmzZip.read(self.location)
      except Exception, e:
        logging.exception(e)
        return False
    # This is not a URL, and we don't have a KMZ file. There's no way to proceed.
    else:
      logging.warning('Invalid URL or file path for layer {0}'.format(self.name))
      return False

    # Analyze file data to determine MIME type.
    mimeType = Config.fileMagic.from_buffer(data)

    # KML
    if mimeType == 'application/xml':
      self.fileType = 'vector'
      self.data = data
    # KMZ
    elif mimeType == 'application/zip':
      self.fileType = 'vector'
      self.extractKmz(data)
    # Raster
    elif mimeType in ('image/png', 'image/gif'):
      self.fileType = 'raster'
      self.data = data
    # Unsupported.
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

    # This script currently supports only one vector layer inside a KMZ file.
    if len(allKmlFiles) != 1:
      logging.error('Unexpected number of KML files found inside KMZ file for layer "{0}":'.format(self.name))
      logging.error(allKmlFiles)
    else:
      kmlFileName = allKmlFiles[0]

    # Read KML layer from ZIP file and process its contents.
    kmlData = kmzZip.read(kmlFileName)

    # Store KML data.
    self.data = kmlData

    # Keep KMZ zip file around in case we need to extract more from it later.
    self.kmzZip = kmzZip

  # Do KML validation checks and scan for sublayers.
  def processKml(self):
    mimeType = Config.fileMagic.from_buffer(self.data)
    if mimeType != 'application/xml':
      return False

    # Process sublayers through recursion.
    sublayers = self.getSublayers()
    if sublayers:
      Config.processLayerList(sublayers)

    return True

  # Convert KML data into shapefiles using GDAL's ogr2ogr utility.
  def convertVector(self):

    # Write KML data to a temporary file on file system.
    kmlFile = tempfile.NamedTemporaryFile()
    kmlFile.write(self.data)
    kmlFile.seek(0)

    # Create temporary directory for shapefile output.
    tempDir = tempfile.mkdtemp()
    fileName = '{0}.shp'.format(self.name)
    safeFileName = Layer.fileNameFilter(fileName)
    shapeFilePath = '{0}/{1}'.format(tempDir, safeFileName)

    # Set up ogr2ogr system call.
    ogrArguments = [
      'ogr2ogr',
      '-f',
      'ESRI Shapefile',
      shapeFilePath,
      kmlFile.name,
    ]

    # Run ogr2ogr, capturing output and errors for debugging.
    ogrProcess = subprocess.Popen(ogrArguments, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
    ogrOutput, ogrErrors = ogrProcess.communicate()

    # ogr2ogr generates lots of different warnings and errors. Make sure the user sees them.
    if ogrProcess.returncode:
      logging.error('ogr2ogr command failed:')
      logging.error(' '.join(ogrArguments))
      logging.debug(ogrOutput)
      logging.debug(ogrErrors)
      return False

    # Scan through output directory. Store and group shapefiles by file prefix.
    shapeFiles = {}
    for rootDir, subDirs, files in os.walk(tempDir):
      for shapeFile in files:
        filePrefix = os.path.splitext(shapeFile)[0]
        try:
          shapeFiles[filePrefix]
        except:
          shapeFiles[filePrefix] = []
        shapeFiles[filePrefix].append(shapeFile)

      # Combine each shapefile file group into a single zip file.
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

  # Convert raster data into GeoTIFFs using GDAL's gdal_translate utility.
  def convertRaster(self):

    # Generate a temporary file on the file system for our output.
    plainImageFile = tempfile.NamedTemporaryFile()
    plainImageFile.write(self.data)
    plainImageFile.seek(0)
    geoTiffFile = tempfile.NamedTemporaryFile()

    # Setup and perform gdal_translate system call.
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

    # Show the user any warnings or errors we encounter.
    if gdalProcess.returncode:
      logging.error('gdal_translate command failed:')
      logging.error(' '.join(gdalArguments))
      logging.debug(gdalOutput)
      logging.debug(gdalErrors)
      return False

    # Copy the temporary file data into the script's output directory.
    geoTiffFile.seek(0)  
    fileName = '{0}.tif'.format(self.name)
    fullFilePath = self.write(fileName, geoTiffFile.read())
    geoTiffFile.close()
    logging.info('Wrote file: {0}'.format(fullFilePath))
    return True

  # Use the layerTrail list to determine nested file system location.
  def getFullPath(self, fileName):
    safeFileName = Layer.fileNameFilter(fileName)
    directories = self.layerTrail[:]
    directories.insert(0, Config.outputDir)
    safeDirectories = map(Layer.fileNameFilter, directories)
    safeDirectoryPath = '/'.join(safeDirectories)

    # Create the output directory if it does not already exist.
    if not os.path.exists(safeDirectoryPath):
      os.makedirs(safeDirectoryPath)

    return (safeDirectoryPath, safeFileName)

  # Write the layer to the file system.
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
      return lxml.etree.ElementTree(etreeElement)
    except Exception, e:
      logging.exception(e)
      return False

  # Parse the KML for either vector or raster sublayers.
  def getSublayers(self):

    # Parse the KML into an XML tree so we can use XPath expressions.
    tree = self.getXmlTree()
    if not tree:
      return False

    sublayers = []

    # Assign the appropriate XPath expressions for each supports sublayer type,
    # based on the KML schema. This page helps clarify:
    # https://developers.google.com/kml/documentation/kmlreference
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

    # Iterate through our supported sublayerTypes, using each type's XPath expressions
    # to grab the data we need.
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

        # We need to capture a bounding box for GeoTIFFs.
        if xPaths['latlonXPath']:
          latLonBoxMatch = node.xpath(xPaths['latlonXPath'])
          if not latLonBoxMatch:
            continue
          latLonBox = latLonBoxMatch[0]
          for direction in ('north', 'south', 'east', 'west'):
            newLayer.boundingBox[direction] = latLonBox.xpath(xPaths['cardinalXPath'].format(direction))[0]

        sublayers.append(newLayer)

    return sublayers

  # Process a layer.
  def process(self):
    if not self.data:
      self.getLayerData()

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

    # Replace any special characters with underscores in file name prefix.
    safeFileNameParts = map(lambda x: re.sub(r'[^a-zA-Z_0-9]', '_', x), fileNameParts)

    safeFileName = '.'.join(safeFileNameParts)
    return safeFileName

