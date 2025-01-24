
import time

import .arenalib as alib

arena = alib.Arena()
dire=1
input()
for i in range(100):
    #dire = dire * -1
    arena.move_platform(10*dire)
    time.sleep(5)
