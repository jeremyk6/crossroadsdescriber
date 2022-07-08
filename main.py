#!/usr/bin/env python3

import shutil
import argparse
import tempfile
import osmnx as ox
import crseg.utils as u
import crseg.segmentation as cs
import crdesc.description as cd
import crdesc.config as cg

#
# Configuration
#

# configure arg parser
parser = argparse.ArgumentParser(description="Build a basic description of the crossroad located at the requested coordinate.")
parser.add_argument('-c', '--by-coordinates', nargs=2, help='Load input from OSM using the given latitude', type=float)
parser.add_argument('-f', '--file', nargs=1, help='Load .osm file instead of downloading data', type=str)
parser.add_argument('--overpass', help='Use Overpass to download data instead of the OSM api', action='store_true')
parser.add_argument('-k', '--keep-cache', help='Do not clear cached datas', action='store_true')
parser.add_argument('-o', '--output', nargs='*', help='Output files containing the description in text, JSON or GeoJSON format (according to the extension of the file).', type=str)
args = parser.parse_args()

# create / clean basic folder structure
folders = ["data", "output"]
if not args.keep_cache:
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
ox.settings.useful_tags_way = ox.settings.useful_tags_way + cg.way_tags_to_keep
ox.settings.useful_tags_node = ox.settings.useful_tags_way + cg.node_tags_to_keep

xmlfile = None
if args.file :
    if args.by_coordinates:
        xmlfile = args.file[0]
        G = ox.graph_from_xml(args.file[0], simplify=False)
    else :
        print("You need to give the coordinate of the main crossroad to proceed.")
        exit
else:
    G = u.Util.get_osm_data(latitude, longitude, 150, args.overpass, cg.way_tags_to_keep, cg.node_tags_to_keep, tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=".xml", dir="cache"))

# graph segmentation (from https://gitlab.limos.fr/jmafavre/crossroads-segmentation/-/blob/master/src/get-crossroad-description.py)

# prepae network by removing unwanted ways
G = cs.Segmentation.prepare_network(G)
# build an undirected version of the graph
undirected_G = ox.utils_graph.get_undirected(G)
# segment it using topology and semantic
seg = cs.Segmentation(undirected_G, C0 = 2, C1 = 2, C2 = 4, max_cycle_elements = 10)
seg.process()
seg.to_json("data/intersection.json", longitude, latitude)

desc = cd.Description()
desc.computeModel(G, "data/intersection.json")
description = desc.generateDescription()

print(description["text"])

# File output
if args.output:
    filename = args.output[0]
    extension = filename.split('.')[-1].lower()
    with open("output/"+args.output[0], "w") as f:
        content = description["text"]
        if extension == "geojson":
            content = desc.getGeoJSON(description["structure"])
        if extension == "json":
            content = desc.descriptionToJSON(description["structure"])
        f.write(content)
        f.close()

# display crossroad and save image
for edge, color in seg.get_regions_colors_from_crossroad(seg.get_crossroad(longitude, latitude)).items():
    if color == (0.5, 0.5, 0.5, 0.1): undirected_G.remove_edge(edge[0], edge[1])
cr = seg.get_crossroad(longitude, latitude)
ec = seg.get_regions_colors_from_crossroad(cr)
nc = seg.get_nodes_regions_colors_from_crossroad(cr)
ox.plot.plot_graph(undirected_G, edge_color=ec, node_color=nc, save=True, filepath="output/crossroad.png")