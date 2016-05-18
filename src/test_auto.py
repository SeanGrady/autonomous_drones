#!/usr/bin/env python

import point_follower
import time


# Simple test of the exploration function
# Drone tries to locate a source of gas using update_exploration to set new waypoints
#
#
drones = []
n=3
for i in xrange(n):
    drone = point_follower.AutoPilot(sim_speedup=2)
    drones.append(drone)
    drone.bringup_drone()
    drone.arm_and_takeoff(20)

while True:
    for drone in drones:
        drone.update_exploration()
    time.sleep(1)


# my_drone = point_follower.AutoPilot(sim_speedup=3)
# my_drone.bringup_drone()
# my_drone.arm_and_takeoff(20)
#
# drone2 = point_follower.AutoPilot()
# drone2.bringup_drone()
# drone2.arm_and_takeoff(20)
#
# while True:
#     my_drone.update_exploration()
#     drone2.update_exploration()
#     time.sleep(1)

