#!/usr/bin/python
import ACELayer
import logging

logging.basicConfig(format = '%(levelname)s: %(message)s', level = logging.INFO)
ACELayer.outputDir = 'output'

layers = [
  ACELayer.Layer('COP', 'http://www.dot.alaska.gov/stwdplng/mapping/transdata/GE_Files/Alaska_Mileposts.kml')
]

ACELayer.Layer.processLayerList(layers)
