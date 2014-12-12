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
layers = {
  'COP': 'http://weather.msfc.nasa.gov/ACE/latestALCOMCOP.kml',
}

# Process list of layers.
def processLayerList(allLayers):
  for layerName, url in allLayers.iteritems():
    processLayer(layerName, url)

# Process a layer.
def processLayer(layerName, url):
  kmlData = downloadLayer(url)

  if kmlData:
    cleanKml = parseKml(layerName, kmlData)
  else:
    if debug:
      print 'Failed to download layer "{0}" from: {1}'.format(layerName, url)
    return False

  if cleanKml:
    fileName = writeKml(layerName, cleanKml)
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
      print 'Failed to write layer "{0}" from: {1}'.format(layerName, url)

def downloadLayer(url):
  # Download KMZ layer from URL.
  try:
    response = urllib2.urlopen(url)
  except Exception, e:
    if debug:
      print e
    return False
  data = response.read()

  # Analyze file contents to determine MIME type.
  fileMagic = magic.Magic(mime = True)
  mimeType = fileMagic.from_buffer(data)

  # Return KML data if we have a valid source, or False if not.
  if mimeType == 'application/xml':
    return data
  elif mimeType == 'application/zip':
    return extractKmz(data)
  else:
    print 'Unsupported MIME type: {0}'.format(mimeType)
    return False

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

# This function processes KML data regardless of whether it originally came
# from a KML file or a KMZ file. It will use whatever layerName you pass it as
# the processed KML's output file name.
def parseKml(layerName, kmlData):
  # Parse layer as XML and set as ElementTree root node.
  try:
    etreeElement = lxml.etree.XML(kmlData)
  except Exception, e:
    if debug:
      print e
    return False
  tree = lxml.etree.ElementTree(etreeElement)

  sublayers = {}

  sublayerNodes = tree.xpath('.//*[local-name() = "NetworkLink"]')
  sublayerNameXPath = './*[local-name() = "name"]/text()'
  sublayerLinkXPath = './*[local-name() = "Link"]/*[local-name() = "href"]/text()'
  sublayers.update(getSublayers(layerName, sublayerNodes, sublayerNameXPath, sublayerLinkXPath))

  sublayerNodes = tree.xpath('.//*[local-name() = "GroundOverlay"]')
  sublayerNameXPath = './*[local-name() = "name"]/text()'
  sublayerLinkXPath = './*[local-name() = "Icon"]/*[local-name() = "href"]/text()'
  sublayers.update(getSublayers(layerName, sublayerNodes, sublayerNameXPath, sublayerLinkXPath))

  # Recursive step.
  processLayerList(sublayers)

  # Unconfirmed assumption based on experience so far:
  # Layers with no Placemark or NetworkLink nodes have nothing to give GeoNode.
  if not tree.xpath('.//*[local-name() = "Placemark"]'):
    return False

  # Encode invalid characters.
  encodeElements(tree.xpath('.//*[local-name() = "styleUrl"]'))
  encodeElements(tree.xpath('.//*[local-name() = "Style" and @id]'), 'id')

  return lxml.etree.tostring(tree)

def getSublayers(layerName, allNodes, nameXPath, linkXPath):
  counter = 1
  sublayers = {}

  for node in allNodes:
    # Get this sublayers's name. If it is unnamed, give it a number.
    sublayerName = node.xpath(nameXPath)
    if sublayerName:
      sublayerName = '{0}/{1}'.format(layerName, sublayerName[0])
    else:
      sublayerName = '{0}/{1}'.format(layerName, counter)
      counter += 1

    # Get this sublayer's URL. If it does not have one, skip it.
    sublayerUrl = node.xpath(linkXPath)
    if sublayerUrl:
      sublayers[sublayerName] = sublayerUrl[0]
    else:
      continue

  return sublayers

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
