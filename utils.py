import glob
import json
import math
from os import path
from datetime import datetime
import itertools
import networkx as nx

# Read OSMnx cache and return start node and end node of a way if it exists
def getOriginalEdgeDirection(way_id, edge):
    paths = glob.glob("cache/*.json")
    timestamps = [datetime.fromtimestamp(path.getctime(json_file)) for json_file in paths]
    json_file = open(paths[min(range(len(timestamps)), key=timestamps.__getitem__)])
    data = json.load(json_file)
    json_file.close()
    for el in data["elements"]:
        if el["type"] == "way" and el["id"] == way_id:
            for node in el["nodes"]:
                if node == edge[0]:
                    return edge
                if node == edge[1]:
                    return [edge[1], edge[0]]
    return -1

# Compute  azimuth between two points
# Source : https://developpaper.com/example-of-python-calculating-azimuth-angle-based-on-the-coordinates-of-two-points/
def azimuthAngle( x1, y1, x2, y2):
    angle = 0.0
    dx = x2 - x1
    dy = y2 - y1
    if x2 == x1:
        angle = math.pi / 2.0
        if y2 == y1 :
            angle = 0.0
        elif y2 < y1 :
            angle = 3.0 * math.pi / 2.0
    elif x2 > x1 and y2 > y1:
        angle = math.atan(dx / dy)
    elif x2 > x1 and y2 < y1 :
        angle = math.pi / 2 + math.atan(-dy / dx)
    elif x2 < x1 and y2 < y1 :
        angle = math.pi + math.atan(dx / dy)
    elif x2 < x1 and y2 > y1 :
        angle = 3.0 * math.pi / 2.0 + math.atan(dy / -dx)
    return (angle * 180 / math.pi)

# Compute mean coordinates of a list of nodes
# Params :
#   G : osmnx graph
#   nodes : list of nodes ids
def meanCoordinates(G, nodes):
    crossroad_center = {"x":0, "y":0}
    for node_id in nodes:
        crossroad_center["x"] += G.nodes[node_id]["x"]
        crossroad_center["y"] += G.nodes[node_id]["y"]
    crossroad_center["x"] /= len(nodes)
    crossroad_center["y"] /= len(nodes)
    return crossroad_center

# Compute mean angle (azimuth) of a branch (represented by its border nodes) from the center of the crossroad
def meanAngle(G, border_nodes, crossroad_center):
    mean_angle = 0
    for border_node in border_nodes:
        border_node = G.nodes[border_node]
        angle = azimuthAngle(crossroad_center["x"], crossroad_center["y"], border_node["x"], border_node["y"])
        # if angle is near to 0°, revert it to -X° to enable mean angle calculation
        if angle > 315 :
            angle -= 360
        mean_angle += angle
    mean_angle /= len(border_nodes)
    return mean_angle

def outputJSON(filename, junctions, branches, general_desc, branches_desc, crossings_desc):
    data = {}
    
    data["introduction"] = general_desc
    
    data["branches"] = []
    for (branch, branch_desc, crossing_desc) in zip(branches, branches_desc, crossings_desc):
        crossing_desc = crossing_desc.split(" ")[4:]
        crossing_desc.insert(0, "Elle")
        nodes = []
        for way in branch.ways:
            nodes.append([junction.id for junction in way.junctions])
        data["branches"].append({
            "nodes" : nodes,
            "text" : branch_desc + " " + " ".join(crossing_desc)
        })
    
    crosswalks = []
    for junction in junctions.values():
        if "Crosswalk" in junction.type:
            crosswalks.append(junction)

    data["crossings"] = []
    for crosswalk in crosswalks:
        crosswalk_desc = "Le passage piéton "

        if "Pedestrian_traffic_light" in crosswalk.type:
            crosswalk_desc += "est protégé par un feu"
            if crosswalk.ptl_sound == "yes":
                crosswalk_desc += " sonore. "
            else :
                crosswalk_desc += ". "
        else:
            crosswalk_desc += "n'est pas protégé par un feu. "

        if crosswalk.cw_tactile_paving == "yes":
            crosswalk_desc += "Il y a des bandes d'éveil de vigilance."
        elif crosswalk.cw_tactile_paving == "incorrect":
            crosswalk_desc += "Il manque des bandes d'éveil de vigilance ou celles-ci sont dégradées."
        else:
            crosswalk_desc += "Il n'y a pas de bandes d'éveil de vigilance."

        data["crossings"].append({
            "node" : crosswalk.id,
            "text" : crosswalk_desc
        })

    with open(filename, 'w') as outfile:
        json.dump(data, outfile, ensure_ascii=False)

# Detect islands by closing branches with multiple ways, then by detecting faces
def getIslands(G, branches, crossroad_border_nodes):
    tG = nx.Graph(G)

    for i, branch in enumerate(branches): 
        border_nodes = []
        for j, way in enumerate(branch.ways):
            for junction in way.junctions:
                if junction.id not in crossroad_border_nodes.keys():
                    border_nodes.append(junction)    
        # Create faces for islands not closed in the graph (border islands)
        for j in range(len(border_nodes)-1):
            tG.add_edge(border_nodes[j].id, border_nodes[j+1].id)

    return [face for face in nx.cycle_basis(tG)]

# Translate words
def tr(word):
    if word == "Road":
        return "circulation"
    if word == "Bus":
        return "bus"