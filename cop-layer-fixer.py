#!/usr/bin/python
import os
import urllib2
import magic
import lxml.etree
import zipfile
import StringIO
import re
import sys

debug = False
outputDir = 'output'

class Layer:
  name = None
  url = None
  mimeType = None
  data = None
  boundingBox = {}

  def __init__(self, name, url):
    self.name = name
    self.url = url

  # Parse layer as XML and set as ElementTree root node.
  def getXmlTree(self):
    try:
      etreeElement = lxml.etree.XML(self.data)
    except Exception, e:
      if debug:
        print e
      return False
    return lxml.etree.ElementTree(etreeElement)

  def download(self):
    # Download KMZ layer from URL.
    try:
      response = urllib2.urlopen(self.url)
    except Exception, e:
      if debug:
        print e
      return False
    data = response.read()

    # Analyze file contents to determine MIME type.
    fileMagic = magic.Magic(mime = True)
    self.mimeType = fileMagic.from_buffer(data)

    # Return KML data if we have a valid source, or False if not.
    if self.mimeType == 'application/xml':
      self.data = data
    elif self.mimeType == 'application/zip':
      self.data = extractKmz(data)
    elif self.mimeType in ('image/png', 'image/gif'):
      self.data = data
    else:
      print 'Unsupported MIME type: {0}'.format(self.mimeType)
      return False

  def process(self):
    if not self.data:
      self.download()

    # Clean the KML.
    if self.mimeType == 'application/xml' and self.data:
      self.parseKml()
    elif self.mimeType in ('image/png', 'image/gif') and self.data:
      print 'Found a {0} file.'.format(self.mimeType)
    else:
      if debug:
        print 'No useable content in layer "{0}" from: {1}'.format(self.name, self.url)
      return False

    # Write the KML, if parseKml() returned working data.
    if self.mimeType == 'application/xml' and self.data:
      fileName = writeKml(self.name, self.data)
    else:
      # Some layers are just containers for sublayers, which are processed
      # independently through recursion. There is no need to write layers that
      # are just containers. But we need to be vigilant that we are catching all
      # layer features. Are Placemarks the only possible vector layer features?
      return False

    if fileName:
      print 'Wrote layer to file: {0}'.format(fileName)
    else:
      if debug:
        print 'Failed to write layer "{0}" from: {1}'.format(self.name, self.url)

  # This function processes KML data regardless of whether it originally came
  # from a KML file or a KMZ file. It will use whatever layerName you pass it as
  # the processed KML's output file name.
  def parseKml(self):
    tree = self.getXmlTree()
    sublayers = []

    sublayerNodes = tree.xpath('.//*[local-name() = "NetworkLink"]')
    sublayerNameXPath = './*[local-name() = "name"]/text()'
    sublayerLinkXPath = './*[local-name() = "Link"]/*[local-name() = "href"]/text()'
    sublayers.extend(getSublayers(self, sublayerNodes, sublayerNameXPath, sublayerLinkXPath))

    sublayerNodes = tree.xpath('.//*[local-name() = "GroundOverlay"]')
    sublayerNameXPath = './*[local-name() = "name"]/text()'
    sublayerLinkXPath = './*[local-name() = "Icon"]/*[local-name() = "href"]/text()'
    sublayers.extend(getSublayers(self, sublayerNodes, sublayerNameXPath, sublayerLinkXPath))

    # Recursive step.
    processLayerList(sublayers)

    # Unconfirmed assumption based on experience so far:
    # Layers with no Placemark or NetworkLink nodes have nothing to give GeoNode.
    if not tree.xpath('.//*[local-name() = "Placemark"]'):
      return False

    # Encode invalid characters.
    encodeElements(tree.xpath('.//*[local-name() = "styleUrl"]'))
    encodeElements(tree.xpath('.//*[local-name() = "Style" and @id]'), 'id')

    self.data = lxml.etree.tostring(tree)

