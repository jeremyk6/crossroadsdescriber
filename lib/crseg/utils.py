import osmnx as ox

from . import region as r

class Util:


    def centroid(G, points):
        x = 0.0
        y = 0.0
        for p in points:
            x += G.nodes[p]["x"]
            y += G.nodes[p]["y"]
        return (x / len(points), y / len(points))

    def coords_distance(point1, point2):
        x1 = point1[0]
        y1 = point1[1]
        x2 = point2[0]
        y2 = point2[1]
        return ox.distance.great_circle_vec(lat1=y1, lng1=x1, lat2=y2, lng2=x2)

    def distance_to(G, node, point):
        x1 = G.nodes[node]["x"]
        y1 = G.nodes[node]["y"]
        x2 = point[0]
        y2 = point[1]
        return ox.distance.great_circle_vec(lat1=y1, lng1=x1, lat2=y2, lng2=x2)

    # links are shorter than real paths
    def distance_with_shortcut(G, node1, node2):
        gEdge = G[node1][node2][0]
        coef = 1
        if "highway" in gEdge and gEdge["highway"] in ["primary_link", "secondary_link", "tertiary_link", "trunk_link", "motorway_link"]:
            coef = 0.5
        return Util.distance(G, node1, node2) * coef

    def distance(G, node1, node2):
        x1 = G.nodes[node1]["x"]
        y1 = G.nodes[node1]["y"]
        x2 = G.nodes[node2]["x"]
        y2 = G.nodes[node2]["y"]
        return ox.distance.great_circle_vec(lat1=y1, lng1=x1, lat2=y2, lng2=x2)

    def bearing(G, node1, node2):
        x1 = G.nodes[node1]["x"]
        y1 = G.nodes[node1]["y"]
        x2 = G.nodes[node2]["x"]
        y2 = G.nodes[node2]["y"]
        return ox.bearing.get_bearing((y1, x1), (y2, x2))

    def length(G, path):
        return sum([Util.distance(G, p1, p2) for p1, p2 in zip(path, path[1:])])

    def angular_distance(angle1, angle2):
        a = angle1 - angle2
        if a > 180:
            a -= 360
        if a < -180:
            a += 360 
        return abs(a)


    def get_adjacent_streetnames(G, node):
        streetnames = set()
        for nb in G.neighbors(node):
            if "name" in G[node][nb][0]:
                streetnames.add(G[node][nb][0]["name"])
            else:
                streetnames.add(None)
        return list(streetnames)

    def is_biffurcation(G, n):
        return len(list(G.neighbors(n))) > 2

    def is_middle_polyline(G, n):
        return len(list(G.neighbors(n))) == 2

    def get_opposite_node(G, n, other):
        for nb in G.neighbors(n):
            if nb != other:
                return nb
        # will not append
        return None


    def get_path_to_biffurcation(G, n1, n2, max = -1):
        path = [n1, n2]
        length = Util.distance(G, n1, n2)

        while (max < 0 or length < max) and Util.is_middle_polyline(G, path[len(path) - 1]):
            path.append(Util.get_opposite_node(G, path[len(path) - 1], path[len(path) - 2]))
            length += Util.distance(G, path[len(path) - 2], path[len(path) - 1])
        
        return path

    # return true if two the node is part of 3 edges, and
    # if two of them are one-way
    def is_street_separation(G, n):
        if len(G[n]) != 3:
            return False
        
        return len([nb for nb in G.neighbors(n) if "oneway" in G[n][nb][0] and G[n][nb][0]["oneway"]]) >= 2

    def is_part_of_local_triangle(G, n, max_perimeter = 150):

        paths = [ Util.get_path_to_biffurcation(G, n, nb) for nb in G.neighbors(n)]

        for i1, p1 in enumerate(paths):

            p1_end = p1[len(p1) - 1]
            p1_end_paths = [ Util.get_path_to_biffurcation(G, p1_end, nb) for nb in G.neighbors(p1_end)]
            p1_end_neighbors = [ p[len(p) - 1] for p in p1_end_paths]

            for i2 in range(i1, len(paths)):
                p2 = paths[i2]
                p2_end = p2[len(p2) - 1]
                if p2_end in p1_end_neighbors:
                    p = [ path for path in p1_end_paths if path[len(path) - 1] == p2_end][0]
                    l = Util.length(G, p1) + Util.length(G, p2) + Util.length(G, p)
                    if l < max_perimeter:
                        return True

        return False

    def has_non_labeled_adjacent_edge(G, n):
        for nb in G.neighbors(n):
            if G[n][nb][0][r.Region.label_region] == -1:
                return True
        return False

    def estimate_edge_width(G, edge):
        gEdge = G[edge[0]][edge[1]][0]
        import re
        if "width" in gEdge and not re.match(r'^-?\d+(?:\.\d+)$', gEdge["width"]) is None:
            return float(gEdge["width"])
        elif "lanes" in gEdge:
            nb = int(gEdge["lanes"])
        else:
            if "oneway" in gEdge and gEdge["oneway"]:
                nb = 1
            else:
                nb = 2
        
        if "highway" in gEdge:
            if gEdge["highway"] in ["motorway", "trunk"]:
                width = 3.5
            elif gEdge["highway"] in ["primary", "secondary"]:
                width = 3
            elif gEdge["highway"] in ["service"]:
                width = 2.25
            else:
                width = 2.75
        else:
            width = 3
        
        result = 0
        # TODO: improve integration of cycleways in this computation
        if ("cycleway" in gEdge and gEdge["cycleway"] == "track") or \
            ("cycleway:left" in gEdge and gEdge["cycleway:left"] == "track") or \
            ("cycleway:right" in gEdge and gEdge["cycleway:right"] == "track"):
            result = (nb + 1) * width # ~ COVID tracks
        else:
            result = nb * width

        return result
