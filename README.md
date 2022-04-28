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

### Obtaining an intersection description

For basic usage, i.e getting the description of a crossroad, you can use the -c option with the coordinates of the crossroads you want to describe :

```bash
./main.py -c 45.77351 3.09015
```

### Visualize generated items

The description generation relies on the generation of sidewalks and islands in the intersection. You can visualize the result of this generation by :

* outputting a geojson :
```
./main.py -c 45.77351 3.09015 -o output.geojson
```

* opening this geojson in QGIS

* import the two model3 from the qgis folder in Processing

* execute each of the model on the line layer of the geojson with the corresponding qml style file (also in the qgis folder)

### Generate an evaluation file

Previous commands generate the description of one intersection. To evaluate the quality of the generated descriptions, you can generate several descriptions at one by using evaluate.py. -r option corresponds to the radius around the coordinates used to download the data. -n indicates the number of intersections to output, randomly fetched among the intersections in the dataset.

```
./evaluate.py -c 45.77351 3.09015 -r 1000 -n 40 -o evaluation.json
```
