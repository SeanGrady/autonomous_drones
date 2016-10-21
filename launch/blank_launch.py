import sys
'''
sys.path.insert(0, '/home/pi/drone_python/drone_scripts')
import drone_control
'''
from drone_scripts import drone_control
import dronekit
import time

SIMULATED=False
SIM_AIR_SENSOR=True
SIM_RF_SENSOR=True

drone = None

try:
  drone = drone_control.Navigator(
          simulated=SIMULATED,
          simulated_RF_sensor=SIM_RF_SENSOR,
          simulated_air_sensor=SIM_AIR_SENSOR,
  )

  '''
  drone.liftoff(10)
  drone.load_mission('demo_mission.json')
  drone.execute_mission()
  '''

except KeyboardInterrupt:
  drone.stop()

