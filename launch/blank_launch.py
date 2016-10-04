import sys
'''
print sys.path
sys.path.insert(0, '/home/pi/drone_python/drone_scripts')
print sys.path
import drone_control
'''
from drone_scripts import drone_control
import dronekit
import time

SIMULATED=True
SIM_AIR_SENSOR=True

drone = None

try:
  drone = drone_control.Navigator(
          simulated=SIMULATED,
          simulated_air_sensor=SIM_AIR_SENSOR,
  )

  '''
  drone.liftoff(10)
  drone.load_mission('test_mission.json')
  drone.execute_mission()
  '''

except KeyboardInterrupt:
  drone.stop()

