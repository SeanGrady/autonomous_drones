import dronekit
import drone_control

SIMULATED=False
MASTER=True

drone = None

try:
    if SIMULATED:
        raise NotImplementedError
    elif MASTER:
        drone = drone_control.AutoPilot(simulated=False)
        drone.bringup_drone("udp:127.0.0.1:14550")
        drone.arm_and_takeoff(10)
        drone.master_exploration()
    else:
        drone = drone_control.AutoPilot(simulated=False)
        drone.bringup_drone("udp:127.0.0.1:14550")
        drone.arm_and_takeoff(10)
        drone.slave_exploration()


except KeyboardInterrupt:
    drone.stop()
