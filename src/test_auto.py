#!/usr/bin/env python

import point_follower
import time

my_drone = point_follower.AutoPilot()
my_drone.bringup_drone()
my_drone.arm_and_takeoff(20)


while True:
    my_drone.update_exploration()
    time.sleep(1)

