import dronekit
import drone_control
import time

receiver = drone_control.SampleDB(csv_file="speed_data_receive.csv")
receiver.sync_from(6001)

try:
    while True:
        receiver.plot()
        time.sleep(5)
except KeyboardInterrupt:
    receiver.close()

