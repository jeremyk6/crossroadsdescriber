
import osmnx as ox
import itertools


from . import reliability as rl
from . import region as r
from . import utils as u
from . import lane_description as ld


class Crossroad(r.Region):

    def __init__(self, G, node = None, target_id = -1):
        r.Region.__init__(self, G, target_id)

        self.max_distance_boundary_polyline = { "motorway": 100, 
                                                "trunk": 100,
                                                "primary": 80, 
                                                "secondary": 80, 
                                                "tertiary": 50, 
                                                "unclassified": 40, 
                                                "residential": 40,
                                                "living_street": 30,
                                                "service": 20,
                                                "default": 25
                                                }

        self.min_distance_boundary_polyline = { "motorway": 100, 
                                                "trunk": 100,
                                                "primary": 50, 
                                                "secondary": 25, 
                                                "tertiary": 20, 
                                                "unclassified": 15, 
                                                "residential": 15,
                                                "living_street": 10,
                                                "service": 6,
                                                "default": 6
                                                }

        if node != None:
            self.propagate(node)
            self.build_lanes_description()

    def __str__(self):
        if hasattr(self, "branches"):
            return "* id: %s\n* center: %s\n* lanes: %s\n* branches: %s" % (self.id, self.center, len(self.lanes), len(self.branches))
        else:
            return "* id: %s\n* center: %s\n* lanes: %s\n" % (self.id, self.center, len(self.lanes))

    def __repr__(self):
        return "id: %s, center: %s, #nodes: %s" % (self.id, self.center, len(self.nodes))

    def get_center(self):
        return self.center

    def is_crossroad(self):
        return True

    def to_text(self):
        text = "General description:\n" + self.__str__()
        text += "\nDetails:\n"
        text += str(self.to_json_data())
        return text

    def to_json_array(tp, innerNodes, borderNodes, edges, G):
        crdata = {}
        crdata["type"] = tp
        crdata["nodes"] = {}
        crdata["nodes"]["inner"] = innerNodes
        crdata["nodes"]["border"] = borderNodes
        crdata["edges_by_nodes"] = []
        for e in edges:
            crdata["edges_by_nodes"].append(e)
        crdata["coordinates"] = {n: {"x": G.nodes[n]["x"], "y": G.nodes[n]["y"]} for n in innerNodes + borderNodes}
        return crdata

    def to_json_data(self):
        data = []

        innerNodes = []
        borderNodes = []
        for n in self.nodes:
            if self.is_boundary_node(n):
                borderNodes.append(n)
            else:
                innerNodes.append(n)            

        data.append(Crossroad.to_json_array("crossroad", innerNodes, borderNodes, self.edges, self.G))

        # for each branch
        for branch in self.branches:
            nodes = set()
            for lane in branch:
                nodes.add(lane.edge[0])
                nodes.add(lane.edge[1])
            edges = [lane.edge for lane in branch]
            data.append(Crossroad.to_json_array("branch", [], list(nodes), edges, self.G))


        return data


    def get_lane_description_from_edge(self, edge):
        e = self.G[edge[0]][edge[1]][0]
        angle = u.Util.bearing(self.G, self.get_center(), edge[0 if self.get_center() == edge[1] else 1])
        name = e["name"] if "name" in e else None
        if name == None:
            # build the path starting from this edge
            path = u.Util.get_path_to_biffurcation(self.G, edge[0], edge[1])

            # if one of the edges has a name, it's the name of the lane
            for p1, p2 in zip(path, path[1:]):
                 e = self.G[p1][p2][0]
                 if "name" in e:
                     name = e["name"]
                     break

            if name == None:
                # if not found,
                # consider the last node of this path
                end = path[-1]
                # and check if it exists other paths between this end and the crossroad
                other_paths = []
                for nb in self.G.neighbors(end):
                    op = u.Util.get_path_to_biffurcation(self.G, end, nb)
                    if self.has_node(op[-1]):
                        # TODO: check if they are parallel
                        other_paths.append(op)
                # if only one path exists
                if len(other_paths) == 1:
                    o_e = self.G[other_paths[0][0]][other_paths[0][1]][0]
                    # if yes, the current edge has probably the same name
                    name = o_e["name"] if "name" in o_e else None
        return ld.LaneDescription(angle, name, edge)

    def get_lanes_description_from_node(self, border):
        edges = [(border, nb) for nb in self.G.neighbors(border) if not self.has_edge((nb, border))]
        return [self.get_lane_description_from_edge(e) for e in edges]

    def get_radius(self):
        borders = [n for n in self.nodes if self.is_boundary_node(n) and n != self.get_center()]
        center = self.get_center()
        if len(borders) == 0:
            radius = 0
            for nb in self.G.neighbors(center):
                c = self.get_highway_classification((center, nb))
                v = self.min_distance_boundary_polyline[c] / 2 # we reduce the impact of missing lanes
                if v > radius:
                    radius = v
            return radius
        else:
            return sum([u.Util.distance(self.G, center, b) for b in borders]) / len(borders)
        

    def get_open_paths(self, point, radius):
        result = []

        for nb in self.G.neighbors(point):
            if not self.has_edge((nb, point)):    
                result.append(u.Util.get_path_to_biffurcation(self.G, point, nb, radius))

        return result

    def build_lanes_description(self):
        self.lanes = []

        center = self.get_center()
        radius = self.get_radius()

        borders = [n for n in self.nodes if self.is_boundary_node(n)]

        for b in borders:
            if b != center:
                self.lanes = self.lanes + self.get_lanes_description_from_node(b)
            else:
                # go trough all possible paths starting from the center
                # and add the corresponding lanes
                open_lanes = self.get_open_paths(center, radius)
                for ol in open_lanes:
                    self.lanes.append(self.get_lane_description_from_edge((ol[1], ol[0])))
        

    def build_crossroads(G):
        crossroads = []
        for n in G.nodes:
            if r.Region.unknown_region_node_in_graph(G, n):
                if Crossroad.is_reliable_crossroad_node(G, n):
                    c = Crossroad(G, n)

                    if c.is_straight_crossing():
                        c.clear_region()
                    else:
                        crossroads.append(c)
        return crossroads

    def is_straight_crossing(self):
        for n in self.nodes:
            if len(list(self.G.neighbors(n))) > 2:
                return False
        
        return True


    def is_reliable_crossroad_node(G, n):
        if rl.Reliability.is_weakly_in_crossroad(G, n):
            return True

        for nb in G.neighbors(n):
            if rl.Reliability.is_weakly_in_crossroad_edge(G, (nb, n)):
                return True
        
        return False

    def propagate(self, n):

        self.add_node(n)
        self.center = n

        for nb in self.G.neighbors(n):
            if self.unknown_region_edge((n, nb)):
                paths = self.get_possible_paths(n, nb)
                for path in paths[::-1]:
                    if path != None and self.is_correct_inner_path(path):
                        self.add_path(path)
                        break


    def is_correct_inner_node(self, node):
        return not rl.Reliability.is_weakly_boundary(self.G, node)

    def get_max_highway_classification_other(self, path):
        if len(self.nodes) == 0:
            return None
        result = "default"
        value = self.max_distance_boundary_polyline[result]
        center = self.get_center()
        for nb in self.G.neighbors(center):
            if nb != path[1]:
                c = self.get_highway_classification((center, nb))
                v = self.max_distance_boundary_polyline[c]
                if v > value:
                    result = c
                    value = v
        return result
            

    def get_closest_possible_biffurcation(self, point):
        result = -1
        length = -1
        for nb in self.G.neighbors(point):
            path = u.Util.get_path_to_biffurcation(self.G, point, nb)
            l = u.Util.length(self.G, path)
            if length < 0 or l < length:
                length = l
                result = path[len(path) - 1]

        return result

    def get_highway_classification(self, edge):
        if not "highway" in edge:
            return "default"
        highway = edge["highway"]
        highway_link = highway + "_link"
        if highway_link in self.max_distance_boundary_polyline:
            highway = highway_link
        if not highway in self.max_distance_boundary_polyline:
            highway = "default"
        return highway

    def is_inner_path_by_osmdata(self, path):
        for p1, p2 in zip(path, path[1:]):
            if not "junction" in self.G[p1][p2][0]:
                return False
        return True

    def is_correct_inner_path(self, path):
        if len(path) < 2:
            return False
        # loops are not correct inner path in a crossing
        if path[0] == path[len(path) - 1]:
            return False

        # use "junction" OSM tag as a good clue
        if self.is_inner_path_by_osmdata(path):
            return True

        first = path[0]
        last = path[len(path) - 1]
        if rl.Reliability.is_weakly_in_crossroad(self.G, first) and rl.Reliability.is_weakly_boundary(self.G, last):
            d =  u.Util.length(self.G, path)
            r = 1
            if len(list(self.G.neighbors(first))) > 4: # a crossroad with many lanes is larger, thus 
                r = 2
            highway = self.get_max_highway_classification_other(path)
            if d < self.min_distance_boundary_polyline[highway] * r or \
                (d < self.max_distance_boundary_polyline[highway] * r and \
                self.get_closest_possible_biffurcation(last) == first):
                return True
            else:
                return False


    def get_possible_paths(self, n1, n2):
        results = []

        path = [n1, n2]

        # check first for a boundary
        while self.is_middle_path_node(path[len(path) - 1]):
            next = self.get_next_node_along_polyline(path[len(path) - 1], path[len(path) - 2])                

            if next == None:
                print("ERROR: cannot follow a path")
                return results
            path.append(next)

            # if we reach a known region, we stop the expension process
            if not self.unknown_region_node(next):
                break

        results.append(path)

        if not self.is_middle_path_node(path[len(path) - 1], True):
            return results
        path = path.copy()

        # if it's a weak border, we continue until we reach a strong one
        while self.is_middle_path_node(path[len(path) - 1], True):
            next = self.get_next_node_along_polyline(path[len(path) - 1], path[len(path) - 2])                

            if next == None:
                print("ERROR: cannot follow a path")
                return results
            path.append(next)

            # if we reach a known region, we stop the expension process
            if not self.unknown_region_node(next):
                break

        results.append(path)

        return results
    
    def is_middle_path_node(self, node, strong = False):
        if len(list(self.G.neighbors(node))) != 2:
            return False

        if strong:
            return not (rl.Reliability.is_strong_boundary(self.G, node) \
                    or rl.Reliability.is_strong_in_crossroad(self.G, node))
        else:
            return not (rl.Reliability.is_weakly_boundary(self.G, node) \
                    or rl.Reliability.is_weakly_in_crossroad(self.G, node))

    def get_next_node_along_polyline(self, current, pred):
        for n in self.G.neighbors(current):
            if n != pred:
                return n
        # cannot append
        return None


    def get_crossroads_in_neighborhood(self, crossroads, scale = 3):
        result = []

        center = self.get_center()
        radius = self.get_radius() * scale

        for c in crossroads:
            if c.id != self.id and u.Util.distance(self.G, center, c.get_center()) < radius:
                result.append(c)

        return result


    def find_direct_path_to_possible_adjacent_biffurcation(self, point):
        center = self.get_center()
        for nb in self.G.neighbors(center):
            path = u.Util.get_path_to_biffurcation(self.G, center, nb)
            if path[len(path) - 1] == point:
                return path
        return None

    def in_same_cluster(self, crossroad):

        if self.id == crossroad.id:
            return False  

        angle = u.Util.bearing(self.G, self.get_center(), crossroad.get_center())


        # if their is no direct path between centers, or 
        # if it exists a strong border between the two crossings, they are not
        # in the same cluster
        path = self.find_direct_path_to_possible_adjacent_biffurcation(crossroad.get_center())
        if path == None or rl.Reliability.has_strong_boundary_in_path(self.G, path):
            return False



        # if no strong boundary has been identified, consider similar branches
        # orthogonal to the junction
        for b1 in self.lanes:
            for b2 in crossroad.lanes:
                if b1.is_similar(b2) and (b1.is_orthogonal(angle) or b2.is_orthogonal(angle)):
                    return True

        return False

    # merge crossroads if they are in a neigborhood defined by scale times the radius of the crossroad
    # and if they are considered as "in same cluster" (using branch similarities)
    def get_clusters(crossroads, scale = 2):
        result = []

        visited = []

        for crossroad in crossroads:
            if not crossroad.id in visited:
                visited.append(crossroad.id)
                cluster = [crossroad]
            else:
                cluster = [c for c in result if crossroad in c]
                if len(cluster) != 1:
                    cluster = [crossroad]
                else:
                    cluster = cluster[0]
                    result = [c for c in result if not crossroad in c]

            cr_in_neigborhood = crossroad.get_crossroads_in_neighborhood(crossroads, scale)
            for cr in cr_in_neigborhood:
                if crossroad.in_same_cluster(cr):
                    if not cr.id in visited:
                        visited.append(cr.id)
                        cluster.append(cr)
                    else:
                        # merge clusters
                        other_cluster = [c for c in result if cr in c]
                        if len(other_cluster) != 1:
                            # we check if the merge wasn't processed before
                            if not cr in cluster:
                                print("Error while merging two clusters:", crossroad, cr)
                                print("Other cluster", other_cluster)
                                print("result", result)
                        else:
                            other_cluster = other_cluster[0]
                            cluster = cluster + other_cluster
                            result = [c for c in result if not cr in c]
                        
            if len(cluster) >= 1:
                result.append(cluster)

        # finally remove single clusters
        result = [r for r in result if len(r) > 1]
        return result

    # add to the current crossing the direct paths that connect the given points
    def add_direct_paths_between_nodes(self, points):
        # TODO: avoid too long paths
        for p1 in points:
            for n in self.G.neighbors(p1):
                if not self.has_edge((p1, n)):
                    path = u.Util.get_path_to_biffurcation(self.G, p1, n)
                    if path[len(path) - 1] in points and u.Util.length(self.G, path) < self.diameter():
                        self.add_path(path)

    # merge all given regions with the current one
    def merge(self, regions):
        # add nodes and edges from the other regions
        for region in regions:
            for n in region.nodes:
                self.add_node(n)
            for e in region.edges:
                self.add_edge(e)

        old_centers = [r.get_center() for r in regions]
        old_centers.append(self.get_center())

        # add missing paths between old centers
        self.add_direct_paths_between_nodes(old_centers)

        # set a new center
        center = u.Util.centroid(self.G, old_centers)
        distance = -1
        new_center = None
        for n in self.nodes:
            d = u.Util.distance_to(self.G, n, center)
            if distance < 0 or d < distance:
                distance = d
                new_center = n
        if new_center != None:
            self.center = new_center
        
        # finally rebuild the branch descriptions
        self.build_lanes_description()

    # add missing paths (inner paths and paths to boundaries)
    def add_missing_paths(self, scale = 2, boundaries = True):
        # add inner paths
        self.add_direct_paths_between_nodes(self.nodes)

        if boundaries:
            # add paths to missing boundaries within the given scale
            max_length = scale * self.get_radius()
            for p1 in self.nodes:
                for n in self.G.neighbors(p1):
                    if not self.has_edge((p1, n)) and self.G[p1][n][0][r.Region.label_region] == -1:
                        path = rl.Reliability.get_path_to_boundary(self.G, p1, n)
                        while len(path) > 2 and self.G[path[-2]][path[-1]][0][r.Region.label_region] != -1:
                            path.pop()
                        # find a boundary node inside the path and cut it
                        if len(path) > 0 and u.Util.length(self.G, path) < max_length:
                            self.add_path(path)

        # finally rebuild the branch descriptions
        self.build_lanes_description()

    def compute_branches(self):

        self.branches = []
        
        # for each lane
        for lane in self.lanes:
            mbranches = []

            # check if it's similar to a lane already in a built branch
            for i, branch in enumerate(self.branches):
                nb = len([l for l in branch if l.is_similar(lane)])
                if nb > 0:
                    mbranches.append(i)
            # if not, create a new branch
            if len(mbranches) == 0:
                self.branches.append([lane])
            else:
                # merge the similar branches
                self.branches[mbranches[0]].append(lane)
                for idb in mbranches[1:]:
                    self.branches[mbranches[0]] += self.branches[idb]
                    self.branches[idb] = []
            
            # remove empty branches
            self.branches = [ b for b in self.branches if len(b) > 0]

    # if the given edge is not part of a branch, it returns -1
    # otherwise, it returns the index of the branch (in this crossing) that contains the given edge
    def get_branch_id(self, e):

        for i, branch in enumerate(self.branches):
            for lane in branch:
                if lane.equals(e):
                    return i

        return -1

    # get the maximum estimated width of a branch
    def max_branch_width(self):
        if not hasattr(self, "branches"):
            self.compute_branches()
        return max([self.estimate_branch_width(b) for b in self.branches])


    def estimate_branch_width(self, branch):
        return sum([self.estimate_lane_width(l) for l in branch])
            
    def estimate_lane_width(self, lane):
        return u.Util.estimate_edge_width(self.G, lane.edge)
