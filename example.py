#!/usr/bin/env python
import unKML
import logging

logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.DEBUG)
unKML.outputDir = 'output'

layers = [
  unKML.Layer('COP', 'http://weather.msfc.nasa.gov/ACE/latestALCOMCOP.kml')
]

unKML.Layer.processLayerList(layers)
