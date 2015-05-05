from setuptools import setup

setup(name='unKML',
      version='0.1',
      description='Uses extraction, conversion, and recursion to turn KML into shapefiles and GeoTIFFs.',
      url='https://github.com/ua-snap/unKML',
      author='Craig Stephenson',
      author_email='crstephenson@alaska.edu',
      license='MIT',
      packages=['unKML'],
      install_requires=[
          'python-magic',
          'lxml'
      ],
      zip_safe=False)
