from . import crossroad as cr
from . import region as rg
from . import utils as u
from . import link as lk


class RegionFactory:

    def clone(region):
        if region.is_crossroad():
            result = cr.Crossroad(region.G)
        elif region.is_link():
            result = lk.Link(region.G)
            result.filled = region.filled
        else:
            result = rg.Region(region.G)
        result.nodes = region.nodes.copy()
        result.edges = region.edges.copy()

        result.lanes = region.lanes.copy()
        result.center = region.center

        return result

    def rebuild_regions_from_tags(G):
        # rebuild regions from metadata
        # ie for each region label associated to an edge or a node, create the corresponding region if it does not exists
        # considering the metadata to create a branch or a crossroad

        regions = {}
        for n in G.nodes:
            if G.nodes[n][rg.Region.label_region] != -1:
                id = G.nodes[n][rg.Region.label_region]
                if not id in regions:
                    regions[id] = cr.Crossroad(G, target_id = int(id)) if G.graph[rg.Region.regiontag_prefix + str(id)] == "crossroad" else rg.Region(G, target_id = id)
                regions[id].add_node(n)

        for e in G.edges:
            if G[e[0]][e[1]][0][rg.Region.label_region] != -1:
                id = G[e[0]][e[1]][0][rg.Region.label_region]
                if not id in regions:
                    regions[id] = cr.Crossroad(G, target_id = id) if G.graph[rg.Region.regiontag_prefix + str(id)] == "crossroad" else rg.Region(G, target_id = id)
                regions[id].add_edge(e)
                regions[id].add_node(e[0])
                regions[id].add_node(e[1])

        return regions

    def build_links_between_crossings(G, crossings):
        links = {}

        for rid in crossings:
            for b in crossings[rid].boundary_nodes():
                # if some edges are not in a region                    
                if u.Util.has_non_labeled_adjacent_edge(G, b):
                    # for each edge outside of a region, create a link region
                    for nb in G.neighbors(b):
                        if G[b][nb][0][rg.Region.label_region] == -1:
                            l = lk.Link(G, b, nb)
                            l.propagate()
                            links[l.id] = l
                else:
                    # create a link region with a single node (if not yet created)
                    exists = len([idl for idl in links if links[idl].has_node(b)])
                    if exists == 0:
                        l = lk.Link(G, b)
                        links[l.id] = l
                    

        return links