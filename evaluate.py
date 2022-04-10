#!/usr/bin/env python3

from audioop import cross
import shutil
import argparse
import json
import random
from copy import deepcopy
import osmnx as ox
import crseg.segmentation as cs
import crdesc.description as cd
from crdesc.model import Junction
import crdesc.utils
import crdesc.config as config

#
# Configuration
#

# configure arg parser
parser = argparse.ArgumentParser(description="Create an evaluation file for the crossroads descriptions provided by crdesc.")
parser.add_argument('-c', '--by-coordinates', nargs=2, help='Load input from OSM using the given latitude', type=float)
parser.add_argument('-f', '--file', nargs=1, help='Load .osm file instead of using Overpass', type=str)
parser.add_argument('-r', '--radius', nargs=1, help='Give a radius to load the data from.', type=float)
parser.add_argument('-n', '--number', nargs=1, help='Set the number of crossroads to evaluate.', type=int)
parser.add_argument('-nc', '--no-clear-cache', help='Do not clear cached datas', action='store_true')
parser.add_argument('-o', '--output', nargs='*', help='Output the JSON evaluation file.', type=str)
args = parser.parse_args()

# create / clean basic folder structure
folders = ["data", "output"]
if not args.no_clear_cache:
    folders.append("cache")
for dir in  folders : shutil.rmtree(dir, ignore_errors=True), shutil.os.mkdir(dir) 

# use coordinates in parameters if presents, else use the coordinates of this intersection : https://www.openstreetmap.org/#map=19/45.77351/3.09015
if args.by_coordinates:
    latitude = args.by_coordinates[0]
    longitude = args.by_coordinates[1]
    if args.radius:
        radius = args.radius[0]
    else:
        radius = 1000
else:
    latitude = 45.77351
    longitude = 3.09015
    radius = 1000

#
# OSM data download
#

# OSMnx configuration
ox.config(use_cache=True, useful_tags_way = list(set(ox.settings.useful_tags_way + config.way_tags_to_keep)), useful_tags_node = list(set(ox.settings.useful_tags_node + config.node_tags_to_keep)))

xmlfile = None
if args.file :
    xmlfile = args.file[0]
    G = ox.graph_from_xml(args.file[0], simplify=False)
else :
    G = ox.graph_from_point((latitude, longitude), dist=radius, network_type="all", retain_all=False, truncate_by_edge=True, simplify=False)

if not args.output :
    print("You must give an output filename.")
    exit()

if not args.output :
    print("You must give a number of crossroads.")
    exit()

# graph segmentation (from https://gitlab.limos.fr/jmafavre/crossroads-segmentation/-/blob/master/src/get-crossroad-description.py)

# remove sidewalks, cycleways, service ways
G = cs.Segmentation.remove_footways_and_parkings(G, False)
G = crdesc.utils.remove_service_ways(G)
# build an undirected version of the graph
G = ox.utils_graph.get_undirected(G)
# segment it using topology and semantic
seg = cs.Segmentation(G, C0 = 2, C1 = 2, C2 = 4, max_cycle_elements = 10)
seg.process()
seg.to_json_all("data/intersection.json", False)

# generate evaluation file
with open("data/intersection.json") as json_file:

    crossroads = json.load(json_file)

    n = args.number[0]
    if n > len(crossroads):
        print("Warning : number of available crossroads inferior to the number of wanted crossroads.")
        n = len(crossroads)

    crossroads_numbers = random.sample(range(len(crossroads)),n)

    evaluated = []

    i = 1
    for number, crossroad in enumerate(crossroads):

        if number in crossroads_numbers:
            # generate single crossroad json file
            with open("data/evaluated.json", "w") as evaluated_crossroad:
                json.dump([crossroad], evaluated_crossroad)
                evaluated_crossroad.close()

            # then generate the description
            try:
                crdesc.model._junctions.clear()
                desc = cd.Description()
                desc.computeModel(deepcopy(G), "data/evaluated.json", None)
                description = desc.generateDescription("http://localhost:8081")
                crossroad[0]["description"] = description["text"]
            except:
                crossroad[0]["description"] = "error"
            
            evaluated.append(crossroad)

            print("Crossroads %s / %s"%(i,n))
            i += 1
                    
    # generate single crossroad json file
    with open("data/%s"%args.output[0], "w") as evaluation_file:
        json.dump(evaluated, evaluation_file)
        evaluation_file.close()
