import threading
import json
import random
import math
import serial
import time
import drone_control
import dronekit
import numpy as np
from numpy.linalg import norm


class FakeSignalStatus(object):
    def __init__(self, autopilot):
        assert isinstance(autopilot, drone_control.AutoPilot)
        self._autopilot = autopilot
        self._pathloss_exp = 3.0    # Path loss exponent. Ideal=2, raise it for multipath and shadowing
        self._sig_d1 = -10          # Signal strength 1 meter away (dBm)

    def get_rssi(self):
        # Assume the base station is at the home location (0,0), alt=0
        loc = self._autopilot.get_local_location()
        if loc is None:
            return None
        assert isinstance(loc, dronekit.LocationLocal)

        # Get distance to home location, accounting for altitude
        dist = math.sqrt(loc.north**2 + loc.east**2 + loc.down**2)

        # Estimate strength based on free-space path loss
        signal = -10 - 10 * self._pathloss_exp * math.log10(dist)

        # Attenuate it even more based on directionality
        antenna = np.array([0.0, 1.0, 0.8])  # (x,y,z) point north and up
        drone = np.array([loc.east, loc.north, -loc.down])
        cos_angle = antenna.dot(drone) / (norm(antenna) * norm(drone))
        angle = abs(math.degrees(math.acos(cos_angle)))
        # Some made-up model
        if angle < 10:
            signal -= angle/2.0
        else:
            signal -= angle*2.0
        return signal


class FakeAirSensor(threading.Thread):
    def __init__(self, autopilot):
        '''
        Set up the fake air sensor
        Depending on where the vehicle is, send it believable data

        :param autopilot: The :py:class:`AutoPilot` object that we are passing fake data to
                            We need to know its location in order to calculate the fake plume
                            concentration at that location.
        :return:
        '''
        super(FakeAirSensor, self).__init__()
        self._autopilot = autopilot
        self._delay = 5

    def callback(self, fn):
        self._callback = fn

    def run(self):
        while(True):
            if self._callback:
                loc = self._autopilot.get_local_location()
                if loc is not None:
                    x,y = loc.east,loc.north

                    # Generate somewhat believable gas distribution
                    # Source is at (-40,-40)
                    reading = math.exp(-math.sqrt((x + 100) ** 2 + (y + 100) ** 2) / 40.0)
                    reading += random.gauss(0,0.01) # fuzz it up a little

                    # reading = max(, 0)
                    print "Got air sensor reading: {0}".format(reading)
                    self._callback(reading)
                    time.sleep(self._delay / drone_control.AutoPilot.sim_speedup)


class RealAirSensor(threading.Thread):
    def __init__(self, autopilot):
        '''
        Set up the fake air sensor
        Depending on where the vehicle is, send it believable data

        :param autopilot: The :py:class:`AutoPilot` object that is receiving this data
                            We need to know this in order to log its location
        :return:
        '''
        super(RealAirSensor, self).__init__()
        self._autopilot = autopilot
        self._delay = 5
        self._serial_speed = 9600
        self._serial_port = '/dev/ttyUSB0'
        self._timeout = 1
        self._connection = serial.Serial(
                self._serial_port,
                self._serial_speed,
                timeout= self._timeout
        )

    def callback(self, fn):
        self._callback = fn

    def run(self):
        while(True):
            if self._callback:
                AQI = self.get_AQI_reading()
                print "Got air sensor reading: {0}".format(AQI)
                self._callback(AQI)

    def get_AQI_reading(self):
        while True:
            latest_raw = self._connection.readline()
            if latest_raw:
                try:
                    readings = json.loads(latest_raw)
                    # print readings
                    AQI = readings['ppb']['AQI']
                    loc = self._autopilot.get_global_location()
                    # loc = self._autopilot.get_bullshit_location()
                    if loc is not None:
                        with open("log_all_things.json",'a') as outfile:
                            modded = {'RAW': readings, 'LOCATION': [loc.lat, loc.lon, loc.alt], 'TIME': time.time()}
                            print modded
                            json.dump(modded, outfile)
                    return AQI
                except Exception as e:
                    print "JSON error"
                    print e.__repr__()
