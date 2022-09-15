from .model import *
from .segmentationReader import *
from .utils import *
from pyrealb import *
import networkx as nx
from geojson import Point, LineString, Feature, FeatureCollection, dumps

class Description:

    def __init__(self):

        self.crossroad = None
        Junction._junctions = {}

    def computeModel(self, G, segmentation_file):
        #
        # Model completion
        #

        seg_crossroad = SegmentationReader(segmentation_file).getCrossroads()[0]

        # intersection center. Computed by mean coordinates, may use convex hull + centroid later
        crossroad_center = meanCoordinates(G, seg_crossroad.border_nodes)

        # crossroad nodes creation
        crossroad_inner_nodes = {}
        crossroad_border_nodes = {}
        crossroad_external_nodes = {}
        for node_id in seg_crossroad.inner_nodes:
            crossroad_inner_nodes[node_id] = createJunction(node_id, G.nodes[node_id])
        for node_id in seg_crossroad.border_nodes:
            crossroad_border_nodes[node_id] = createJunction(node_id, G.nodes[node_id])
        for branch in seg_crossroad.branches :
            for node_id in branch.border_nodes:
                if node_id not in (list(crossroad_inner_nodes.keys()) + list(crossroad_border_nodes.keys())):
                    crossroad_external_nodes[node_id] = createJunction(node_id, G.nodes[node_id])

        #crossroad edges creation
        crossroad_edges = {}
        for edge in seg_crossroad.edges_by_nodes:
            edge_id = "%s%s"%(edge[0],edge[1])
            crossroad_edges[edge_id] = createWay(edge, G)
        for branch in seg_crossroad.branches:
            for edge in branch.edges_by_nodes:
                edge_id = "%s%s"%(edge[0],edge[1])
                crossroad_edges[edge_id] = createWay(edge, G, seg_crossroad.border_nodes)    

        # Get border path of the intersection, then keep only the border nodes (the external nodes of the branches)
        border_path = getBorderPath(G, crossroad_inner_nodes, crossroad_border_nodes, crossroad_external_nodes, crossroad_edges)
        external_nodes = [junction.id for junction in crossroad_external_nodes.values()] #list(dict.fromkeys(filter(lambda node : node in  list(crossroad_external_nodes.keys()), border_path)))
        branch_edges = getBranchesEdges(border_path, seg_crossroad.branches, external_nodes)

        # create branches
        branches = {}
        for edge in branch_edges:
            if not edge["branch_id"] in branches:
                branches[edge["branch_id"]] = Branch(edge["branch_id"], None, None, None, [])
            branch = branches[edge["branch_id"]]
            branch.ways.append(crossroad_edges[edge["edge_id"]])

        # add branches attributes
        min = None
        max = None
        for branch_id, branch in branches.items():
            nodes = []
            for way in branch.ways:
                if way.name != None : 
                    branch.street_name = [way.name.split(" ").pop(0).lower()," ".join(way.name.split(" ")[1:])]
                if way.junctions[0].id not in nodes : nodes.append(way.junctions[0].id)
                if way.junctions[1].id not in nodes : nodes.append(way.junctions[1].id)
            # compute branch bearing
            branch.angle = meanAngle(G, nodes, crossroad_center)
            if min is None: min,max = branch,branch
            if branch.angle < min.angle: min = branch
            if branch.angle > max.angle: max = branch

        # get the branch nearest to the north, then shift the branches list
        branches = list(branches.values())
        index = branches.index(max) if 360 - max.angle < min.angle else branches.index(min)
        branches = branches[index:] + branches[:index]

        # number branches according to their actuel order
        for i in range(len(branches)):
            branches[i].number = i + 1

        #
        # Sidewalks and islands generation
        #

        sidewalk_paths = getSidewalks(border_path, branches, external_nodes)

        # graph cleaning to remove edges that are not part of the crossroads
        G = cleanGraph(G, crossroad_edges)

        # Get sidewalks
        sidewalks = []
        for sidewalk_id, sidewalk_path in enumerate(sidewalk_paths):
            sidewalk = Sidewalk(sidewalk_id)
            sidewalks.append(sidewalk)
            for j, node in enumerate(sidewalk_path):
                if j < len(sidewalk_path)-1:
                    n1 = sidewalk_path[j]
                    n2 = sidewalk_path[j+1]
                    way = None
                    ids = ["%s%s"%(n1,n2), "%s%s"%(n2,n1)]
                    for id in ids:
                        if id in crossroad_edges:
                            way = crossroad_edges[id]
                    # if the way does not exist we create it (may not happen but sometimes it is)
                    if not way:
                        way = createWay([n1,n2], G)
                        crossroad_edges[id] = way
                    # if the sidewalk goes in the same direction as the way, it's the left sidewalk. Otherwise it's the right one.
                    if way.junctions[0].id == n1:
                        way.sidewalks[0] = sidewalk
                    else:
                        way.sidewalks[1] = sidewalk
                    # add pedestrian nodes to the crosswalks in the way
                    for junction in way.junctions:
                        if "Crosswalk" in junction.type:
                            if sidewalk not in junction.pedestrian_nodes:
                                junction.pedestrian_nodes.append(sidewalk)

        # Get islands in the crossroads
        islands = []
        for island_id, island_path in enumerate(getIslands(G, branches, crossroad_border_nodes)):
            if not isPolygonClockwiseOrdered(island_path, G):
                island_path = list(reversed(island_path))
            # island is not closed by NetworkX, we close it
            island_path.append(island_path[0])
            island = Island(island_id)
            islands.append(island)
            for j, node in enumerate(island_path):
                if j < len(island_path)-1:
                    n1 = island_path[j]
                    n2 = island_path[j+1]
                    way = None
                    ids = ["%s%s"%(n1,n2), "%s%s"%(n2,n1)]
                    for id in ids:
                        if id in crossroad_edges:
                            way = crossroad_edges[id]
                    if way:
                        if way.junctions[0].id == n1:
                            way.islands[1] = island
                        else:
                            way.islands[0] = island
                        # add pedestrian nodes to the crosswalks in the way
                        for junction in way.junctions:
                            if "Crosswalk" in junction.type:
                                if island not in junction.pedestrian_nodes:
                                    junction.pedestrian_nodes.append(island)

        #
        # Crossings creation
        #

        crosswalks = Junction.getJunctions("Crosswalk")


        # if two crosswalks share the same pedestrian nodes, choose the nearest to the crossroads
        to_delete = []
        for c1 in crosswalks:
            for c2 in crosswalks:
                if c1 != c2:
                    if c1.pedestrian_nodes == c2.pedestrian_nodes or c1.pedestrian_nodes[::-1] == c2.pedestrian_nodes:
                        if c1.id in [n.id for n in crossroad_border_nodes.values()]:
                            to_delete.append(c2)
        for d in to_delete: crosswalks.remove(d)

        # create dual graph
        pG = nx.Graph()
        for crosswalk in crosswalks:
            pG.add_edge(
                "s%s"%crosswalk.pedestrian_nodes[0].id if isinstance(crosswalk.pedestrian_nodes[0], Sidewalk) else "i%s"%crosswalk.pedestrian_nodes[0].id, 
                "s%s"%crosswalk.pedestrian_nodes[1].id if isinstance(crosswalk.pedestrian_nodes[1], Sidewalk) else "i%s"%crosswalk.pedestrian_nodes[1].id, 
                crosswalk=crosswalk
            )

        # compute crossings
        crossings = {}
        for sidewalk_start in sidewalks:
            for sidewalk_end in list(set(sidewalks) - set([sidewalk_start])):
                try:
                    crossing = nx.shortest_path(pG, "s%s"%sidewalk_start.id, "s%s"%sidewalk_end.id)
                except: # this sidewalk can't be reached
                    continue
                crossing_id = ";".join(crossing)
                if crossing_id.count("s") <= 2: # we keep paths that don't go through other sidewalks
                    if crossing_id not in crossings.keys() and ";".join(crossing_id.split(";")[::-1]) not in crossings.keys():
                        crosswalk_list = [pG[crossing[i]][crossing[i+1]]["crosswalk"] for i in range(len(crossing)-1)]
                        crossings[crossing_id] = Crossing(crossing_id, crosswalk_list)

        # attach crossings to a branch
        for branch in branches:

            # Retrieve branch sidewalks
            branch_sidewalks = []
            for items in [way.sidewalks for way in branch.ways]:
                for sidewalk in items:
                    if sidewalk is not None and sidewalk not in branch_sidewalks:
                        branch_sidewalks.append(sidewalk)
            
            # Retrieve crossing sidewalks
            for crossing in crossings.values():
                crossing_sidewalks = []
                for crosswalk in crossing.crosswalks:
                    for pedestrian_node in crosswalk.pedestrian_nodes:
                        if isinstance(pedestrian_node, Sidewalk):
                            crossing_sidewalks.append(pedestrian_node)
                # If the branch and the crossing share the same sidewalks, it's the branch's corssing
                if branch_sidewalks == crossing_sidewalks or branch_sidewalks[::-1] == crossing_sidewalks:
                    branch.set_crossing(crossing)
                    break

        #
        # Crossroad creation
        #

        self.crossroad = Intersection(None, branches, crossroad_center)
        self.crossroad.junctions = {**crossroad_inner_nodes, **crossroad_border_nodes}
        self.crossroad.ways = crossroad_edges
        self.crossroad.crossings = crossings

    #
    # Text generation
    #
    # Returns : a dict with a text attribute containing the description, and a structure attribute containing the non-concatenated description
    #

    def generateDescription(self):

        # Load PyRealB french lexicon and add missing words
        loadFr()
        addToLexicon("pyramide", {"N":{"g":"f","tab":"n17"}})
        addToLexicon("croisement", {"N":{"g":"m","tab":"n3"}})
        addToLexicon("îlot", {"N":{"g":"m","tab":"n3"}})
        addToLexicon("tourne-à-gauche", {"N":{"g":"m","tab":"n3"}})
        addToLexicon("tourne-à-droite", {"N":{"g":"m","tab":"n3"}})
        addToLexicon("entrant", {"A":{"tab":"n28"}})
        addToLexicon("sortant", {"A":{"tab":"n28"}})

        # if a branch does not have a name, we name it "rue qui n'a pas de nom"
        for branch in self.crossroad.branches:
            if branch.street_name is None : branch.street_name = ["rue","qui n'a pas de nom"]

        #
        # General description
        #
        streets = []
        for branch in self.crossroad.branches:
            if branch.street_name not in streets : streets.append(branch.street_name) 
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
        general_desc = "Le carrefour à l'intersection %s est un carrefour à %s branches."%(s, len(self.crossroad.branches))

        #
        # Branches description
        #

        branches_desc = []
        for branch in self.crossroad.branches:

            # branch number
            number = NO(branch.number).dOpt({"nat": True})

            name = " ".join(branch.street_name)
            
            channels = []
            for way in branch.ways:
                channels += way.channels
            n_voies = PP(
                P("de"),
                NP(
                    NO(len(channels)).dOpt({"nat": True}), 
                    N("voie")
                )
            )
            # temporary fix for pyrealb issue 4 (https://github.com/lapalme/pyrealb/issues/4)
            if len(channels) == 8 : n_voies = "de huit voies"

            channels_in_desc = CP(C("et"))
            channels_out_desc = CP(C("et"))

            # count number of channels per type
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
            if channels_in:
                word = "entrante"
                
                if n > 1:
                    word += "s"
                channels_in_desc = "%s %s"%(channels_in_desc, word)

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
            if channels_out:
                word = "sortante"
                if n > 1:
                    word += "s"
                channels_out_desc = "%s %s"%(channels_out_desc, word)

            branch_desc = "La branche numéro %s qui s'appelle %s est composée %s : %s%s%s."%(number, name, n_voies, channels_out_desc, ", et " if channels_in and channels_out else "", channels_in_desc)

            # post process to remove ':' and duplicate information if there's only one type of way in one direction
            branch_desc = branch_desc.split(" ")
            if " et " not in branch_desc:
                i = branch_desc.index(":")
                if branch_desc[i-2] == "d'une": branch_desc[i+1] = "d'une"
                branch_desc.pop(i-2)
                branch_desc.pop(i-2)
                branch_desc.pop(i-2)
            branch_desc = " ".join(branch_desc)

            # hacks to prettify sentences
            branch_desc = branch_desc.replace("qui s'appelle rue qui n'a pas de nom", "qui n'a pas de nom")
            branch_desc = branch_desc.replace("de une voie", "d'une voie")
            
            branches_desc.append(branch_desc)

        #
        # Traffic light cycle
        # right turn on red are barely modelized in OSM, see https://wiki.openstreetmap.org/w/index.php?title=Red_turn&oldid=2182526
        #

        #TODO

        #
        # Attention points
        #

        # TODO

        #
        # Crossings descriptions
        #
        crossings_desc = []

        for branch in self.crossroad.branches:

            number = NO(branch.number).dOpt({"nat": True})

            name = " ".join(branch.street_name)
            crosswalks = branch.crossing.crosswalks if branch.crossing is not None else []

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
                    if n_ptl == len(crosswalks):
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
                
            crossings_desc.append("La branche numéro %s %s. %s"%(number, "se traverse en %s fois"%n_crosswalks if len(crosswalks) else "ne se traverse pas", crossing_desc))

        #
        # Print description
        #

        description = ""
        description += general_desc+"\n\n"

        description += "== Description des branches ==\n\n"

        for branch_desc in branches_desc:
            description += branch_desc+"\n\n"

        description += "== Description des traversées ==\n\n"

        for crossing_desc in crossings_desc:
            description += crossing_desc+"\n\n"

        return({'text' : description, 'structure' : {'general_desc' : general_desc, 'branches_desc' : branches_desc, 'crossings_desc' : crossings_desc}})

    #
    # Generate a JSON that bind generated descriptions to OSM nodes
    #
    # Dependencies : the non-concatenated description
    # Returns : the JSON as a string

    def descriptionToJSON(self, description_structure):

        data = {}
        general_desc = description_structure["general_desc"]
        branches_desc = description_structure["branches_desc"]
        crossings_desc = description_structure["crossings_desc"]
        branches = self.crossroad.branches
        junctions = self.crossroad.junctions
        
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
                "text" : branch_desc + " " + " ".join(crossing_desc),
                "tags" : {
                    "auto" : "yes"
                }
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
                "text" : crosswalk_desc,
                "tags" : {
                    "auto" : "yes"
                }
            })

        return(json.dumps(data, ensure_ascii=False))

    def getGeoJSON(self, description_structure):
        features = []

        # Crossroad general description
        features.append(Feature(geometry=Point([self.crossroad.center["x"], self.crossroad.center["y"]]), properties={
            "id" : None,
            "type" : "crossroads",
            "description" : description_structure["general_desc"]
        }))

        # Crossroad branch description
        branches_ways = []
        for (branch, branch_desc) in zip(self.crossroad.branches, description_structure["branches_desc"]):
            for way in branch.ways:
                n1 = way.junctions[0]
                n2 = way.junctions[1]
                features.append(Feature(geometry=LineString([(n1.x, n1.y), (n2.x, n2.y)]), properties={
                    "id" : "%s;%s"%(n1.id, n2.id),
                    "type" : "branch",
                    "name" : "branch n°%s | %s"%(branch.number,way.name),
                    "description" : branch_desc,
                    "left_sidewalk" : way.sidewalks[0].id if way.sidewalks[0] else "",
                    "right_sidewalk" : way.sidewalks[1].id if way.sidewalks[1] else "",
                    "left_island" : way.islands[0].id if way.islands[0] else "",
                    "right_island" : way.islands[1].id if way.islands[1] else ""
                }))
                branches_ways.append(way)
        
        # Crossroad ways
        for way in self.crossroad.ways.values():
            if way not in branches_ways:
                n1 = way.junctions[0]
                n2 = way.junctions[1]
                features.append(Feature(geometry=LineString([(n1.x, n1.y), (n2.x, n2.y)]), properties={
                    "id" : "%s;%s"%(n1.id, n2.id),
                    "type" : "way",
                    "name" : way.name,
                    "left_sidewalk" : way.sidewalks[0].id if way.sidewalks[0] else "",
                    "right_sidewalk" : way.sidewalks[1].id if way.sidewalks[1] else "",
                    "left_island" : way.islands[0].id if way.islands[0] else "",
                    "right_island" : way.islands[1].id if way.islands[1] else ""
                }))

        # Single crosswalks descriptions
        crosswalks = []
        for junction in self.crossroad.junctions.values():
            if "Crosswalk" in junction.type:
                crosswalks.append(junction)
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
            features.append(Feature(geometry=Point([crosswalk.x, crosswalk.y]), properties={
                "id" : crosswalk.id,
                "type" : "crosswalk",
                "description" : crosswalk_desc
            }))

        # Crossings description
        for crossing, crossing_desc in zip([branch.crossing for branch in self.crossroad.branches], description_structure["crossings_desc"]):
            if crossing is None:
                continue
            crosswalks = crossing.crosswalks
            geom = None
            id = None
            if len(crosswalks) > 1:
                id = ";".join(map(str,[crosswalks[i].id for i in range(len(crosswalks))]))
                geom = LineString([(crosswalks[i].x, crosswalks[i].y) for i in range(len(crosswalks))])
            else:
                id = crosswalks[0].id
                geom = Point([crosswalks[0].x, crosswalks[0].y])
            features.append(Feature(geometry=geom, properties={
                "id" : id,
                "type" : "crossing",
                "description" : crossing_desc
            }))

        return(dumps(FeatureCollection(features)))