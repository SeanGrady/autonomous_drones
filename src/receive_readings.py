import dronekit
import point_follower
import time

receiver = point_follower.AirSampleDB()
receiver.sync_from(6001)

try:
    while True:
        receiver.plot()
        time.sleep(5)
except KeyboardInterrupt:
    receiver.close()

