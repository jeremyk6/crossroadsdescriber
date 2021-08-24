
from . import utils as u

class LaneDescription:

    def __init__(self, angle, name, edge):
        self.angle = angle
        self.name = name
        self.edge = edge

    def is_similar(self, bd, angle_similarity = 90):
        if self.name == None or bd.name == None:
            return False
        if self.name != bd.name:
            return False

        if u.Util.angular_distance(self.angle, bd.angle) < angle_similarity:
            return True

        return False

    def is_orthogonal(self, angle, epsilon = 45):
        diff = u.Util.angular_distance(self.angle, angle)
        if diff >= 90 - epsilon and diff <= 90 + epsilon:
            return True
        return False

    def equals(self, edge):
        return (self.edge[0] == edge[0] and self.edge[1] == edge[1]) or \
                (self.edge[1] == edge[0] and self.edge[0] == edge[1])

    def __str__(self):
        return "%s : %s" % (self.name, self.angle)

    def __repr__(self):
        return self.__str__()