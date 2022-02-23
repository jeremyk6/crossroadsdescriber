import glob
import json
from xml.dom import minidom
import math
from os import path
from datetime import datetime
import itertools
import osmnx as ox
import networkx as nx
import time

# Read OSMnx cache and return start node and end node of a way if it exists
def getOriginalEdgeDirection(way_id, edge, xmlfile=None):
    if xmlfile:
        doc = minidom.parse(xmlfile)
        ways = doc.getElementsByTagName("way")
        for way in ways:
            if way.getAttribute("id") == str(way_id):
                nodes = way.getElementsByTagName("nd")
                for node in nodes:
                    node_id = node.getAttribute("ref")
                    if node_id == str(edge[0]):
                        return edge
                    if node_id == str(edge[1]):
                        return [edge[1], edge[0]]
        return -1
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


    faces = []
    for cycle in nx.minimum_cycle_basis(tG):
        ordered = []
        to_handle = cycle[0]
        while len(cycle) > 0:
            ordered.append(to_handle)
            cycle.remove(to_handle)
            neighbors = list(set(tG.neighbors(to_handle)).intersection(cycle))
            if len(neighbors) > 0:
                to_handle = neighbors[0]
        faces.append(ordered)

    return faces

# Detect sidewalks by computing shortest path 
def getSidewalks(G, branches, crossroad_border_nodes):

    def getLeftShortestPath(G, n1, n2):
        path = [n1, next(G.neighbors(n1))]
        while path[-1] != n2:
            neighbors = [neighbor for neighbor in G.neighbors(path[-1])]
            azimuth_by_node = [[next_node, azimuthAngle(G.nodes[path[-1]]["x"], G.nodes[path[-1]]["y"], G.nodes[next_node]["x"], G.nodes[next_node]["y"])] for next_node in neighbors]
            azimuth_by_node.sort(key=lambda x: x[1])
            next_node = azimuth_by_node[([el[0] for el in azimuth_by_node].index(path[-2]) + 1) % len(azimuth_by_node)][0]
            path.append(next_node)
            if path[-1] == n1: return None
        return path

    sidewalk_nodes = []
    for i, branch in enumerate(branches):
        
        # Keep border nodes of the branch
        border_nodes = []
        for j, way in enumerate(branch.ways):
            for junction in way.junctions:
                if junction.id not in crossroad_border_nodes.keys():
                    border_nodes.append(junction)

        # Filter to keep the most left and most right nodes (branch sidewalk nodes)
        branch_sidewalk_nodes = []
        branch_sidewalk_nodes.append(border_nodes[0])
        if(len(border_nodes) > 1):
            branch_sidewalk_nodes.append(border_nodes[-1])
        sidewalk_nodes.append(branch_sidewalk_nodes)

    sidewalk_paths = []
    for i, branch_sidewalk_nodes in enumerate(sidewalk_nodes):
        # create sidewalk path
        next_i = i+1 if i < len(sidewalk_nodes)-1 else 0
        sidewalk_n1 = branch_sidewalk_nodes[1] if len(branch_sidewalk_nodes) > 1 else branch_sidewalk_nodes[0]
        sidewalk_n2 = sidewalk_nodes[next_i][0]
        sidewalk_path = getLeftShortestPath(G, sidewalk_n1.id, sidewalk_n2.id) # ox.distance.shortest_path(G, sidewalk_n1.id, sidewalk_n2.id)
        if(sidewalk_path):
            sidewalk_paths.append(sidewalk_path)
        
    return sidewalk_paths

def isPolygonClockwiseOrdered(polygon, G):
    polygon = list(polygon)
    for i in range(len(polygon)):
        id = polygon[i]
        polygon[i] = {"x":G.nodes[id]["x"],"y":G.nodes[id]["y"]}
    # we close the polygon if it's not closed
    if polygon[0] != polygon[-1]:
        polygon.append(polygon[0])
    sum = 0
    for i in range(len(polygon)-1):
        x1 = polygon[i]["x"]
        x2 = polygon[i+1]["x"]
        y1 = polygon[i]["y"]
        y2 = polygon[i+1]["y"]
        sum += (x2 - x1)*(y2 + y1)
    return sum >= 0
    

# Translate words
def tr(word):
    if word == "Road":
        return "circulation"
    if word == "Bus":
        return "bus"