from utils import *

#
# Intersection
#

class Intersection():

    def __init__(self, type, branches):
        self.type = type
        self.branches = branches

#
# Branches
#

class Branch():

    def __init__(self, id, angle, direction_name, street_name, ways):
        self.id = id
        self.number = None
        self.angle = angle
        self.direction_name = direction_name
        self.street_name = street_name
        self.ways = ways

#
# Ways
#

class Way():

    def __init__(self, id, name, junctions, channels):
        self.id = id
        self.name = name
        self.junctions = junctions
        self.channels = channels

class Channel():

    def __init__(self, id, direction):
        self.id = id
        self.direction = direction

class Road(Channel):

    def __init__(self, id, direction):
        super().__init__(id, direction)

class Bus(Channel):

    def __init__(self, id, direction):
        super().__init__(id, direction)

class Island(Channel):

    def __init__(self, id, direction):
        super().__init__(id, direction)

class Sidewalk(Channel):

    def __init__(self, id, direction):
        super().__init__(id, direction)

class Bicycle(Channel):

    def __init__(self, id, direction):
        super().__init__(id, direction)

#
# Junctions
#
# Use the decorator design pattern, that enables having one class per concrete object with its own semantic attributes to create a complex junction

# Abstract junction
class AbstractJunction():
    pass

# Concrete junction
class Junction(AbstractJunction):

    def __init__(self, id, x, y):
        super().__init__()
        self.id = id
        self.x = x
        self.y = y
        self.type = []

# Junction decorator
class JunctionDecorator(AbstractJunction):

    _junction : AbstractJunction = None

    def __init__(self, junction : AbstractJunction):
        self._junction = junction
        self._junction.type.append(type(self).__name__)

    @property
    def junction(self) -> str:
        return self._junction

    @property
    def id(self) -> str:
        return self._junction.id

    @property
    def x(self) -> str:
        return self._junction.x
    
    @property
    def y(self) -> str:
        return self._junction.y

    @property
    def type(self) -> str:
        return self._junction.type

# Concrete decorators

# Bikebox decorator
class Bikebox(JunctionDecorator):

    def __init__(self, decorated_junction, bb_distance_from_tl):
        JunctionDecorator.__init__(self, decorated_junction)

        # Specific attributes
        JunctionDecorator.bb_distance_from_tl = bb_distance_from_tl

# Crosswalk decorator
class Crosswalk(JunctionDecorator):

    def __init__(self, decorated_junction, cw_tactile_paving):
        JunctionDecorator.__init__(self, decorated_junction)

        # Specific attributes
        JunctionDecorator.cw_tactile_paving = cw_tactile_paving

# Pedestrian traffic light decorator
class Pedestrian_traffic_light(JunctionDecorator):

    def __init__(self, decorated_junction, ptl_sound):
        JunctionDecorator.__init__(self, decorated_junction)

        # Specific attributes
        JunctionDecorator.ptl_sound = ptl_sound

# Traffic light decorator
class Traffic_light(JunctionDecorator):

    def __init__(self, decorated_junction, tl_phase, tl_direction):
        JunctionDecorator.__init__(self, decorated_junction)

        # Specific attributes
        JunctionDecorator.tl_phase = tl_phase
        JunctionDecorator.tl_direction = tl_direction

# Yield decorator
class Yield(JunctionDecorator):

    def __init__(self, decorated_junction, yd_direction, yd_way):
        JunctionDecorator.__init__(self, decorated_junction)

        # Specific attributes
        JunctionDecorator.yd_direction = yd_direction
        JunctionDecorator.yd_way = yd_way

#
# Object creation function
#

def createCrosswalk(junction, node):
    # Does it have a tactile paving ?
    cw_tactile_paving = "no"
    if "tactile_paving" in node:
        cw_tactile_paving = node["tactile_paving"]
    junction = Crosswalk(junction, cw_tactile_paving)
    # Does it have a traffic light ?
    if node["crossing"] == "traffic_signals":
        ptl_sound = "no"
        # Does it have sound ?
        if "traffic_signals:sound" in node and node["traffic_signals:sound"] == "yes":
            ptl_sound = "yes"
        junction = Pedestrian_traffic_light(junction, ptl_sound)
    return junction

def createTrafficSignal(junction, node):
    tl_direction = "forward"
    if "traffic_signals:direction" in node:
        tl_direction = node["traffic_signals:direction"]
    junction = Traffic_light(junction, None, tl_direction)
    return junction

def createJunction(node_id, node):
    junction = Junction(node_id, node["x"], node["y"])
        
    # is it a crosswalk ?
    if "crossing" in node and node["crossing"] != "no":
        junction = createCrosswalk(junction, node)

    # is it a traffic light ?
    if "traffic_signals" in node:
        junction = createTrafficSignal(junction, node)

    return junction

def createLane(type, way, way_out):
    if type == "Road":
        way.channels.append(Road(None, "out" if way_out else "in"))
    if type == "Bus":
        way.channels.append(Bus(None, "out" if way_out else "in"))

def createDirectedLanes(edge, way, way_out):
    # does it have designated bus lanes ?
    if "psv:lanes:backward" in edge and "psv:lanes:forward" in edge:
        for lane in edge["psv:lanes:backward"].split("|"):
            type = "Road"
            if lane == "designated": type = "Bus",
            createLane(type, way, not way_out)
        for lane in edge["psv:lanes:forward"].split("|"):
            type = "Road"
            if lane == "designated": type = "Bus"
            createLane(type, way, way_out)
    else:
        for i in range(int(edge["lanes:backward"])): createLane("Road", way, not way_out)
        for i in range(int(edge["lanes:forward"])): createLane("Road", way, way_out)

def createUndirectedLanes(edge, way, way_out):
    for i in range(int(edge["lanes"])):
        type = "Road"
        if edge["highway"]=="service" and "psv" in edge and edge["psv"]=="yes": type = "Bus"
        createLane(type, way, way_out)

def createWay(edge, G, border_nodes=[]):
    n1 = edge[0]
    n2 = edge[1]

    # try both order of the edge in case of oneway
    try:
        edge = G[n1][n2][0]
    except:
        n1,n2 = n2,n1
        edge = G[n1][n2][0]
    n1,n2 = getOriginalEdgeDirection(edge["osmid"], [n1,n2])
    
    # Note : access node attributes
    # ex. for x : G.nodes[n1].x
    # Junctions creation
    junctions = []
    for node_id, node in [ [n1,G.nodes[n1]] , [n2,G.nodes[n2]] ]:
        junctions.append(createJunction(node_id, node))

    # ways creation
    # hack : if an edge does not have a name, we name it "rue qui n'a pas de nom"
    if not "name" in edge:
        edge["name"] = "rue qui n'a pas de nom"
    way = Way(edge["osmid"], edge["name"], junctions, channels = [])

    # if n2 is a border node, it means the way is drawn as outgoing from the direction.
    way_out = None
    if border_nodes:
        way_out = True if n2 in border_nodes else False

    # does it have directed lanes ?
    if "lanes:backward" in edge and "lanes:forward" in edge:
        createDirectedLanes(edge, way, way_out)
    # does it have lanes ?
    elif "lanes" in edge:
        createUndirectedLanes(edge, way, way_out)
    else :
        if "oneway" in edge and edge["oneway"] == "no":
            createLane("Road", way, way_out)
            createLane("Road", way, not way_out)
        else:
            createLane("Road", way, way_out)

    return way