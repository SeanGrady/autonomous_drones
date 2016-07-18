import dronekit
import drone_control

SIMULATED=True

drone = None

try:
    if SIMULATED:
        navigator = drone_control.Navigator(simulated=True)
    else:
        navigator = drone_control.Navigator(simulated=False)

    navigator.liftoff(10)
    navigator.run_mission()

except KeyboardInterrupt:
    drone.stop()
