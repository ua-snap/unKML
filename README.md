unKML
=====

## Setup and installation

These instructions will install unKML and the components it needs locally, inside your home directory. This is to avoid impacting the system-wide installation of GDAL, if it exists, since unKML requires a custom build of GDAL with libkml support. 

 1. Install libcurl if it is not already installed

    ```bash
    sudo apt-get install libcurl4-openssl-dev
    ```

 1. Install virtualenv if it is not already installed

    ```bash
    sudo pip install virtualenv
    ```

 1. Create an unKML virtual environment

    ```bash
    virtualenv ~/env/unKML
    ```

 1. Download, build, and install libkml source

    ```bash
    git clone https://github.com/google/libkml.git
    cd libkml
    ./autogen.sh
    ./configure --prefix=$HOME/env/unKML
    make
    make install
    cd ..
    ```

 1. Download, build, and install GDAL from source with libkml support

    ```bash
    wget 'http://download.osgeo.org/gdal/1.11.1/gdal-1.11.1.tar.gz'
    tar -zxvf gdal-1.11.1.tar.gz
    cd gdal-1.11.1
    ./configure --prefix=$HOME/env/unKML --with-libkml=$HOME/env/unKML
    make
    make install
    cd ..
    ```

 1. Add the following line to the bottom of ~/.profile

    ```bash
    export LD_LIBRARY_PATH=$HOME/env/unKML/lib
    ```

    And run this command to make sure the change is in effect:

    ```bash
    source ~/.profile
    ```

 1. Activate the unKML virtual environment

    ```bash
    source ~/env/unKML/bin/activate
    ```

 1. Install required Python modules

    ```bash
    pip install python-magic lxml
    ```

 1. Download unKML

    ```bash
    git clone https://github.com/ua-snap/unKML.git
    ```

## Usage

 1. Activate the unKML virtual environment

    ```bash
    source ~/env/unKML/bin/activate
    ```
