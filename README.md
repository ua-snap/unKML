unKML
=====

## Setup and installation

These instructions will install unKML and all of the components it needs locally, inside your home directory. This is to avoid impacting the system-wide installation of GDAL, if it exists, since unKML requires a custom build of GDAL with libkml support.

 1. Install virtualenv, if it is not already installed

    ```bash
    sudo pip install virtualenv
    ```

 1. Create an unkml virtual environment

    ```bash
    virtualenv unkml
    ```

 1. Activate the unkml virtual environment

    ```bash
    source unkml/bin/activate
    ```

 1. Install required Python modules

    ```bash
    pip install python-magic
    ```

 1. Download, build, and install libkml source

    ```bash
    git clone https://github.com/google/libkml.git
    cd libkml
    ./autogen.sh
    ./configure --prefix=$HOME/unkml
    make
    make install
    cd ..
    ```

 1. Download, build, and install GDAL from source with libkml support

    ```bash
    wget 'http://download.osgeo.org/gdal/1.11.1/gdal-1.11.1.tar.gz'
    tar zxvf gdal-1.11.1.tar.gz
    cd gdal-1.11.1
    ./configure --prefix=$HOME/unkml --with-libkml=$HOME/unkml
    make
    make install
    cd ..
    ```

 1. Add the following line to the bottom of ~/.profile

    ```bash
    export LD_LIBRARY_PATH=$HOME/unkml/lib
    ```

    And run this command to make sure the change is in effect:

    ```bash
    source ~/.profile
    ```

 1. Download unKML

    ```bash
    git clone https://github.com/ua-snap/unKML.git
    ```

## Usage

 1. Activate the unkml virtual environment

    ```bash
    source unkml/bin/activate
    ```
