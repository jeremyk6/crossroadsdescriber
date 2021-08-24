from . import crossroad as cr
from . import region as rg


class RegionFactory:


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