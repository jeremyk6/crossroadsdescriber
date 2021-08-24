


import networkx as nx
import osmnx as ox
import pandas as pd
import random
import math


from . import region as r
from . import utils as u



class Reliability:

    # distance for a path to be considered as a branch
    distance_inner_branch = 50
 

    boundary_reliability = "reliability boundary"
    crossroad_reliability = "reliability.crossroad"


    moderate_boundary = [ "stop", "traffic_signals", "motorway_junction", "give_way" ]
    possible_boundary = [ "crossing"]
    strongly_no_boundary_attr = [ "bus_stop", "milestone", "steps", "elevator" ]

    strongly_yes = 1000.0
    strongly_no = 0.0

    uncertain = (strongly_yes + strongly_no) / 2

    weakly_yes = (strongly_yes + uncertain) / 2
    weakly_no = (strongly_no + uncertain) / 2

    moderate_yes = (weakly_yes + strongly_yes) / 2
    moderate_no = (weakly_no + strongly_no) / 2


    def init_attr(G):
        nx.set_node_attributes(G, values=Reliability.uncertain, name=Reliability.boundary_reliability)
        nx.set_node_attributes(G, values=Reliability.uncertain, name=Reliability.crossroad_reliability)
        Reliability.compute_nodes_reliability(G)

        nx.set_edge_attributes(G, values=Reliability.uncertain, name=Reliability.crossroad_reliability)
        Reliability.compute_edges_reliability(G)

    def compute_edges_reliability(G):

        for e in G.edges():
            length = u.Util.distance(G, e[0], e[1])
            if "junction" in G[e[0]][e[1]][0]:
                G[e[0]][e[1]][0][Reliability.crossroad_reliability] = Reliability.strongly_yes

    def compute_nodes_reliability(G):

        for n in G.nodes:
            nb_neighbors = len(list(G.neighbors(n)))

            if "highway" in G.nodes[n]:
                if nb_neighbors == 2:
                    G.nodes[n][Reliability.crossroad_reliability] = Reliability.strongly_no
                
                


                if G.nodes[n]["highway"] in Reliability.strongly_no_boundary_attr:
                    G.nodes[n][Reliability.boundary_reliability] = Reliability.moderate_no
                elif G.nodes[n]["highway"] in Reliability.possible_boundary and nb_neighbors <= 3:
                    G.nodes[n][Reliability.boundary_reliability] = Reliability.strongly_yes
                elif G.nodes[n]["highway"] in Reliability.moderate_boundary and nb_neighbors <= 3:
                    G.nodes[n][Reliability.boundary_reliability] = Reliability.moderate_yes
                    G.nodes[n][Reliability.crossroad_reliability] = Reliability.moderate_yes
                
                if nb_neighbors >= 3:
                    G.nodes[n][Reliability.crossroad_reliability] = Reliability.strongly_yes
            else:
                if nb_neighbors == 2:
                    G.nodes[n][Reliability.boundary_reliability] = Reliability.strongly_no
                    G.nodes[n][Reliability.crossroad_reliability] = Reliability.strongly_no
                elif nb_neighbors >= 4:
                        G.nodes[n][Reliability.crossroad_reliability] = Reliability.strongly_yes
                elif nb_neighbors == 3:
                        adj_streetnames = u.Util.get_adjacent_streetnames(G, n)

                        if len(adj_streetnames) > 1:
                            # more than one street name, it is probably part of a crossroad
                            G.nodes[n][Reliability.crossroad_reliability] = Reliability.moderate_yes
                        else:
                            # only one name
                            if u.Util.is_part_of_local_triangle(G, n) or u.Util.is_street_separation(G, n):
                                G.nodes[n][Reliability.crossroad_reliability] = Reliability.moderate_no
                            else:
                                G.nodes[n][Reliability.crossroad_reliability] = Reliability.moderate_yes


    def get_best_reliability_node(G, n):
        
        if G.nodes[n][Reliability.crossroad_reliability] > G.nodes[n][Reliability.boundary_reliability]:
            return Reliability.crossroad_reliability
        else:
            return Reliability.boundary_reliability

    def has_strong_boundary_in_path(G, path):
        for p in path:
            if Reliability.is_strong_boundary(G, p):
                return True
        return False

    def is_strong_boundary(G, n):
        return G.nodes[n][Reliability.boundary_reliability] == Reliability.strongly_yes

    def is_weakly_boundary(G, n):
        return G.nodes[n][Reliability.boundary_reliability] >= Reliability.weakly_yes

    def is_weakly_no_boundary(G, n):
        return G.nodes[n][Reliability.boundary_reliability] <= Reliability.weakly_no

    def is_strong_no_boundary(G, n):
        return G.nodes[n][Reliability.boundary_reliability] == Reliability.strongly_no

    def is_strong_in_crossroad(G, n):
        return G.nodes[n][Reliability.crossroad_reliability] == Reliability.strongly_yes

    def is_weakly_in_crossroad(G, n):
        return G.nodes[n][Reliability.crossroad_reliability] >= Reliability.weakly_yes

    def is_weakly_not_in_crossroad(G, n):
        return G.nodes[n][Reliability.crossroad_reliability] <= Reliability.weakly_no

    def is_strong_not_in_crossroad(G, n):
        return G.nodes[n][Reliability.crossroad_reliability] == Reliability.strongly_no

    def is_weakly_in_crossroad_edge(G, e):
        return G[e[0]][e[1]][0][Reliability.crossroad_reliability] >= Reliability.weakly_yes

    def is_strong_in_crossroad_edge(G, e):
        return G[e[0]][e[1]][0][Reliability.crossroad_reliability] == Reliability.strongly_yes


    def get_path_to_boundary(G, n1, n2, max = -1):
        path = [n1, n2]
        length = u.Util.distance(G, n1, n2)

        while (max < 0 or length < max) and u.Util.is_middle_polyline(G, path[len(path) - 1]):
            path.append(u.Util.get_opposite_node(G, path[len(path) - 1], path[len(path) - 2]))
            length += u.Util.distance(G, path[len(path) - 2], path[len(path) - 1])
            last = path[len(path) - 1]
            if Reliability.is_weakly_boundary(G, last):
                return path
        # we reach a split node without reaching a boundary node
        return []
        
