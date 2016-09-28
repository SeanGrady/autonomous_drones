import dronekit
from drone_scripts import drone_control
import time

SIMULATED=True

drone = None

try:
  if SIMULATED:
      drone = drone_control.Pilot(simulated=True)
      drone.bringup_drone()
  else:
      drone = drone_control.Pilot(simulated=False)
      drone.bringup_drone("udp:127.0.0.1:14550")
      while True:
        time.sleep(1)   # just let it get samples

  drone.arm_and_takeoff(5)

  for i in xrange(10):
      drone.goto_relative(0,0,i*1 + 5)
      time.sleep(10)
except KeyboardInterrupt:
  drone.stop()

