import dronekit
import drone_control
import time

receiver = drone_control.AirSampleDB()
receiver.sync_from(6001)

try:
    while True:
        receiver.plot()
        time.sleep(5)
except KeyboardInterrupt:
    receiver.close()

