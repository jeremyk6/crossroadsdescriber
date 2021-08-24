#!/usr/bin/env python3

from model import *

j1 = Junction(0,1,2)

j2 = Junction(1,1,2)
j2 = Crosswalk(j2, True)
j2.cw_tactile_paving = False
j2 = Traffic_light(j2, [], "south")

j3 = Junction(2,1,2)

print(j1.type)
print(j2.cw_tactile_paving)
print(j3.type)