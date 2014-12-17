unKML
=====

## Setup and installation

These instructions have been tested on Ubuntu 12.04 LTS. They will install unKML and the components it needs locally, inside your home directory. This is to avoid impacting the system-wide installation of GDAL, if it exists, since unKML requires a custom build of GDAL with libkml support. 

 1. Install libcurl if it is not already installed:

    ```bash
    sudo apt-get install libcurl4-openssl-dev
    ```

 1. Install virtualenv and virtualenvwrapper if they are not already installed:

    ```bash
    sudo pip install virtualenv virtualenvwrapper
    ```

 1. Add the following lines to ```~/.bash_profile``` to complete the virtualenvwrapper installation:

    ```bash
    export WORKON_HOME=$HOME/.virtualenvs
    export PROJECT_HOME=$HOME/Devel
    source /usr/local/bin/virtualenvwrapper.sh
    ```

    And make sure these changes are in effect with:

    ```bash
    source ~/.bash_profile
    ```

 1. Create an unKML virtual environment:

    ```bash
    mkvirtualenv unKML
    ```

 1. Add a local dynamic library path to the unKML virtual environment by adding the following line to the ```~/.virtualenvs/unKML/bin/postactivate``` file:
    
    ```bash
    export LD_LIBRARY_PATH=$HOME/.virtualenvs/unKML/lib
    ```

    And the following line to ```~/.virtualenvs/unKML/bin/predeactivate```:

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
    wget 'http://download.osgeo.org/gdal/1.11.1/gdal-1.11.1.tar.gz'
    tar -zxvf gdal-1.11.1.tar.gz
    cd gdal-1.11.1
    ./configure --prefix=$HOME/.virtualenvs/unKML --with-libkml=$HOME/.virtualenvs/unKML
    make
    make install
    cd ..
    ```

 1. Activate the unKML virtual environment:

    ```bash
    workon unKML
    ```

 1. Install required Python modules:

    ```bash
    pip install python-magic lxml
    ```

 1. Download unKML:

    ```bash
    git clone https://github.com/ua-snap/unKML.git
    ```

## Usage

 1. Activate the unKML virtual environment:

    ```bash
    source ~/env/unKML/bin/activate
    ```

 1. Copy or modify the included ```example.py``` to get started, adding one or more layers to download and convert. unKML will also attempt to recursively download and convert all sublayers included in the provided layers.
