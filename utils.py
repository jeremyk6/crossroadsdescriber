import glob
import json
import math

# Read OSMnx cache and return start node and end node of a way if it exists
def getOriginalEdgeDirection(way_id, edge):
    path = glob.glob("cache/*.json")[0]
    data = json.load(open(path))
    for el in data["elements"]:
        if el["type"] == "way" and el["id"] == way_id:
            for node in el["nodes"]:
                if node == edge[0]:
                    return edge
                if node == edge[1]:
                    return [edge[1], edge[0]]
    return -1

# Compute  azimuth between two points
# Source : https://developpaper.com/example-of-python-calculating-azimuth-angle-based-on-the-coordinates-of-two-points/
def azimuthAngle( x1, y1, x2, y2):
    angle = 0.0
    dx = x2 - x1
    dy = y2 - y1
    if x2 == x1:
        angle = math.pi / 2.0
        if y2 == y1 :
            angle = 0.0
        elif y2 < y1 :
            angle = 3.0 * math.pi / 2.0
    elif x2 > x1 and y2 > y1:
        angle = math.atan(dx / dy)
    elif x2 > x1 and y2 < y1 :
        angle = math.pi / 2 + math.atan(-dy / dx)
    elif x2 < x1 and y2 < y1 :
        angle = math.pi + math.atan(dx / dy)
    elif x2 < x1 and y2 > y1 :
        angle = 3.0 * math.pi / 2.0 + math.atan(dy / -dx)
    return (angle * 180 / math.pi)

def tr(word):
    if word == "Road":
        return "circulation"
    if word == "Bus":
        return "bus"