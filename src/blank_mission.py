import dronekit
import drone_control

SIMULATED=True

drone = None

try:
  if SIMULATED:
      drone = drone_control.AutoPilot(simulated=True)
  else:
      drone = drone_control.AutoPilot(simulated=False)

  drone.start_and_takeoff(10)

except KeyboardInterrupt:
  drone.stop()
