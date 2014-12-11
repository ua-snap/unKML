#!/usr/bin/python
import os
import urllib2
import magic
import lxml.etree
import zipfile
import StringIO
import re
import sys

outputDir = 'output'

copLayers = {
  'Alaska Surface Analysis': 'http://www.hpc.ncep.noaa.gov/alaska/kml/ak_analysis_transparent.kml',
  'Alaska 4-8 Day Surface Forecasts': 'http://www.hpc.ncep.noaa.gov/alaska/kml/ak_pmsl_fcst_transparent.kml',
  'Alaska 4-8 Day 500mb Height Forecasts': 'http://www.hpc.ncep.noaa.gov/alaska/kml/ak_500mb_fcst_transparent.kml',
  'METAR Observations': 'http://www.srh.noaa.gov/gis/kml/metar/metarlink.kml',
  'Air Quality Information': 'http://www.epa.gov/airnow/today/airnow.kml',
  'Alaska USDA Forest Service': 'http://activefiremaps.fs.fed.us/data/kml/alaska_latest_AFM_bundle.kml',
  'Plume Trajectories': 'http://weather.msfc.nasa.gov/ACE/volcanoTrajectories.kml',
  'AK DOT Bridges': 'http://www.dot.alaska.gov/stwdplng/mapping/transdata/GE_Files/AKDOT_Bridges_April2013.kml',
  'AK Ferry Terminals': 'http://www.dot.alaska.gov/stwdplng/mapping/transdata/GE_Files/Ferry_Terminals_May2013.kml',
  'AK Public Airports': 'http://www.dot.alaska.gov/stwdplng/mapping/transdata/GE_Files/Public_Airports_May2013.kml',
  'Alaska BLM Fire Information': 'http://afsmaps.blm.gov/imf/sites/help/AlaskaWildfires.kml',
  'AK DOT Route Centerlines': 'http://www.dot.alaska.gov/stwdplng/mapping/transdata/GE_Files/Alaska_DOTPF_RoadSystem.kml',
  'River Ice Thickness': 'http://aprfc.arh.noaa.gov/php/icedb/map_ice_kml.php',
  'USGS Magnitude 1.0+ Earthquakes, Past Week': 'http://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/1.0_week_age.kml',
  'Fire Locations': 'http://www.ospo.noaa.gov/data/land/fire/fire.kml',
  'GINA Fire Points': 'http://kml.gina.alaska.edu/fire.kml',
  'Smoke': 'http://www.ospo.noaa.gov/data/land/fire/smoke.kml',
  'Volcano Status': 'http://weather.msfc.nasa.gov/ACE/volcano.kml',
  'AK DOT Mileposts': 'http://www.dot.alaska.gov/stwdplng/mapping/transdata/GE_Files/Alaska_Mileposts.kml',
  'AK Railroad Mileposts': 'https://ace.arsc.edu/system/files/arrc_database.MPL__0.kml',
  'Alaska Coastal Marine': 'http://weather.msfc.nasa.gov/ACE/AlaskaCoastalMarineZones.kmz',
  'Alaska Offshore Marine': 'http://weather.msfc.nasa.gov/ACE/AlaskaOffShoreMarineZones.kmz',
  'Alaska Zone Alerts': 'http://weather.msfc.nasa.gov/ACE/AlaskaLandZones.kmz',
  'Radar Composite Reflectivity': 'https://ace.arsc.edu/system/files/NWS_Radar_data%20%284%29.kmz',
  'Radar Doppler Velocity': 'https://ace.arsc.edu/system/files/Alaska--Velocity--NWS_Radar_data.kmz',
  'Radar 1 Hr Precipitation': 'https://ace.arsc.edu/system/files/NWS_Radar_data%283%29.kmz',
  'NWS Warnings': 'http://radar.weather.gov/ridge/warningzipmaker.php',
  'NWS Watches': 'http://wdssii.nssl.noaa.gov/realtime/nws_warnings.kmz',
  'River Remarks at Alaska River Gages': 'http://aprfc.arh.noaa.gov/gages/remarks.kmz',
  '3-Day Snow Depth Change at River Gages': 'http://aprfc.arh.noaa.gov/gages/3daysd.kmz',
  'Total Ozone Forecast': 'https://ace.arsc.edu/system/files/Total%20Ozone%20RAQDPS%20EC.kmz',
  'Disaster Area': 'http://gis.fema.gov/kmz/DesignatedCounties.kmz',
  'Flood Zones': 'https://hazards.fema.gov/femaportal/kmz/FEMA_NFHL_v3.0.kmz',
  'Ice - MASIE': 'http://weather.msfc.nasa.gov/masie/latest_masie.kmz',
  'Ice - MIZ': 'http://www.natice.noaa.gov/pub/special/google_kml/arctic.kmz',
  'AK Pavement Conditions': 'http://www.dot.alaska.gov/stwdmno/pvmtmgt/data/roads/AllData.kmz',
  'Tsunami - DART Buoys': 'https://ace.arsc.edu/system/files/Tsunami.kmz',
}

