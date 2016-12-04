"""Read air quality data from a sensor connected to a USB port.

This script provides both an example of how to interact with the Terraswarm air
sensors and a means for reading data from them without launching an entire
drone.
"""
import serial
from pprint import pprint
import json
import time

class DataReceiver():
    """Provide a class for reading air sensor data."""

    def __init__(self):
        """Construct an instance of DataReceiver.

        The serial settings (speed, port and timeout) are configured for a
        Raspberry Pi 2. Running this on a laptop should work fine if you set
        the serial port accordingly.
        """
        self.serial_speed = 9600
        self.serial_port = '/dev/ttyACM0'
        self.connection = serial.Serial(
                self.serial_port,
                self.serial_speed,
                timeout=1
        )
        with open('sensor_data_log.txt', 'w') as wipe:
            pass
        self.connection.write('{"msg":"cmd","usb":1}')
        print self.connection.isOpen()

    def read_data_stream(self):
        """Write air sensor data to a file until a keyboard interrupt.

        This will keep reading data until interrupted, and will print the data
        to the screen as well as writing it to 'sensor_log.txt'. It looks kind
        of nasty because the air sensor is prone to random errors including but
        not limited to not outputting data, outputting errors, outputing random
        strings and outputting random integers. Rather than try to keep up with
        the changes I've just had it ignore anything that isn't valid JSON.
        """
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
        """Parse the data read by read_data_stream and write it to a file."""
        raw = data_object
        with open('sensor_log.txt', 'a') as infile:
            json.dump([raw, time.time()], infile)
            infile.write('\n')

if __name__ == "__main__":
    dr = DataReceiver()
    dr.read_data_stream()
