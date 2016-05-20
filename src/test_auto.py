#!/usr/bin/env python

import point_follower
import time
import threading
import multiprocessing

# Simple test of the exploration function
# Drone tries to locate a source of gas using update_exploration to set new waypoints
#

def drone_explore_start(drone):
    drone.bringup_drone()
    drone.arm_and_takeoff(20)
    while True:
        drone.update_exploration()
        time.sleep(1)

def drone_bringup(drone):
    drone.bringup_drone()
    drone.arm_and_takeoff(20)

drones = []
threads = []
n=3
for i in xrange(n):
    drone = point_follower.AutoPilot(sim_speedup=2)
    drones.append(drone)
    drone_bringup(drone)
    # thread = threading.Thread(target=drone_explore_start,args=(drone, ))
    # thread.start()
    # threads.append(thread)

# for t in threads:
#     t.join()


while True:
    for drone in drones:
        drone.update_exploration()
    time.sleep(1)

