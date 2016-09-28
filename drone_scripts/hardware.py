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
    

class FakeSignalStatus(object):
    def __init__(self, pilot):
        assert isinstance(pilot, drone_control.Pilot)
        self._pilot = pilot
        self._pathloss_exp = 3.0    # Path loss exponent. Ideal=2, raise it for multipath and shadowing
        self._sig_d1 = -10          # Signal strength 1 meter away (dBm)

    def get_rssi(self):
        import numpy as np
        from numpy.linalg import norm
        # Assume the base station is at the home location (0,0), alt=0
        loc = self._pilot.get_local_location()
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

class SpeedTester(object):
    def __init__(self, pilot):
        self._callback = None

    def callback(self, fn):
        self._callback = fn

    def start(self):
        # Credit to:
        # http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python
        ON_POSIX = 'posix' in sys.builtin_module_names

        def report_output(self, out):
            for line in iter(out.readline, b''):
                if self._callback is not None:
                    self._callback(line)
            out.close()

        have_iperf = call("iperf -v", shell=True)
        if have_iperf != 1:
            sys.exit("You need to have iperf installed and accessible in your PATH in order to use"
                     "the speed tester.\n")

        p = Popen(['iperf', '-s', '-i', '1', '-p', '5010', '-y', 'c'], stdout=PIPE, bufsize=1, close_fds=ON_POSIX)
        t = Thread(target=report_output, args=(self, p.stdout, ))
        t.daemon = True
        t.start()


class FakeAirSensor(threading.Thread):
    def __init__(self, pilot):
        '''
        Set up the fake air sensor
        Depending on where the vehicle is, send it believable data

        :param pilot: The :py:class:`Pilot` object that we are passing fake data to
                            We need to know its location in order to calculate the fake plume
                            concentration at that location.
        :return:
        '''
        super(FakeAirSensor, self).__init__()
        self._pilot = pilot
        self._delay = 5

    def callback(self, fn):
        self._callback = fn

    def run(self):
        while(True):
            if self._callback:
                loc = self._pilot.get_local_location()
                if loc is not None:
                    x,y = loc.east,loc.north

                    # Generate somewhat believable gas distribution
                    # Source is at (-40,-40)
                    reading = math.exp(-math.sqrt((x + 100) ** 2 + (y + 100) ** 2) / 40.0)
                    reading += random.gauss(0,0.01) # fuzz it up a little

                    # reading = max(, 0)
                    print "Got air sensor reading: {0}".format(reading)
                    self._callback(reading)
                    time.sleep(self._delay / drone_control.Pilot.sim_speedup)


class AirSensor(threading.Thread):
    def __init__(self, pilot, simulated=False):
        '''
        Set up the fake air sensor
        Depending on where the vehicle is, send it believable data

        :param pilot: The :py:class:`Pilot` object that is receiving this data
                            We need to know this in order to log its location
        :return:
        '''
        super(AirSensor, self).__init__()
        self.daemon = True
        self._pilot = pilot
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
                    return readings
                except Exception as e:
                    print "JSON error"
                    print e.__repr__()
                    return None

    def generate_fake_reading(self):
        x, y = random.uniform(-50, 50), random.uniform(-50, 50)
        # Generate somewhat believable gas distribution
        # Source is at (-40,-40)
        reading = math.exp(-math.sqrt((x + 100) ** 2 + (y + 100) ** 2) / 40.0)
        reading += random.gauss(0,0.01) # fuzz it up a little

        reading_dict = {"fake_reading":reading}
        return reading_dict

