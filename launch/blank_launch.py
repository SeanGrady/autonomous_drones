import dronekit
from drone_scripts import drone_control
import time

SIMULATED=True

drone = None

try:
  if SIMULATED:
      drone = drone_control.Navigator(simulated=True)
  else:
      drone = drone_control.Navigator(simulated=False)

  drone.liftoff(10)

except KeyboardInterrupt:
  drone.stop()