def processLayer(layerName, url):
  kmlData = downloadLayer(url)

  if kmlData:
    cleanKml = parseKml(layerName, kmlData)
  else:
    print 'Failed to download layer "{0}" from: {1}'.format(layerName, url)
    return False

  if cleanKml:
    writeSuccess = writeKml(layerName, cleanKml)
  else:
    # Unconfirmed assumption based on experience so far:
    # Layers with no Placemark nodes have nothing useful except for
    # NetworkLinks, which are processed indepedently through recursion.
    print 'Found nothing useful in, or failed to parse, layer "{0}" from: {1}'.format(layerName, url)
    return False

  if not writeSuccess:
    print 'Failed to write layer "{0}" from: {1}'.format(layerName, url)

def downloadLayer(url):
  # Download KMZ layer from URL.
  try:
    response = urllib2.urlopen(url)
  except Exception, e:
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
    print e
    return False
  tree = lxml.etree.ElementTree(etreeElement)

  counter = 1
  allNetworkLinks = tree.xpath('.//*[local-name() = "NetworkLink"]')
  for networkLink in allNetworkLinks:
    # Get this NetworkLink's name. If it is unnamed, give it a number.
    networkLinkName = networkLink.xpath('./*[local-name() = "name"]/text()')
    if networkLinkName:
      subName = networkLinkName[0]
    if not networkLinkName:
      subName = counter
      counter += 1
    newLayerName = '{0}/{1}'.format(layerName, subName)

    # Get this NetworkLink's URL. If it does not have one, skip it.
    networkLinkUrl = networkLink.xpath('./*[local-name() = "Link"]/*[local-name() = "href"]/text()')
    if networkLinkUrl:
      processLayer(newLayerName, networkLinkUrl[0])
    else:
      print 'Missing URL in NetworkLink "{0}".'.format(newLayerName)

  # Unconfirmed assumption based on experience so far:
  # Layers with no Placemark or NetworkLink nodes have nothing to give GeoNode.
  if not tree.xpath('.//*[local-name() = "Placemark"]'):
    return False

  # Encode invalid characters.
  encodeElements(tree.xpath('.//*[local-name() = "styleUrl"]'))
  encodeElements(tree.xpath('.//*[local-name() = "Style" and @id]'), 'id')

  return lxml.etree.tostring(tree)

# Pass this function a list of ElementTree elements that need encoding. If an
# attribute parameter is specified, it will encode that attribute's value. If
# no attribute parameter is specified, it will encode the node's text.
def encodeElements(allElements, attribute = None):
  for element in allElements:
    if attribute:
      try:
        element.set(attribute, urllib2.quote(element.attrib[attribute], '#'))
      except Exception, e:
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
    outputFile = open('{0}/{1}.kml'.format(outputDir, layerFilePrefix), 'w')
    outputFile.write(data)
    outputFile.close()
  except Exception, e:
    print e
    return False

  return True

# Process COP layers.
for layerName, url in copLayers.iteritems():
  print '--- Processing first-level layer "{0}"'.format(layerName)
  processLayer(layerName, url)
  print ''
