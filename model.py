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
