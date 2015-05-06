#!/usr/bin/env python
import unkml
import logging

logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.DEBUG)
unkml.Config.outputDir = 'output'

layers = [
  unkml.Layer('Sample KMZ', 'http://kml-samples.googlecode.com/svn/trunk/kml/time/time-stamp-point.kmz')
]

unkml.Config.processLayerList(layers)
