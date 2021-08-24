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

# Configure arg parser

parser = argparse.ArgumentParser(description="Build a basic description of the crossroad located at the requested coordinate.")
parser.add_argument('-c', '--by-coordinates', nargs=2, help='Load input from OSM using the given latitude', type=float)
args = parser.parse_args()

#
# OSMnx configuration
#

way_tags_to_keep = [
    # general informations,
    'name',
    'highway',
    'fooway',
    'oneway',
    'surface',
    # lanes informations
    'lanes',
    'lanes:backward',
    'lanes:forward',
    # turn informations
    'turn:lanes',
    'turn:lanes:backward',
    'turn:lanes:forward',
    #cycling informations
    'bicycle',
    'segregated',
    'cycleway',
    'cycleway:right',
    'cycleway:left',
    'cycleway:both',
    # sidewalk informations
    'sidewalk',
    'sidewalk:left',
    'sidewalk:right',
    'sidewalk:both',
    # public transportation informations,
    'bus',
    'psv',
    'psv:lanes:backward',
    'psv:lanes:forward'
]

node_tags_to_keep = [
    # general informations
    'highway',
    # crosswalk informations
    'crossing',
    'tactile_paving',
    # traffic signals informations
    'traffic_signals',
    'traffic_signals:direction',
    'traffic_signals:sound',
    'button_operated'
    #sidewalk informations
    'kerb',
    #island informations
    'crossing:island'
]

ox.config(use_cache=True, useful_tags_way = list(set(ox.settings.useful_tags_way + way_tags_to_keep)), useful_tags_node = list(set(ox.settings.useful_tags_node + node_tags_to_keep)))

#
# OSM data download
#

# clean cache folder
shutil.rmtree("cache")

if args.by_coordinates:
    latitude = args.by_coordinates[0]
    longitude = args.by_coordinates[1]
else:
    # Carrefour thèse 1
    latitude = 45.77351
    longitude = 3.09015

G = ox.graph_from_point((latitude, longitude), dist=150, network_type="all", retain_all=False, truncate_by_edge=True, simplify=False)

# Graph segmentation (from https://gitlab.limos.fr/jmafavre/crossroads-segmentation/-/blob/master/src/get-crossroad-description.py)

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

# Intersection center
# Computed by mean coordinates, may use convex hull + centroid later
crossroad_center = {"x":0, "y":0}
for node_id in seg_crossroad.border_nodes:
    crossroad_center["x"] += G.nodes[node_id]["x"]
    crossroad_center["y"] += G.nodes[node_id]["y"]
crossroad_center["x"] /= len(seg_crossroad.border_nodes)
crossroad_center["y"] /= len(seg_crossroad.border_nodes)

# Branch and ways creation
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

            # Junction decoration with tags
            if node_id in seg_crossroad.border_nodes:
                
                # Is it a crosswalk ?
                if "crossing" in node:
                    # Does it have a tactile paving ?
                    cw_tactile_paving = "no"
                    if "tactile_paving" in node:
                        cw_tactile_paving = node["tactile_paving"]
                    junction = Crosswalk(junction, cw_tactile_paving)
                    # Does it have a traffic light ?
                    if node["crossing"] == "traffic_signals":
                        ptl_sound = "no"
                        # Does it have sound ?
                        if "traffic_signals:sound" in node and node["traffic_signals:sound"] == "yes":
                            ptl_sound = "yes"
                        junction = Pedestrian_traffic_light(junction, ptl_sound)

                # Is it a traffic light ?
                if "traffic_signals" in node:
                    tl_direction = "forward"
                    if "traffic_signals:direction" in node:
                        tl_direction = node["traffic_signals:direction"]
                    junction = Traffic_light(junction, None, tl_direction)
                    
            junctions.append(junction)

        # Ways creation

        way = Way(edge["osmid"], edge["name"], junctions, channels = [])

        # Does it have directed lanes ?
        way_out = True if n2 in seg_crossroad.border_nodes else False
        if "lanes:backward" in edge and "lanes:forward" in edge:
            # does it have designated bus lanes ?
            if "psv:lanes:backward" in edge and "psv:lanes:forward" in edge:
                for lane in edge["psv:lanes:backward"].split("|"):
                    if lane == "designated":
                        way.channels.append(Bus(None, "in" if way_out else "out"))
                    else:
                        way.channels.append(Road(None, "in" if way_out else "out"))
                for lane in edge["psv:lanes:forward"].split("|"):
                    if lane == "designated":
                        way.channels.append(Bus(None, "in" if way_out else "in"))
                    else:
                        way.channels.append(Road(None, "in" if way_out else "in"))
            else:
                for i in range(int(edge["lanes:backward"])):
                    way.channels.append(Road(None, "in" if way_out else "out"))
                for i in range(int(edge["lanes:forward"])):
                    way.channels.append(Road(None, "out" if way_out else "in"))
        # Does it have lanes ?
        elif "lanes" in edge:
            for i in range(int(edge["lanes"])):
                if edge["highway"]=="service" and edge["psv"]=="yes":
                    way.channels.append(Bus(None, "out" if way_out else "in"))
                else:
                    way.channels.append(Road(None, "out" if way_out else "in"))
        else :
            way.channels.append(Road(None, "out" if way_out else "in"))

        # Does it have sidewalks (default : yes)
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

    # Compute mean angle by branch
    mean_angle = 0
    for border_node in border_nodes:
        border_node = G.nodes[border_node]
        angle = azimuthAngle(crossroad_center["x"], crossroad_center["y"], border_node["x"], border_node["y"])
        # if angle is near to 0°, revert it to -X° to enable mean angle calculation
        if angle > 315 :
            angle -= 360
        mean_angle += angle
    mean_angle /= len(border_nodes)

    branches.append(Branch(id, mean_angle, None, ways[0].name, ways))

    id += 1

