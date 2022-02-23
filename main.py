#!/usr/bin/env python3

import shutil
import argparse
import osmnx as ox
import lib.crseg.segmentation as cs
import crdesc.description as cd
import crdesc.config as config

#
# Configuration
#

# configure arg parser
parser = argparse.ArgumentParser(description="Build a basic description of the crossroad located at the requested coordinate.")
parser.add_argument('-c', '--by-coordinates', nargs=2, help='Load input from OSM using the given latitude', type=float)
parser.add_argument('-f', '--file', nargs=1, help='Load .osm file instead of using Overpass', type=str)
parser.add_argument('-nc', '--no-clear-cache', help='Do not clear cached datas', action='store_true')
parser.add_argument('-o', '--output', nargs=1, help='Output a JSON file.', type=str)
parser.add_argument('-or', '--output-roads', nargs=1, help='Output a GeoJSON file containing the roads with added semantics about sidewalks and islands.', type=str)
parser.add_argument('-op', '--output-pedestrian', nargs=1, help='Output a GeoJSON file containing the derived pedestrian graph.', type=str)
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
else:
    latitude = 45.77351
    longitude = 3.09015

#
# OSM data download
#

# OSMnx configuration
ox.config(use_cache=True, useful_tags_way = list(set(ox.settings.useful_tags_way + config.way_tags_to_keep)), useful_tags_node = list(set(ox.settings.useful_tags_node + config.node_tags_to_keep)))

xmlfile = None
if args.file :
    if args.by_coordinates:
        xmlfile = args.file[0]
        G = ox.graph_from_xml(args.file[0], simplify=False)
    else :
        print("You need to give the coordinate of the main crossroad to proceed.")
        exit
else :
    G = ox.graph_from_point((latitude, longitude), dist=150, network_type="all", retain_all=False, truncate_by_edge=True, simplify=False)

# graph segmentation (from https://gitlab.limos.fr/jmafavre/crossroads-segmentation/-/blob/master/src/get-crossroad-description.py)

connection_intensity = 5
max_cycle_elements = 10

# remove sidewalks, cycleways
G = cs.Segmentation.remove_footways_and_parkings(G, False)
# build an undirected version of the graph
G = ox.utils_graph.get_undirected(G)
# segment it using topology and semantic
seg = cs.Segmentation(G, connection_intensity = connection_intensity, max_cycle_elements = max_cycle_elements)
seg.process()
seg.to_json("data/intersection.json", longitude, latitude)

desc = cd.Description()
desc.computeModel(G, "data/intersection.json", xmlfile)
description = desc.generateDescription("http://localhost:8081")

print(description["text"])
output = open("output/description.txt", "w")
output.write(description["text"])
output.close()

# json output
if args.output:
    with open("output/"+args.output[0], "w") as f:
        f.write(desc.descriptionToJSON(description["structure"]))
        f.close()

# geojson output
if args.output_roads:
    with open("output/"+args.output_roads[0], "w") as f:
        f.write(desc.getSidewalksAndIslands())
        f.close()

if args.output_pedestrian:
    with open("output/"+args.output_pedestrian[0], "w") as f:
        f.write(desc.getCrossings())
        f.close()


# display crossroad and save image
cr = seg.get_crossroad(longitude, latitude)
ec = seg.get_regions_colors_from_crossroad(cr)
nc = seg.get_nodes_regions_colors_from_crossroad(cr)
ox.plot.plot_graph(G, edge_color=ec, node_color=nc, save=True, filepath="output/crossroad.png")