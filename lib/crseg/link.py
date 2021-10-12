
import osmnx as ox

from . import reliability as rl
from . import region as r
from . import utils as u
from . import lane_description as ld


class Link(r.Region):
    
    def __init__(self, G, node1 = None, node2 = None, target_id = -1):
        r.Region.__init__(self, G, target_id)
        if node1 != None:
            self.add_node(node1)
            self.filled = False
            if node2 != None:
                if G.nodes[node2][r.Region.label_region] != -1:
                    self.filled = True
                self.add_node(node2)
                self.add_edge((node1, node2))

    def is_link(self):
        return True

    def propagate(self):
        # only propagate if this link is not filled
        if not self.filled and len(self.nodes) > 0:
            start = self.nodes[-1]
            self.propagate_from_node(start)
    
    def propagate_from_node(self, start):
        for nb in self.G.neighbors(start):
            if self.G[start][nb][0][r.Region.label_region] == -1:
                open = self.G.nodes[nb][r.Region.label_region] == -1
                self.add_node(nb)
                self.add_edge((start, nb))
                if open:
                    self.propagate_from_node(nb)
