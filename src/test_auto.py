#!/usr/bin/env python

import point_follower
import time


# Simple test of the exploration function
# Drone tries to locate a source of gas using update_exploration to set new waypoints


my_drone = point_follower.AutoPilot(sim_speedup=3)
my_drone.bringup_drone()
my_drone.arm_and_takeoff(20)

while True:
    my_drone.update_exploration()
    time.sleep(1)

