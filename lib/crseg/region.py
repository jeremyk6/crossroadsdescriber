import networkx as nx
import osmnx as ox
import pandas as pd
import random
import math


from . import utils as u
from . import reliability as r



class Region:

    id_region = 0

    label_region = "region"
    regiontag_prefix = "cr.region-"

    def __init__(self, G, target_id = -1):
        self.G = G
        self.edges = []
        self.nodes = []
        if target_id == -1:
            self.id = Region.id_region
            Region.id_region += 1
        else:
            self.id = target_id
            if Region.id_region <= target_id:
                Region.id_region = target_id + 1

    def is_crossroad(self):
        return False

    def is_link(self):
        return False

    def clear_region(self):
        # remove edges
        for e in self.edges:
            self.G[e[0]][e[1]][0][Region.label_region] = -1
        
        # then remove nodes
        for n in self.nodes:
            self.G.nodes[n][Region.label_region] = -1
    
    # return true if all the nodes of the given region are part of the current region
    def contains(self, region):
        for n in region.nodes:
            if not n in self.nodes:
                return False
        return True

    def init_attr(G):
        nx.set_edge_attributes(G, values=-1, name=Region.label_region)
        nx.set_node_attributes(G, values=-1, name=Region.label_region)

    def unknown_region_node_in_graph(G, n):
        return G.nodes[n][Region.label_region] == -1

    def unknown_region_edge_in_graph(G, e):
        return G[e[0]][e[1]][0][Region.label_region] == -1

    def unknown_region_node(self, n):
        return Region.unknown_region_node_in_graph(self.G, n)

    def unknown_region_edge(self, e):
        return Region.unknown_region_edge_in_graph(self.G, e)

    def clear_node_region_in_grah(G, n):
        G.nodes[n][Region.label_region] = -1

    def add_path(self, path):
        for n in path:
            self.add_node(n)
        for n1, n2 in zip(path, path[1:]):
            self.add_edge((n1, n2))

    def add_paths(self, paths):
        for path in paths:
            self.add_path(path)

    def add_node(self, n):
        if n not in self.nodes:
            self.nodes.append(n)
        self.G.nodes[n][Region.label_region] = self.id

    def add_edge(self, e):
        if not self.has_edge(e):
            self.edges.append(e)
        self.G[e[0]][e[1]][0][Region.label_region] = self.id

    def add_path(self, path):
        for p in path:
            self.add_node(p)
        for p1, p2 in zip(path, path[1:]):
            self.add_edge((p1, p2))

    def has_edge(self, e):
        return (e[0], e[1]) in self.edges or (e[1], e[0]) in self.edges

    def has_node(self, n):
        return n in self.nodes

    def edges_with_node(self, n):
        return [ e for e in self.edges if e[0] == n or e[1] == n]

    def is_boundary_node(self, n):
        nbnb = len(list(self.G.neighbors(n)))
        nbEdgesInside = len([e for e in self.edges if e[0] == n or e[1] == n])
        return nbnb != nbEdgesInside

    def centroid(self):
        return u.Util.centroid(self.G, self.nodes)

    def boundary_nodes(self):
        result = []
        for n in self.nodes:
            if self.is_boundary_node(n):
                result.append(n)
        return result

    def diameter(self):
        # TODO: not optimized
        result = 0
        for n1 in self.nodes:
            for n2 in self.nodes:
                d = u.Util.distance(self.G, n1, n2)
                if d > result:
                    result = d
        return result

    # return a shortest path inside the current region that connects a node from nodes1 and a node from nodes2
    # if no such path exists, it returns an empty path
    def get_path(self, nodes1, nodes2, weight_function = None):
        if len(nodes1) == 0 or len(nodes2) == 0:
            return []

        cutoff = 3 * self.diameter() # large number in case of non straight paths
        # get all possible paths in the current region from the input nodes
        distances, paths = nx.multi_source_dijkstra(self.G, nodes1, 
            weight = lambda n1, n2, d: (weight_function(self.G, n1, n2) if weight_function != None else u.Util.distance(self.G, n1, n2)) if self.has_edge((n1, n2)) else None, 
            cutoff = cutoff)

        # keep paths that reach one of the given nodes
        distances = {k: v for k, v in distances.items() if k in nodes2}
        if len(distances) == 0:
            return None
        # keep the best one
        best_target = min(distances, key=distances.get)
        return paths[best_target], distances[best_target]
