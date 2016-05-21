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
n=1
for i in xrange(n):
    drone = point_follower.AutoPilot(simulated=True, sim_speedup=1)
    drones.append(drone)
    drone_bringup(drone)

sensor_db = point_follower.AirSampleDB()
sensor_db.sync_from(6001)

while True:
    for drone in drones:
        drone.update_exploration()
    time.sleep(1)

