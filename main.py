#!/usr/bin/env python3

import shutil
import os
import argparse
from warnings import catch_warnings
from networkx.algorithms.distance_measures import center
from model import *
from segmentationReader import *
from utils import *
from toolz import unique
from lib.jsRealBclass import N,A,Pro,D,Adv,V,C,P,DT,NO,Q,  NP,AP,AdvP,VP,CP,PP,S,SP,  Constituent, Terminal, Phrase, jsRealB
import lib.crseg.segmentation as cs
import osmnx as ox
from config import *

#
# Configuration
#

# create / clean basic folder structure
for dir in ["cache", "data", "output"] : shutil.rmtree(dir, ignore_errors=True), os.mkdir(dir)

# configure arg parser
parser = argparse.ArgumentParser(description="Build a basic description of the crossroad located at the requested coordinate.")
parser.add_argument('-c', '--by-coordinates', nargs=2, help='Load input from OSM using the given latitude', type=float)
args = parser.parse_args()

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
ox.config(use_cache=True, useful_tags_way = list(set(ox.settings.useful_tags_way + way_tags_to_keep)), useful_tags_node = list(set(ox.settings.useful_tags_node + node_tags_to_keep)))

G = ox.graph_from_point((latitude, longitude), dist=150, network_type="all", retain_all=False, truncate_by_edge=True, simplify=False)

# graph segmentation (from https://gitlab.limos.fr/jmafavre/crossroads-segmentation/-/blob/master/src/get-crossroad-description.py)

# remove sidewalks, cycleways
G = cs.Segmentation.remove_footways_and_parkings(G, False)
# build an undirected version of the graph
G = ox.utils_graph.get_undirected(G)
# segment it using topology and semantic
seg = cs.Segmentation(G)
seg.process()
seg.to_json("data/intersection.json", longitude, latitude)

# clear console
os.system("clear")

#
# Model completion
#

seg_crossroad = SegmentationReader("data/intersection.json").getCrossroads()[0]

# intersection center. Computed by mean coordinates, may use convex hull + centroid later
crossroad_center = meanCoordinates(G, seg_crossroad.border_nodes)

# branch and ways creation
id = 1
branches = []
for branch in seg_crossroad.branches:

    ways = []

    border_nodes = []

    for edge in branch.edges_by_nodes:

        n1 = edge[0]
        n2 = edge[1]

        # keep border nodes
        if n1 in seg_crossroad.border_nodes:
            border_nodes.append(n1)
        if n2 in seg_crossroad.border_nodes:
            border_nodes.append(n2)

        # try both order of the edge in case of oneway
        try:
            edge = G[n1][n2][0]
        except:
            n1,n2 = n2,n1
            edge = G[n1][n2][0]
        n1,n2 = getOriginalEdgeDirection(edge["osmid"], [n1,n2])
        
        # Note : access node attributes
        # ex. for x : G.nodes[n1].x
        # Junctions creation
        junctions = []
        for node_id, node in [ [n1,G.nodes[n1]] , [n2,G.nodes[n2]] ]:

            junction = Junction(node_id, node["x"], node["y"])

            # junction decoration with tags
            if node_id in seg_crossroad.border_nodes:
                
                # is it a crosswalk ?
                if "crossing" in node:
                    junction = createCrosswalk(junction, node)

                # is it a traffic light ?
                if "traffic_signals" in node:
                    junction = createTrafficSignal(junction, node)
                    
            junctions.append(junction)

        # ways creation
        way = Way(edge["osmid"], edge["name"], junctions, channels = [])

        # if n2 is a border node, it means the way is drawn as outgoing from the direction.
        way_out = True if n2 in seg_crossroad.border_nodes else False

        # does it have directed lanes ?
        if "lanes:backward" in edge and "lanes:forward" in edge:
            createDirectedLanes(edge, way, way_out)
        # does it have lanes ?
        elif "lanes" in edge:
            createUndirectedLanes(edge, way, way_out)
        else :
            if "oneway" in edge and edge["oneway"] == "no":
                createLane("Road", way, way_out)
                createLane("Road", way, not way_out)
            else:
                createLane("Road", way, way_out)

        # does it have sidewalks (default : yes)
        # bug in lanes with sidewalks, to solve later
        '''
        if "sidewalk" in edge:
            if edge["sidewalk"] == "yes":
                way.channels.insert(0, Sidewalk(None, None))
                way.channels.append(Sidewalk(None, None))
        else:
                way.channels.insert(0, Sidewalk(None, None))
                way.channels.append(Sidewalk(None, None))
        '''

        ways.append(way)

    # compute mean angle by branch
    mean_angle = meanAngle(G, border_nodes, crossroad_center)

    branches.append(Branch(id, mean_angle, None, ways[0].name, ways))

    id += 1

