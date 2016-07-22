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
      drone.bringup_drone("udp:127.0.0.1:14550")
      while True:
        time.sleep(1)   # just let it get samples

  drone.arm_and_takeoff(15)

except KeyboardInterrupt:
  drone.stop()

