#!/usr/bin/env python

import point_follower
import dronekit
import random
import time

db = point_follower.AirSampleDB()
db.load("sample_data_run.json");
db.plot(block=True)

#
# while True:
#     db.plot()
#     db.record(dronekit.LocationLocal(random.gauss(0,50), random.gauss(0,50), -20),
#               max(random.gauss(0.5, 0.5), 0))
#     time.sleep(1)
