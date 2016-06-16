import dronekit
import drone_control

SIMULATED=True

drone = None

try:
  if SIMULATED:
      drone = drone_control.AutoPilot(simulated=True)
      drone.bringup_drone()
  else:
      drone = drone_control.AutoPilot(simulated=False)
      drone.bringup_drone("udp:127.0.0.1:14550")

  drone.arm_and_takeoff(10)

except KeyboardInterrupt:
  drone.stop()
