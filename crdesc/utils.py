import glob
import json
from xml.dom import minidom
import math
from os import path
from datetime import datetime
from scipy.stats import circmean
import itertools
import osmnx as ox
import networkx as nx
import time

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
    angles = []
    for border_node in border_nodes:
        border_node = G.nodes[border_node]
        angles.append(ox.bearing.calculate_bearing(crossroad_center["y"], crossroad_center["x"], border_node["y"], border_node["x"]))
    mean_angle = circmean(angles, 0, 360)
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
def getSidewalks(G, branches, crossroad_border_nodes, crossroad_inner_nodes):

    G = ox.utils_graph.get_undirected(G)

    def getLeftShortestPath(G, n1, n2):
        path = [n1]
        while path[-1] != n2:
            neighbors = [neighbor for neighbor in G.neighbors(path[-1])]
            azimuth_by_node = [[next_node, ox.bearing.calculate_bearing(G.nodes[path[-1]]["y"], G.nodes[path[-1]]["x"], G.nodes[next_node]["y"], G.nodes[next_node]["x"])] for next_node in neighbors]
            azimuth_by_node.sort(key=lambda x: x[1]) # format : [[n1, azimuth], [n2, azimuth],...]
            if len(path) > 1: # if we started the path, the next node corresponds to the index next the n-2 node
                next_node = azimuth_by_node[([el[0] for el in azimuth_by_node].index(path[-2]) + 1) % len(azimuth_by_node)][0]
            else : # the first node of the path
                if len(azimuth_by_node) == 1: # if there's only one neighbour, it's the next node
                    next_node = azimuth_by_node[0][0]
                else: # else we grab an external node and use it to find the next node
                    external = None
                    nodes = []
                    for el in azimuth_by_node:
                        if el[0] not in crossroad_border_nodes.keys() and el[0] not in crossroad_inner_nodes.keys():
                            if external is None:
                                external = el[0]
                                nodes.append(el)
                        else:
                            nodes.append(el)  
                    next_node = nodes[([el[0] for el in nodes].index(external) + 1) % len(nodes)][0]
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

# remove edges that are not part of the crossroads
def cleanGraph(G, crossroad_edges):
    clean_G = G.copy()
    to_remove = []
    for (n1, n2, edge) in G.edges(data=True):
        if "%s%s"%(n1,n2) not in crossroad_edges.keys() and "%s%s"%(n2,n1) not in crossroad_edges.keys():
            to_remove.append([n1,n2])
    clean_G.remove_edges_from(to_remove)
    clean_G = ox.utils_graph.remove_isolated_nodes(clean_G)
    return clean_G  

# Translate words
def tr(word):
    if word == "Road":
        return "circulation"
    if word == "Bus":
        return "bus"