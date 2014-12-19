#!/usr/bin/env python
import unKML
import logging

logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.DEBUG)
unKML.outputDir = 'output'

layers = [
  unKML.Layer('Sample KMZ', 'http://kml-samples.googlecode.com/svn/trunk/kml/time/time-stamp-point.kmz')
]

unKML.processLayerList(layers)
