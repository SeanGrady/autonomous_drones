import sys
print sys.path
sys.path.insert(0, '/home/pi/drone_python/drone_scripts')
print sys.path
import dronekit
import drone_control
import time

SIMULATED=False

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