# order branch by angle
branches.sort(key=lambda b: b.angle)

# give name to branches
# direction : unused for now
"""
print("This crossroad has %s branches. Name them according to their clock order, starting from 12': "%len(branches))
for branch in branches:
    print("For the branch named %s at %s':"%(branch.street_name, branch.angle))
    direction = input()
    # format direction for the text generation
    direction = direction.split(" ")
    branch.direction = [direction.pop(0).lower()," ".join(direction)]
    #format street name for the text generation
    street_name = branch.street_name.split(" ")
    branch.street_name = [street_name.pop(0).lower()," ".join(street_name)]
"""

# branch number : number branches according to their clockwise order
for i, branch in enumerate(branches): 
    branch.number = i+1
    #format street name for the text generation
    street_name = branch.street_name.split(" ")
    branch.street_name = [street_name.pop(0).lower()," ".join(street_name)]
    
# create crossroad
crossroad = Intersection(None, branches)

#
# Text generation
# ~~ Need a jsRealB server ~~
#
# General description
#

streets = map(list, unique(map(tuple, [branch.street_name for branch in crossroad.branches]))) # horrible syntax to remove duplicates
s = CP(C("et"))
for street in streets:
    s.add(
        PP(
            P("de"), 
            NP(
                D("le"), 
                N(street[0]), 
                Q(street[1])
            )
        )
    )
general_desc = "Le carrefour à l'intersection %s est un carrefour à %s branches."%(jsRealB(s), len(crossroad.branches))

#
# Branches description
#

branches_desc = []
for branch in crossroad.branches:

    # direction : unused for now
    """
    direction = PP(
        P("de"), 
        NP(
            D("le"), 
            N(branch.direction[0]), 
            Q(branch.direction[1]) if len(branch.direction) > 1 else Q("")
        )
    )
    """

    # branch number
    number = NO(branch.number).dOpt({"nat": True})

    name = " ".join(branch.street_name)
    
    # channels = branch.ways[0].channels
    channels = []
    for way in branch.ways:
        channels += way.channels
    for channel in channels:
        if channel.__class__.__name__ == "Sidewalk":
            channels.remove(channel)
    n_voies = PP(
        P("de"),
        NP(
            NO(len(channels)).dOpt({"nat": True}), 
            N("voie")
        )
    )

    channels_in_desc = CP(C("et"))
    channels_out_desc = CP(C("et"))

    # count number of channels per type
    channels_in = {}
    channels_out = {}
    for channel in channels:

        c = None
        if channel.direction == "in":
            c = channels_in
        else:
            c = channels_out

        type = channel.__class__.__name__
        if type not in c:
            c[type] = 0
        c[type] += 1

    n = None
    for type,n in channels_in.items():
        channels_in_desc.add(
            NP(
                NO(n).dOpt({"nat": True}),
                N("voie"),
                PP(
                    P("de"),
                    N(tr(type))
                )
            )
        )
    channels_in_desc = jsRealB(channels_in_desc)
    if channels_in:
        word = "entrante"
        
        if n > 1:
            word += "s"
        channels_in_desc += " %s"%word

    for type,n in channels_out.items():
        channels_out_desc.add(
            NP(
                NO(n).dOpt({"nat": True}),
                N("voie"),
                PP(
                    P("de"),
                    N(tr(type))
                )
            )
        )
    channels_out_desc = jsRealB(channels_out_desc)
    if channels_out:
        word = "sortante"
        if n > 1:
            word += "s"
        channels_out_desc += " %s"%word

    branch_desc = "La branche numéro %s qui s'appelle %s est composée %s : %s%s%s."%(jsRealB(number), name, jsRealB(n_voies), channels_out_desc, ", et " if channels_in_desc and channels_out_desc else "", channels_in_desc)

    # post process to remove ':' and duplicate information if there's only one type of way in one direction
    branch_desc = branch_desc.split(" ")
    if "et" not in branch_desc:
        i = branch_desc.index(":")
        branch_desc.pop(i-2)
        branch_desc.pop(i-2)
        branch_desc.pop(i-2)
    branch_desc = " ".join(branch_desc)
    
    branches_desc.append(branch_desc)

