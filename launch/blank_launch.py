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
  drone.load_mission('test_mission.json')
  drone.execute_mission()

except KeyboardInterrupt:
  drone.stop()

