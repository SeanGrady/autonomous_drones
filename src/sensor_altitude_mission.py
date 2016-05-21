import dronekit
import point_follower
import time

SIMULATED=True

drone = None
if SIMULATED:
    drone = point_follower.AutoPilot(simulated=True)
    drone.bringup_drone()
else:
    drone = point_follower.AutoPilot(simulated=False)
    drone.bringup_drone("udp:127.0.0.1:14550")

drone.arm_and_takeoff(5)

for i in xrange(10):
    drone.goto_relative(0,0,i*2)
    time.sleep(10)

