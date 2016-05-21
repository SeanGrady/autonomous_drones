import serial
from pprint import pprint
import json
import time

class DataReceiver():
    def __init__(self):
        self.serial_speed = 9600
        self.serial_port = '/dev/tty.usbserial-A602Z731'
        self.connection = serial.Serial(
                self.serial_port,
                self.serial_speed,
                timeout=1
        )
        with open('sensor_log.txt', 'w') as wipe:
            pass
        print self.connection.isOpen()

    def read_data_stream(self):
        try:
            while True:
                latest_raw = self.connection.readline()
                print latest_raw.strip('\n')
                if latest_raw:
                    try:
                        latest_readings = json.loads(latest_raw)
                        self.parse_data(latest_readings)
                        print "JSON success"
                    except:
                        print "JSON error"
                else:
                    print "No data packet"
        except KeyboardInterrupt:
            pass

    def parse_data(self, data_object):
        raw = data_object
        with open('sensor_log.txt', 'a') as infile:
            json.dump([raw, time.time()], infile)
            infile.write('\n')

if __name__ == "__main__":
    dr = DataReceiver()
    dr.read_data_stream()
