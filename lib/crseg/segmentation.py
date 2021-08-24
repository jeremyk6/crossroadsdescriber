
import networkx as nx
import osmnx as ox
import pandas as pd
import random
import math
import json


from . import crossroad as cr
from . import region as rg
from . import regionfactory as rf
from . import reliability as rel

class Segmentation:

    def __init__(self, G, init=True):
        self.G = G
        self.regions = {}
        random.seed()
        if init:
            rel.Reliability.init_attr(self.G)
        else:
            self.regions = rf.RegionFactory.rebuild_regions_from_tags(self.G)


    def process(self):

        # init flags
        rg.Region.init_attr(self.G)


        self.regions = {}

        # first build crossroads
        crossroads = cr.Crossroad.build_crossroads(self.G)
        for c in crossroads:
            self.regions[c.id] = c


        # group subparts of crossroads together if they are part of the same crossing
        scale = 4
        clusters = cr.Crossroad.get_clusters(crossroads, scale)

        # for each cluster
        for cluster in clusters:
            # merge them
            if len(cluster) > 1:
                cluster[0].merge(cluster[1:])
            for o in cluster[1:]:
                del self.regions[o.id]

        # add inner paths and missing boundaries
        for rid in self.regions:
            region = self.regions[rid]
            if region.is_crossroad():
                region.add_missing_paths()
            

        # TODO: second pass to merge main crossroad and small adjacent parts (such as access branches with forks)

        # TODO: add inner paths and missing boundaries (again)

        # create branch regions
        for rid in self.regions:
            self.regions[rid].compute_branches()
            



    def in_crossroad_region(self, e):
        tag = self.G[e[0]][e[1]][0][rg.Region.label_region]
        if tag == -1:
            False
        else: 
            return self.regions[tag].is_crossroad()


    def get_adjacent_crossroad_regions(self, n):
        result = []
        for nb in self.G.neighbors(n):
            e = (n, nb)
            tag = self.G[e[0]][e[1]][0][rg.Region.label_region]
            if tag != -1 and self.regions[tag].is_crossroad():
                result.append(self.regions[tag].id)
            else:
                result.append(-1)
        return result

    def is_crossroad_node(self, n):
        tag = self.G.nodes[n][rg.Region.label_region]
        if tag == -1:
            False
        else: 
            return self.regions[tag].is_crossroad()

    ######################### Functions used to prepare the graph ########################

    def remove_footways_and_parkings(G, keep_all_components):
            

        # remove footways and parkings
        to_remove = []
        for u, v, a in G.edges(data = True):
            if "footway" in a or ("highway" in a and a["highway"] in ["footway"]):
                to_remove.append((u, v))
                # add missing crossings
                if not "highway" in G.nodes[u]:
                    G.nodes[u]["highway"] = "crossing"
                if not "highway" in G.nodes[v]:
                    G.nodes[v]["highway"] = "crossing"
            if ("highway" in a and a["highway"] in ["cycleway", "path"]):
                to_remove.append((u, v))
            #elif "service" in a and a["service"] in ["parking_aisle"]:
            #    to_remove.append((u, v))                
        G.remove_edges_from(to_remove)
        G = ox.utils_graph.remove_isolated_nodes(G)
        if not keep_all_components:
            G = ox.utils_graph.get_largest_component(G)
        return G

        
    ######################### Functions related to graph rendering (colors) ########################

    # return edge colors according to the region label
    def get_regions_colors(self):
        result = {}
        color = {}
        for e in self.G.edges:
            tag = self.G[e[0]][e[1]][e[2]][rg.Region.label_region]
            if tag == -1:
                result[e] = (0.5, 0.5, 0.5, 0.5)
            else:
                if not tag in color:
                    color[tag] = Segmentation.random_color()
                result[e] = color[tag]
        return pd.Series(result)

    # return edge colors according to the region class label
    def get_regions_class_colors(self):
        result = {}
        for e in self.G.edges:
            tag = self.G[e[0]][e[1]][e[2]][rg.Region.label_region]
            if tag == -1:
                result[e] = (0.5, 0.5, 0.5, 0.5)
            elif self.regions[tag].is_crossroad():
                result[e] = (0.8, 0, 0, 1)
            elif self.regions[tag].is_branch():
                result[e] = (0.6, 0.6, 0, 1)
            else:
                result[e] = (0.3, 0.3, 0.3, 1)

        return pd.Series(result)


    def random_color(only_bg = False):
        r1 = math.pi * random.random()
        r2 = math.pi * random.random()
        start = 0.2
        coef = 0.8
        return (0 if only_bg else (start + coef * abs(math.sin(r1)) * abs(math.sin(r2))), \
                start + coef * abs(math.cos(r1)) * abs(math.sin(r2)), \
                start + coef * abs(math.sin(r1)) * abs(math.cos(r2)), 
                1)

    # return edge colors using one random color per label
    def get_edge_random_colors_by_attr(G, label, values = {}):
        result = {}
        for e in G.edges:
            tag = G[e[0]][e[1]][e[2]][label]
            if not tag in values:
                if tag == -1:
                    values[tag] = (0.5, 0.5, 0.5, 0.5)
                else:
                    values[tag] = Segmentation.random_color()
            result[e] = values[tag]
        return pd.Series(result)
        
    def get_nodes_reliability_on_regions_colors(self):

        result = {}
        for n in self.G.nodes:
            r_class = rel.Reliability.get_best_reliability_node(self.G, n)
            r_value = self.G.nodes[n][r_class]
            coef = (r_value - rel.Reliability.strongly_no) / (rel.Reliability.strongly_yes - rel.Reliability.strongly_no)
            coef = math.pow(coef, 2)
            if r_class == rel.Reliability.crossroad_reliability:
                result[n] = (0.8, 0, 0, coef)
            elif r_class == rel.Reliability.boundary_reliability:
                adj = self.get_adjacent_crossroad_regions(n)
                # in the middle of a branch
                if len([n for n in adj if n != -1]) == 0:
                    result[n] = (0, 0, 0.6, coef)
                # inside a region
                elif len(list(set([n for n in adj if n != -1]))) == 1 and len([n for n in adj if n != -1]) != 1:
                    result[n] = (1, 0.6, 0.6, coef)
                # in a boundary
                else:
                    result[n] = (0.6, 0.6, 0, coef)

            else: # branch
                result[n] = (0, 0, 0, 0)


        return pd.Series(result)


    def get_edges_reliability_colors(self):
        result = {}
        for e in self.G.edges:
            r_value = self.G[e[0]][e[1]][e[2]][rel.Reliability.crossroad_reliability]
            coef = (r_value - rel.Reliability.strongly_no) / (rel.Reliability.strongly_yes - rel.Reliability.strongly_no)
            coef = math.pow(coef, 2)
            result[e] = (1, 1, 1, coef)
        return pd.Series(result)

    def get_nodes_reliability_colors(self):

        result = {}
        for n in self.G.nodes:
            r_class = rel.Reliability.get_best_reliability_node(self.G, n)
            r_value = self.G.nodes[n][r_class]
            coef = (r_value - rel.Reliability.strongly_no) / (rel.Reliability.strongly_yes - rel.Reliability.strongly_no)
            coef = math.pow(coef, 2)
            if r_class == rel.Reliability.boundary_reliability:
                result[n] = (0.1, 0, 0.8, coef)
            else:
                result[n] = (0.8, 0, 0, coef)


        return pd.Series(result)

    def get_boundary_node_colors(self):

        result = {}
        for n in self.G.nodes:
            nb_adj_crossings = len(list(set([r for r in self.get_adjacent_crossroad_regions(n) if r != -1])))
            nbnb = len(list(self.G.neighbors(n)))
            nbAdj = len([ nb for nb in self.G.neighbors(n) if rg.Region.unknown_region_edge_in_graph(self.G, (n, nb))])
            if nbnb == nbAdj:
                if nbnb == 1: # dead end
                    result[n] = (0.5, 0.5, 0.5, 0.1)
                elif rg.Region.unknown_region_node_in_graph(self.G, n):
                    result[n] = (0, 0, 0.5, 1) # node not taggued, possibly a missing crossing
                else:
                    if nb_adj_crossings >= 2:
                        result[n] = (0.6, 0.6, 0, 1) # splitter in a crossroad
                    elif nb_adj_crossings == 0 and self.is_crossroad_node(n):
                        result[n] = (1, 0, 0, 1) # single-node crossroad
                    else:
                        result[n] = (0, 0, 0, 0)
            else:
                if nb_adj_crossings >= 2:
                    result[n] = (0.6, 0.6, 0, 1) # splitter in a crossroad
                elif nb_adj_crossings == 0 and self.is_crossroad_node(n):
                    result[n] = (1, 0, 0, 1) # single-node crossroad
                else:
                    result[n] = (0, 0, 0, 0)
        return pd.Series(result)

    def get_nodes_regions_colors(self):
        result = {}
        for n in self.G.nodes:
            if len(list(self.G.neighbors(n))) <= 2:
                result[n] = (0, 0, 0, 0)
            else:
                label = self.G.nodes[n][rg.Region.label_region]
                if label < 0:
                    result[n] = (0, 0, 0, 0)
                else:
                    nb_edge_in_region = len([nb for nb in self.G[n] if self.G[n][nb][0][rg.Region.label_region] == label])
                    if nb_edge_in_region == 0:
                        result[n] = Segmentation.random_color()
                    else:
                        result[n] = (0, 0, 0, 0)

        return pd.Series(result)

    def get_regions_colors_from_crossroad(self, cr):
        result = {}
        color = {}
        for e in self.G.edges:
            tag = self.G[e[0]][e[1]][e[2]][rg.Region.label_region]
            if tag != cr.id:
                bid = cr.get_branch_id(e)
                if bid == -1:
                    result[e] = (0.5, 0.5, 0.5, 0.1)
                else:
                    tag = cr.id + bid + 1
                    if not tag in color:
                        color[tag] = Segmentation.random_color()
                    result[e] = color[tag]
            else:
                if not tag in color:
                    color[tag] = (1, 0, 0, 1)
                result[e] = color[tag]
        return pd.Series(result)

    def get_nodes_regions_colors_from_crossroad(self, cr):
        result = {}
        for n in self.G.nodes:
            if len(list(self.G.neighbors(n))) <= 2:
                result[n] = (0, 0, 0, 0)
            else:
                label = self.G.nodes[n][rg.Region.label_region]
                if label != cr.id:
                    result[n] = (0, 0, 0, 0)
                else:
                    nb_edge_in_region = len([nb for nb in self.G[n] if self.G[n][nb][0][rg.Region.label_region] == label])
                    if nb_edge_in_region == 0:
                        result[n] = Segmentation.random_color()
                    else:
                        result[n] = (0, 0, 0, 0)

        return pd.Series(result)

    ######################### text descriptions ########################

    def get_crossroad(self, longitude, latitude):
        distance = -1
        middle = -1
        for rid in self.regions:
            region = self.regions[rid]
            x1 = self.G.nodes[region.get_center()]["x"]
            y1 = self.G.nodes[region.get_center()]["y"]
            d = ox.distance.great_circle_vec(lat1=y1, lng1=x1, lat2=latitude, lng2=longitude)
            if distance < 0 or d < distance:
                distance = d
                middle = rid
        return self.regions[middle]

    def to_text(self, longitude, latitude):
        return self.get_crossroad(longitude, latitude).to_text()

    def to_text_all(self):
        result = ""
        for rid in self.regions:
            result += self.regions[rid].to_text()
            result += "\n"
            result += "\n"
        return result

    ######################### json descriptions ########################

    def to_json(self, filename, longitude, latitude):
        data = self.get_crossroad(longitude, latitude).to_json_data()

        with open(filename, 'w') as outfile:
            json.dump(data, outfile)


    def to_json_all(self, filename):
        data = []
        for rid in self.regions:
            entry = self.regions[rid].to_json_data()
            data.append(entry)

        with open(filename, 'w') as outfile:
            json.dump(data, outfile)
