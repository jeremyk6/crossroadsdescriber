import osmnx as ox


class Util:


    def centroid(G, points):
        x = 0.0
        y = 0.0
        for p in points:
            x += G.nodes[p]["x"]
            y += G.nodes[p]["y"]
        return (x / len(points), y / len(points))

    def distance_to(G, node, point):
        x1 = G.nodes[node]["x"]
        y1 = G.nodes[node]["y"]
        x2 = point[0]
        y2 = point[1]
        return ox.distance.great_circle_vec(lat1=y1, lng1=x1, lat2=y2, lng2=x2)

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