layers = [
  Layer('COP', 'http://weather.msfc.nasa.gov/ACE/latestALCOMCOP.kml')
]

# Process list of layers.
def processLayerList(allLayers):
  for layer in allLayers:
    layer.process()

def extractKmz(kmzData):
  # ZipFile cannot read ZIP data from a string, so convert the string into a
  # file-like object using StringIO.
  kmzDataIO = StringIO.StringIO(kmzData)

  # Create and read ZIP file contents without touching the filesystem.
  kmzZip = zipfile.ZipFile(kmzDataIO)
  kmzFileList = kmzZip.namelist()

  # Find KML file(s) inside the KMZ layer.
  allKmlFiles = filter(lambda x: os.path.splitext(x)[1] == '.kml', kmzFileList)

  # This script works with the assumption that there is only one KML file
  # inside each KMZ layer. So far this has been the case with the JTF-AK COP
  # layers, but if it changes, or if this script processes new KMZ layers with
  # multiple KML files, we need to make sure to catch it and figure out how to
  # change this script accordingly.
  if len(allKmlFiles) != 1:
    print 'Unexpected number of KML files found inside KMZ file for layer "{0}":'.format(layerName)
    print allKmlFiles
  else:
    kmlFileName = allKmlFiles[0]

  # Read KML layer from ZIP file and process its contents.
  kmlData = kmzZip.read(kmlFileName)

  return kmlData

def getSublayers(layer, allNodes, nameXPath, linkXPath):
  counter = 1
  newSublayers = []

  for node in allNodes:
    # Get this sublayers's name. If it is unnamed, give it a number.
    sublayerName = node.xpath(nameXPath)
    if sublayerName:
      sublayerName = '{0}/{1}'.format(layer.name, sublayerName[0])
    else:
      sublayerName = '{0}/{1}'.format(layer.name, counter)
      counter += 1

    # Get this sublayer's URL. If it does not have one, skip it.
    sublayerUrl = node.xpath(linkXPath)
    if sublayerUrl:
      sublayer = Layer(sublayerName, sublayerUrl[0])
    else:
      continue

    sublayer.download()

    if sublayer.mimeType in ('image/png', 'image/gif'):
      latLonBox = node.xpath('./*[local-name() = "LatLonBox"]')[0]
      sublayer.boundingBox['north'] = latLonBox.xpath('./*[local-name() = "north"]')[0]
      sublayer.boundingBox['south'] = latLonBox.xpath('./*[local-name() = "south"]')[0]
      sublayer.boundingBox['east'] = latLonBox.xpath('./*[local-name() = "east"]')[0]
      sublayer.boundingBox['west'] = latLonBox.xpath('./*[local-name() = "west"]')[0]
      
    newSublayers.append(sublayer)

  return newSublayers

# Pass this function a list of ElementTree elements that need encoding. If an
# attribute parameter is specified, it will encode that attribute's value. If
# no attribute parameter is specified, it will encode the node's text.
def encodeElements(allElements, attribute = None):
  for element in allElements:
    if attribute:
      try:
        element.set(attribute, urllib2.quote(element.attrib[attribute], '#'))
      except Exception, e:
        if debug:
          print e
        return False
    else:
      element.text = urllib2.quote(element.text, '#')
  return True

def writeKml(layerName, data):
  # Make sure we have an output directory.
  if not os.path.exists(outputDir):
    os.mkdir(outputDir)

  # Write modified KML file using cleaned layer name as file name.
  layerFilePrefix = re.sub(r'[^a-zA-Z_0-9]', '_', layerName)
  try:
    layerFileName = '{0}.kml'.format(layerFilePrefix)
    outputFile = open('{0}/{1}'.format(outputDir, layerFileName), 'w')
    outputFile.write(data)
    outputFile.close()
  except Exception, e:
    if debug:
      print e
    return False

  return layerFileName

processLayerList(layers)
