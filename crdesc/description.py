from .model import *
from .segmentationReader import *
from .utils import *
from .jsRealBclass import *
from toolz import unique
import osmnx as ox
import networkx as nx
from geojson import Point, LineString, Feature, FeatureCollection, dumps

class Description:

    def __init__(self):

        self.crossroad = None

    def computeModel(self, G, segmentation_file, xml_file=None):
        #
        # Model completion
        #

        seg_crossroad = SegmentationReader(segmentation_file).getCrossroads()[0]

        # intersection center. Computed by mean coordinates, may use convex hull + centroid later
        crossroad_center = meanCoordinates(G, seg_crossroad.border_nodes)

        # crossroad nodes creation
        crossroad_inner_nodes = {}
        crossroad_border_nodes = {}
        for node_id in seg_crossroad.inner_nodes:
            crossroad_inner_nodes[node_id] = createJunction(node_id, G.nodes[node_id])
        for node_id in seg_crossroad.border_nodes:
            crossroad_border_nodes[node_id] = createJunction(node_id, G.nodes[node_id])

        #crossroad edges creation
        crossroad_edges = {}
        for edge in seg_crossroad.edges_by_nodes:
            edge_id = "%s%s"%(edge[0],edge[1])
            crossroad_edges[edge_id] = createWay(edge, G, xmlfile=xml_file)

        # branch creation
        id = 1
        branches = []
        for branch in seg_crossroad.branches:

            ways = []
            azimuths = []

            border_nodes = []

            for edge in branch.edges_by_nodes:

                # keep border nodes
                border_node = None
                if edge[0] in branch.border_nodes:
                    border_nodes.append(edge[0])
                    border_node = G.nodes[edge[0]]
                if edge[1] in branch.border_nodes:
                    border_nodes.append(edge[1])
                    border_node = G.nodes[edge[1]]

                edge_id = "%s%s"%(edge[0],edge[1])
                crossroad_edges[edge_id] = createWay(edge, G, seg_crossroad.border_nodes, xmlfile=xml_file)
                ways.append(crossroad_edges[edge_id])
                azimuths.append(azimuthAngle(crossroad_center["x"], crossroad_center["y"], border_node["x"], border_node["y"]))

            # reorder ways in branch
            if(max(azimuths) - min(azimuths) >= 180):
                for i in range(len(azimuths)):
                    if azimuths[i] >= 270 : azimuths[i] -= 360
            azimuths, ways = (list(t) for t in zip(*sorted(zip(azimuths, ways))))
            # Casse ici : 45.77340 3.09223 WTF ?!

            # compute mean angle by branch
            mean_angle = meanAngle(G, border_nodes, crossroad_center)

            # fetch name of the way in the middle of the branch
            name = ways[int(len(ways)/2)].name

            branches.append(Branch(id, mean_angle, None, name, ways))

            id += 1

        # order branch by angle
        branches.sort(key=lambda b: b.angle)

        # branch number : number branches according to their clockwise order
        for i, branch in enumerate(branches): 
            branch.number = i+1
            #format street name for the text generation
            street_name = branch.street_name.split(" ")
            branch.street_name = [street_name.pop(0).lower()," ".join(street_name)]

        # graph cleaning to remove edges that are not part of the crossroads
        to_remove = []
        for (n1, n2, edge) in G.edges(data=True):
            if "%s%s"%(n1,n2) not in crossroad_edges.keys() and "%s%s"%(n2,n1) not in crossroad_edges.keys():
                to_remove.append([n1,n2])
        G.remove_edges_from(to_remove)

        #
        # Sidewalks and islands generation
        #

        # Get sidewalks
        sidewalks = []
        for sidewalk_id, sidewalk_path in enumerate(getSidewalks(G, branches, crossroad_border_nodes)):
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
                        way = createWay([n1,n2], G, xmlfile=xml_file)
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
    # Dependencies : a jsRealB server
    # Returns : a dict with a text attribute containing the description, and a structure attribute containing the non-concatenated description
    #

    def generateDescription(self, jsrealb_server_url):

        # Set jsRealB server URL
        jsRealB_setServerURL(jsrealb_server_url)

        #
        # General description
        #

        streets = map(list, unique(map(tuple, [branch.street_name for branch in self.crossroad.branches]))) # horrible syntax to remove duplicates
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
        general_desc = "Le carrefour à l'intersection %s est un carrefour à %s branches."%(jsRealB(s), len(self.crossroad.branches))

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
            channels_in_desc = jsRealB(channels_in_desc)
            if channels_in:
                word = "entrante"
                
                if n > 1:
                    word += "s"
                channels_in_desc += " %s"%word

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
            channels_out_desc = jsRealB(channels_out_desc)
            if channels_out:
                word = "sortante"
                if n > 1:
                    word += "s"
                channels_out_desc += " %s"%word

            branch_desc = "La branche numéro %s qui s'appelle %s est composée %s : %s%s%s."%(jsRealB(number), name, jsRealB(n_voies), channels_out_desc, ", et " if channels_in_desc and channels_out_desc else "", channels_in_desc)

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
            crosswalks = []

            for way in branch.ways:
                
                for junction in way.junctions:
                    if "Crosswalk" in junction.type:
                        crosswalks.append(junction)

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

            # TODO 
            # add bikeboxes sentence in outgoing lanes if any

            # TODO
            # add, for islands, if difficult movements need to be made
                
            crossings_desc.append("La branche numéro %s %s. %s"%(jsRealB(number), "se traverse en %s fois"%jsRealB(n_crosswalks) if len(crosswalks) else "ne se traverse pas", crossing_desc))

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
                    "type" : "branch",
                    "name" : way.name,
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
                    "type" : "way",
                    "name" : way.name,
                    "left_sidewalk" : way.sidewalks[0].id if way.sidewalks[0] else "",
                    "right_sidewalk" : way.sidewalks[1].id if way.sidewalks[1] else "",
                    "left_island" : way.islands[0].id if way.islands[0] else "",
                    "right_island" : way.islands[1].id if way.islands[1] else ""
                }))

        # Crossings description
        for crossing, crossing_desc in zip(self.crossroad.crossings.values(), description_structure["crossings_desc"]):
            crosswalks = crossing.crosswalks
            geom = None
            if len(crosswalks) > 1:
                geom = LineString([(crosswalks[i].x, crosswalks[i].y) for i in range(len(crosswalks))])
            else:
                geom = Point([crosswalks[0].x, crosswalks[0].y])
            features.append(Feature(geometry=geom, properties={
                "type" : "crossing",
                "description" : crossing_desc
            }))

        return(dumps(FeatureCollection(features)))