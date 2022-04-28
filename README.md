# CrossroadsDescriber

**CrossroadsDescriber** is a Python tool that produces automatic text description of data from OpenStreetMap.

This tool was developed and tested under Ubuntu 20.04.

## Dependencies

This tool depends on several Python libraries that can be installed with pip:

```bash
pip3 install -r requirements.txt
````

It also depends on a jsRealB server to generate text. You must install node, then execute the server :

```bash
sudo apt install nodejs
node jsrealb/jsRealB-serverfr.js
```

## How to use

Detailed optiions can be obtained by using :

```bash
./main.py -h
```

For basic usage, i.e getting the description of a crossroad, you can use the -c option with the coordinates of the crossroads you want to describe :

```bash
./main.py -c 45.77351 3.09015
```