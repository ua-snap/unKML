#!/usr/bin/python
import os
import urllib2
import lxml.etree

kmlLayers = {
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
  'AK Railroad Mileposts': 'https://ace.arsc.edu/system/files/arrc_database.MPL__0.kml'
}

kmzLayers = {
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

# Pass this function a list of ElementTree elements that need encoding. If an
# attribute parameter is specified, it will encode that attribute's value. If
# no attribute parameter is specified, it will encode the node's text.
def filterElements(allElements, attribute = None):
  if allElements:
    for element in allElements:
      if attribute:
        try:
          element.set(attribute, urllib2.quote(element.attrib[attribute], '#'))
        except:
          print 'Element is missing {0} attribute.'.format(attribute)
      else:
        element.text = urllib2.quote(element.text, '#')
    return True
  return False

for layer, url in kmlLayers.iteritems():
  # Download KML layer from URL.
  response = urllib2.urlopen(url)
  layerData = response.read()

  # Parse layer as XML and set as ElementTree root node.
  etreeElement = lxml.etree.XML(layerData)
  tree = lxml.etree.ElementTree(etreeElement)

  # Layers with no Placemark nodes have nothing to give GeoNode.
  if not tree.xpath('.//*[local-name() = "Placemark"]'):
    print 'Skipping {0} layer because it has no features.'.format(layer)
    continue

  # Encode invalid characters.
  filterElements(tree.xpath('.//*[local-name() = "styleUrl"]'))
  filterElements(tree.xpath('.//*[local-name() = "Style" and @id]'), 'id')

  # Make sure we have an output directory.
  outputDir = 'output'
  if not os.path.exists(outputDir):
    os.mkdir(outputDir)

  # Write modified KML file using original file name.
  layerBasename = url.rsplit('/', 1).pop()
  outputFile = open('{0}/{1}'.format(outputDir, layerBasename), 'w')
  tree.write(outputFile)
  outputFile.close()
