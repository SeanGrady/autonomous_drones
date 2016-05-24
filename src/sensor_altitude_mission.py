import dronekit
import drone_control
import time

SIMULATED=False

drone = None

try:
  if SIMULATED:
      drone = drone_control.AutoPilot(simulated=True)
      drone.bringup_drone()
  else:
      drone = drone_control.AutoPilot(simulated=False)
      while True:
        time.sleep(1)   # just let it get samples
      drone.bringup_drone("udp:127.0.0.1:14550")

  drone.arm_and_takeoff(5)

  for i in xrange(10):
      drone.goto_relative(0,0,i*2)
      time.sleep(10)
except KeyboardInterrupt:
  drone.stop()