#
# Traffic light cycle
# right turn on red are barely modelized in OSM, see https://wiki.openstreetmap.org/w/index.php?title=Red_turn&oldid=2182526
#

#TODO

#
# Attention points
#

# TODO

#
# Crossings descriptions
#
crossings_desc = []

for branch in crossroad.branches:

    name = " ".join(branch.street_name)
    crosswalks = []

    for way in branch.ways:
        
        for junction in way.junctions:
            if "Crosswalk" in junction.type:
                crosswalks.append(junction)

    crossing_desc = ""
    if len(crosswalks):

        n_crosswalks = NP(NO(len(crosswalks)).dOpt({"nat": True})).g("f") # followed by "fois", which is f.
        n_podotactile = 0
        n_ptl = 0
        n_ptl_sound = 0
        incorrect = False
        for crosswalk in crosswalks:
            if crosswalk.cw_tactile_paving != "no":
                n_podotactile += 1
            if crosswalk.cw_tactile_paving == "incorrect":
                incorrect = True
            if "Pedestrian_traffic_light" in crosswalk.type:
                n_ptl += 1
                if crosswalk.ptl_sound == "yes":
                    n_ptl_sound += 1

        crossing_desc = "Les passages piétons "
        if n_ptl:
            if n_podotactile == len(crosswalks):
                crossing_desc += "sont tous protégés par un feu. "
            else :
                crossing_desc += "ne sont pas tous protégés par un feu. "
        else:
            crossing_desc += "ne sont pas protégés par des feux. "
            
        
        if n_podotactile:
            if n_podotactile == len(crosswalks) and incorrect == False:
                crossing_desc += "Il y a des bandes d'éveil de vigilance."
            else:
                crossing_desc += "Il manque des bandes d'éveil de vigilance ou celles-ci sont dégradées."
        else:
            crossing_desc += "Il n'y a pas de bandes d'éveil de vigilance."

    # TODO 
    # add bikeboxes sentence in outgoing lanes if any

    # TODO
    # add, for islands, if difficult movements need to be made
        
    crossings_desc.append("La branche %s %s. %s"%(name, "se traverse en %s fois"%jsRealB(n_crosswalks) if len(crosswalks) else "ne se traverse pas", crossing_desc))

#
# Print description
#

description = ""
description += general_desc+"\n\n"

description += "== Description des branches ==\n\n"

for branch_desc in branches_desc:
    description += branch_desc+"\n\n"

description += "== Description des traversées ==\n\n"

for crossing_desc in crossings_desc:
    description += crossing_desc+"\n\n"

print("\n"+description)

# description output
output = open("output/description.txt", "w")
output.write(description)
output.close()

# display crossroad and save image
cr = seg.get_crossroad(longitude, latitude)
ec = seg.get_regions_colors_from_crossroad(cr)
nc = seg.get_nodes_regions_colors_from_crossroad(cr)
ox.plot.plot_graph(G, edge_color=ec, node_color=nc, save=True, filepath="output/crossroad.png")