# Order branch by angle
branches.sort(key=lambda b: b.angle)

# Give name to branches
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
    
# Create crossroad
crossroad = Intersection(None, branches)

#
# Text generation
#
# Need a jsRealB server

# General description

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

# Branches description

branches_desc = []
for branch in crossroad.branches:

    direction = PP(
        P("de"), 
        NP(
            D("le"), 
            N(branch.direction[0]), 
            Q(branch.direction[1]) if len(branch.direction) > 1 else Q("")
        )
    )

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

    # Count number of channels per type
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

    branch_desc = "La branche en direction %s qui s'appelle %s est composée %s : %s%s%s."%(jsRealB(direction), name, jsRealB(n_voies), channels_out_desc, ", et " if channels_in_desc and channels_out_desc else "", channels_in_desc)

    # Post process to remove ':' and duplicate information if there's only one type of way in one direction
    branch_desc = branch_desc.split(" ")
    if "et" not in branch_desc:
        i = branch_desc.index(":")
        branch_desc.pop(i-2)
        branch_desc.pop(i-2)
        branch_desc.pop(i-2)
    branch_desc = " ".join(branch_desc)
    
    branches_desc.append(branch_desc)

# Traffic light cycle
# Right turn on red are barely modelized in OSM, see https://wiki.openstreetmap.org/w/index.php?title=Red_turn&oldid=2182526
#TODO

# Attention points
# TODO

# Crossings descriptions
crossings_desc = []

for branch in crossroad.branches:

    name = " ".join(branch.street_name)
    crosswalks = []

    for way in branch.ways:
        
        for junction in way.junctions:
            if "Crosswalk" in junction.type:
                crosswalks.append(junction)

    if len(crosswalks):
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
        # Add bikeboxes sentence in outgoing lanes if any

        # TODO
        # Add, for islands, if difficult movements need to be made
        
    crossings_desc.append("La branche %s %s. %s"%(name, "se traverse en %s fois"%jsRealB(n_crosswalks) if len(crosswalks) else "ne se traverse pas", crossing_desc))

# Print description

description = ""
description += general_desc+"\n\n"

description += "== Description des branches ==\n\n"

for branch_desc in branches_desc:
    description += branch_desc+"\n\n"

description += "== Description des traversées ==\n\n"

for crossing_desc in crossings_desc:
    description += crossing_desc+"\n\n"

print("\n"+description)

# Description output
output = open("output/description.txt", "w")
output.write(description)
output.close()

# Display crossroad and save image
cr = seg.get_crossroad(longitude, latitude)
ec = seg.get_regions_colors_from_crossroad(cr)
nc = seg.get_nodes_regions_colors_from_crossroad(cr)
ox.plot.plot_graph(G, edge_color=ec, node_color=nc, save=True, filepath="output/crossroad.png")