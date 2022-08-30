from scipy.stats import circmean
import osmnx as ox
import networkx as nx
import pandas as pd
import operator
import copy

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

# Remove edges that are not part of the crossroads
def cleanGraph(G, crossroad_edges):
    clean_G = G.copy()
    to_remove = []
    for (n1, n2, edge) in G.edges(data=True):
        if "%s%s"%(n1,n2) not in crossroad_edges.keys() and "%s%s"%(n2,n1) not in crossroad_edges.keys():
            to_remove.append([n1,n2])
    clean_G.remove_edges_from(to_remove)
    clean_G = ox.utils_graph.remove_isolated_nodes(clean_G)
    return clean_G 

# Get the cycle path that represents the border of the crossroads
def getBorderPath(G, crossroad_inner_nodes, crossroad_border_nodes, crossroad_external_nodes, crossroad_edges):

    G = ox.utils_graph.get_undirected(G)

    n1 = list(crossroad_external_nodes.keys())[0]
    path = [n1]
    while True:
        neighbors = [neighbor for neighbor in G.neighbors(path[-1])]
        azimuth_by_node = [[next_node, ox.bearing.calculate_bearing(G.nodes[path[-1]]["y"], G.nodes[path[-1]]["x"], G.nodes[next_node]["y"], G.nodes[next_node]["x"])] for next_node in neighbors]
        azimuth_by_node.sort(key=lambda x: x[1]) # format : [[n1, azimuth], [n2, azimuth],...]
        if len(path) > 1: # if we started the path, the next node corresponds to the index next the n-2 node
            if path[-1] in list(crossroad_external_nodes.keys()): # if encountering an external border node, we go back
                next_node = path[-2]
            else:
                next_node = azimuth_by_node[([el[0] for el in azimuth_by_node].index(path[-2]) + 1) % len(azimuth_by_node)][0]
        else : # the first node of the path
            if len(azimuth_by_node) == 1: # if there's only one neighbour, it's the next node
                next_node = azimuth_by_node[0][0]
            else: # else we grab an external node and use it to find the next node
                external = None
                nodes = []
                for el in azimuth_by_node:
                    if el[0] not in (list(crossroad_border_nodes.keys()) + list(crossroad_inner_nodes.keys())):
                        if external is None:
                            external = el[0]
                            nodes.append(el)
                    else:
                        nodes.append(el)  
                next_node = nodes[([el[0] for el in nodes].index(external) + 1) % len(nodes)][0]
                G = cleanGraph(G, crossroad_edges)
        path.append(next_node)
        if path[-1] == n1: return path

def getBranchesEdges(border_path, seg_crossroad_branches, external_nodes):
    
    branch_edges = []
    for branch in seg_crossroad_branches:
        for edge in branch.edges_by_nodes:
            branch_edges.append({'branch_id' : branch.id, 'edge_id' : "%s%s"%(edge[0],edge[1]), 'order' : None})
    
    # How it works : 
    # Follow the border path, check if the edge (current node + next node) is part of a branch. If yes, ordering it starting from 0.
    # Particular case : if last node, the edge = current node + previous node.
    # If not starting from the first edge of a branch (in clockwise order), when the first branch is encountered again, order
    # will be negative to enable sorting with contiguous branches.
    order = 0
    first_branch = None
    flag = False
    for i in range(len(border_path)):
        if border_path[i] in external_nodes:
            for edge in branch_edges:
                next_i = i-1 if i == len(border_path)-1 else i+1
                if edge["edge_id"] in ["%s%s"%(border_path[i], border_path[next_i]), "%s%s"%(border_path[next_i], border_path[i])] and edge["order"] is None:
                        if first_branch is None:
                            first_branch = edge["branch_id"]
                        if flag == False and edge["branch_id"] != first_branch:
                            flag = True
                        if flag and edge["branch_id"] == first_branch:
                            edge["order"] = -(len(branch_edges)-order)
                        else:
                            edge["order"] = order
                        order += 1

    branch_edges.sort(key=operator.itemgetter('order'))

    return branch_edges

# Detect islands by closing branches with multiple ways, then by detecting faces
def getIslands(G, branches, crossroad_border_nodes):
    tG = copy.deepcopy(G)

    for i, branch in enumerate(branches): 
        border_nodes = []
        for j, way in enumerate(branch.ways):
            for junction in way.junctions:
                if junction.id not in crossroad_border_nodes.keys():
                    border_nodes.append(junction)    
        # Create faces for islands not closed in the graph (border islands)
        for j in range(len(border_nodes)-1):
            tG.add_edge(border_nodes[j].id, border_nodes[j+1].id)
    ox.distance.add_edge_lengths(tG)

    tG = nx.Graph(tG)
    faces = []
    for cycle in nx.minimum_cycle_basis(tG, "length"):
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

# Get sidewalks by following the border path of the intersection
def getSidewalks(border_path, branches, external_nodes):

    branch_nodes = []
    sidewalk_nodes = []
    for branch in branches:
        ways = [branch.ways[0]]
        if len(branch.ways) > 1: ways.append(branch.ways[-1])
        nodes = []
        for way in ways:
            for junction in way.junctions:
                if junction.id in external_nodes and junction.id not in nodes: nodes.append(junction.id)
        sidewalk_nodes += nodes
        branch_nodes.append(nodes)

    sidewalks = []
    sidewalk = []      
    for node in border_path:
        sidewalk.append(node)
        if len(sidewalk) > 1 and node in sidewalk_nodes and sidewalk[0] in sidewalk_nodes:
            if [sidewalk[0],sidewalk[-1]] not in branch_nodes and sidewalk[0] != sidewalk[-1]:
                sidewalks.append(sidewalk)
            sidewalk = [node]

    return sidewalks

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

def displayPath(G, path):
    ec = {}

    edges = []
    for i in range(len(path)-1):
        edges.append((path[i],path[i+1]))

    for edge in G.edges():
        ec[edge] = (0.5,0.5,0.5,0.5)
        if edge in edges or edge[::-1] in edges:
            ec[edge] = (1,0,0,1)

    ox.plot_graph(G, edge_color=pd.Series(ec), node_alpha=0)

# Translate words
def tr(word):
    if word == "Road":
        return "circulation"
    if word == "Bus":
        return "bus"