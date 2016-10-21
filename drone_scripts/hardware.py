"""
File with 'drivers' for the various hardware peripherals the drone can have.
Currently everything except AirSensor is depricated pending updates to the
signal stuff.
"""
import threading
from threading import Thread
import json
import random
import math
import serial
import time
import drone_control
import dronekit
from subprocess import Popen, PIPE, call
import sys
from pubsub import pub
    

class AirSensor(threading.Thread):
    def __init__(self, simulated=False):
        '''
        Set up the fake air sensor
        Depending on where the vehicle is, send it believable data

        :param pilot: The :py:class:`Pilot` object that is receiving this data
                            We need to know this in order to log its location
        :return:
        '''
        super(AirSensor, self).__init__()
        self.daemon = True
        self._simulated = simulated
        self._delay = 5
        self._serial_speed = 9600
        self._serial_port = '/dev/ttyACM0'
        self._timeout = 1
        self._connection = None
        if not self._simulated:
            self.connect_to_sensor()
        self.start()

    def connect_to_sensor(self):
        try:
            self._connection = serial.Serial(
                    self._serial_port,
                    self._serial_speed,
                    timeout= self._timeout
            )
            self._connection.write('{"msg":"cmd","usb":1}')
        except serial.serialutil.SerialException as e:
            sys.stderr.write("Could not open serial for RealAirSensor\n")
            sys.stderr.write(e.__repr__())

    def _callback(self, air_data):
        pub.sendMessage("sensor-messages.air-data", arg1=air_data)

    def run(self):
        if not self._simulated:
            if self._connection is None:
                return
            while(True):
                data = self.get_reading()
                if data is not None:
                    #print "Got air sensor reading: {}".format(data)
                    self._callback(data)
        else:
            while(True):
                data = self.generate_fake_reading()
                #print "Got air sensor reading: {}".format(data)
                self._callback(data)
                time.sleep(self._delay / drone_control.Pilot.sim_speedup)

    def get_reading(self):
        while True:
            latest_raw = self._connection.readline()
            if latest_raw:
                try:
                    readings = json.loads(latest_raw)
                except Exception as e:
                    #print "JSON error"
                    return None
		return readings

    def generate_fake_reading(self):
        # fuction that will generate mostly ~410, occasionally higher
        raw = random.expovariate(1)
        reading = max(raw, 2) * 200 + random.uniform(5, 15)
        reading_dict = {"CO2":reading}
        return reading_dict
