unKML
=====

unKML is a Python module that recursively downloads and parses KML and KMZ files, attempting to convert each vector and raster layer it finds into either a shapefile or GeoTIFF using GDAL. Follow the setup and usage instructions below to get started.

## Setup

**It is highly recommended to use a custom build of GDAL with support for Google's official libkml module. unKML can technically run without libkml support by using GDAL's built-in KML driver, but using libkml vastly increases the number of files it can convert successfully.**

These instructions have been tested on Ubuntu 12.04 LTS. They will install unKML and the components it needs inside your home directory as a virtual environment. This is to avoid impacting the system-wide installation of GDAL, if one exists, since unKML requires a custom build of GDAL with libkml support. You will also be able to switch between using your custom GDAL and the system GDAL by activating or deactivating the unKML virtual environment, respectively.

 1. Install needed system packages:

    ```bash
    sudo apt-get install libcurl4-openssl-dev python-pip autoconf libtool \
    libexpat1-dev build-essential python-dev libxml2-dev libxslt1-dev
    ```

 1. Install virtualenv and virtualenvwrapper if they are not already installed:

    ```bash
    sudo pip install virtualenv virtualenvwrapper
    ```

 1. Add the following lines to ```~/.bashrc``` to complete the virtualenvwrapper installation:

    ```bash
    export WORKON_HOME=$HOME/.virtualenvs
    export PROJECT_HOME=$HOME/Devel
    source /usr/local/bin/virtualenvwrapper.sh
    ```

    And make sure these changes are in effect by running:

    ```bash
    source ~/.bashrc
    ```

 1. Create an unKML virtual environment, then deactivate it for now so we can modify it and reactivate it later:

    ```bash
    mkvirtualenv unKML
    deactivate
    ```

 1. Add a local dynamic library path to the unKML virtual environment by adding the following line to ```~/.virtualenvs/unKML/bin/postactivate```:
    
    ```bash
    export LD_LIBRARY_PATH=$HOME/.virtualenvs/unKML/lib
    ```

    And adding the following line to ```~/.virtualenvs/unKML/bin/predeactivate```:

    ```bash
    unset LD_LIBRARY_PATH
    ```

 1. Download, build, and install libkml from source:

    ```bash
    git clone https://github.com/google/libkml.git
    cd libkml
    ./autogen.sh
    ./configure --prefix=$HOME/.virtualenvs/unKML
    make
    make install
    cd ..
    ```

 1. Download, build, and install GDAL from source with libkml support:

    ```bash
    wget 'http://download.osgeo.org/gdal/1.11.2/gdal-1.11.2.tar.gz'
    tar -zxvf gdal-1.11.2.tar.gz
    cd gdal-1.11.2
    ./configure --prefix=$HOME/.virtualenvs/unKML --with-libkml=$HOME/.virtualenvs/unKML
    make
    make install
    cd ..
    ```

 1. Remove libkml and GDAL source files:

    ```bash
    rm -fr libkml gdal-1.11.2.tar.gz gdal-1.11.2
    ```

 1. Activate the unKML virtual environment:

    ```bash
    workon unKML
    ```

 1. Install unKML from this GitHub repository:

    ```bash
    pip install -e git://github.com/ua-snap/unKML.git#egg=unKML
    ```

## Usage

 1. Activate the unKML virtual environment:

    ```bash
    workon unKML
    ```

 1. Copy or modify the included ```example.py``` to get started, adding one or more layers to download and convert. unKML will also attempt to recursively download and convert all sublayers found in the provided layers.

    All converted files will be stored in a nested directory tree in whatever directory was specified as your `outputDir`. Since shapefiles are made up of several different files, each shapefile is stored as a single zip file.
