import dronekit
from dronekit import connect, VehicleMode
import dronekit_sitl
import time
import math
import argparse
from nav_utils import relative_to_global, get_distance_meters, Waypoint, read_wp_file
import nav_utils
import threading
import random
import json
import tempfile
import multiprocessing
import socket
import Queue
import cPickle
import time
import sys
import serial

class FakeAirSensor(threading.Thread):
    def __init__(self, autopilot):
        '''
        Set up the fake air sensor
        Depending on where the vehicle is, send it believable data

        :param autopilot: The :py:class:`AutoPilot` object that we are passing fake data to
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
                    time.sleep(self._delay / AutoPilot.sim_speedup)


class RealAirSensor(threading.Thread):
    def __init__(self, autopilot):
        '''
        Set up the fake air sensor
        Depending on where the vehicle is, send it believable data

        :param autopilot: The :py:class:`AutoPilot` object that we are passing fake data to
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


class AirSample(object):
    num_values = 5

    @staticmethod
    def load(pickled):
        array = cPickle.loads(pickled)
        if len(array) != AirSample.num_values:
            return None
        return AirSample(data=array)

    def __init__(self, location=None, value=None, data=None):
        if location is not None and value is not None:
            assert isinstance(location, dronekit.LocationGlobal)
            self._data = [location.lat,
                          location.lon,
                          location.alt,
                          value,
                          time.time()]
        else:
            assert data is not None
            assert len(data)==AirSample.num_values
            self._data = data

    def __eq__(self, other):
        if hasattr(other, "_data"):
            return self._data == other._data
        return False

    def __str__(self):
        return "({0}, {1}) {2}m value={3}".format(self.lat,
                                                  self.lon,
                                                  self.altitude,
                                                  self.value)

    def dump(self):
        return cPickle.dumps(self._data, protocol=2)

    @property
    def data(self):
        return self._data[:]

    @property
    def lat(self):
        return self._data[0]

    @property
    def lon(self):
        return self._data[1]

    @property
    def altitude(self):
        return self._data[2]

    @property
    def value(self):
        return self._data[3]

    @property
    def timestamp(self):
        return self._data[4]

    @timestamp.setter
    def timestamp(self, new):
        self._data[4] = new

    def distance(self, other):
        assert isinstance(other, AirSample)
        return nav_utils.lat_lon_distance(self._data[0], self._data[1],
                                          other._data[0], other._data[1])


class AirSampleDB(object):
    """
    A place to store and easily retrieve recorded air samples

    For now, the data structure is just an array
    """

    def __init__(self):
        self._data_points = []
        self._lock_db = threading.Lock()
        self._send_thread = None
        self._keep_send_thread_alive = None
        self._recv_thread = None
        self._keep_recv_thread_alive = None
        self._samples_to_send = None
        self.matplotlib_imported = False

    def __len__(self):
        return len(self._data_points)

    def record(self, air_sample):
        assert isinstance(air_sample, AirSample)
        self._lock_db.acquire()
        if air_sample not in self._data_points:
            self._data_points.append(air_sample)
            self.save()
            print "recorded sample {0}".format(air_sample)
            print "{0} {1}".format(self, len(self))
            if self._samples_to_send is not None:
                try:
                    self._samples_to_send.put(air_sample, block=False)
                    print "queue size {0}".format(self._samples_to_send.qsize())
                except Queue.Full:
                    pass
        else:
            sys.stderr.write("Already sampled {0}, not recording it again\n".format(air_sample))
        self._lock_db.release()


    def max_sample(self):
        self._lock_db.acquire()
        m=None
        if len(self) > 0:
            m = max(self._data_points, key=lambda v: v.value)
        self._lock_db.release()
        return m

    def min_sample(self):
        self._lock_db.acquire()
        m = None
        if len(self) > 0:
            m = min(self._data_points, key=lambda v: v.value)
        self._lock_db.release()
        return m

    def average(self):
        self._lock_db.acquire()
        avg = None
        if len(self) > 0:
            avg = reduce(lambda s,v: s+v.value, self._data_points) / len(self)
        self._lock_db.release()
        return avg

    def sync_from(self, port):
        """
        Receive samples on this port
        Send acknowledgements to port+1 (for testing on localhost)

        :param port:
        :return:
        """
        self._keep_recv_thread_alive = threading.Event()
        self._keep_recv_thread_alive.set()
        self._recv_thread = threading.Thread(target=AirSampleDB.recv_thread_entry,
                                             args=(self, port, ))
        self._recv_thread.start()

    def recv_thread_entry(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.bind(("", port))
        while self._keep_recv_thread_alive.is_set():
            try:
                data, (ip, recv_port) = sock.recvfrom(1024)
                print "got {0} from {1}, i am {2}".format(data, (ip, recv_port), self)
                sock.sendto("ACK", (ip, port+1))
                air_sample = AirSample.load(data)
                if air_sample is not None:
                    print "sample {0}".format(air_sample)
                    self.record(air_sample)
                else:
                    sys.stderr.write("Bad air sample\n")
            except socket.timeout:
                pass
        sock.close()
        print "recv thread done"

    def sync_to(self, ip, port):
        """
        Send values over UDP to specified IP and port
        Another AirSampleDB will have called sync_from and will receive this data
        It will acknowledge on port+1

        :param ip:
        :param port:
        :return:
        """

        self._lock_db.acquire()     # Prevent record() from doing anything while we change stuff

        if self._send_thread is not None:
            # Kill existing thread
            self._keep_send_thread_alive.clear()
            timeout = time.time() + 10
            while self._send_thread.is_alive() and time.time() < timeout:
                pass
            assert time.time() < timeout, "Thread won't die!"
        self._samples_to_send = Queue.Queue(maxsize=10)
        self._keep_send_thread_alive = threading.Event()
        self._keep_send_thread_alive.set()
        self._send_thread = threading.Thread(target=AirSampleDB.send_thread_entry,
                                             args=(self, ip, port, ))
        self._send_thread.start()

        self._lock_db.release()

    def send_thread_entry(self, ip, port):
        print "started send thread"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.bind(("", port + 1))
        item = None
        while self._keep_send_thread_alive.is_set():
            try:
                item = self._samples_to_send.get(block=False, timeout=0.2)
            except Queue.Empty:
                continue
            assert isinstance(item, AirSample)
            print "sending to {0} {1}".format(ip, port)
            sock.sendto(item.dump(), (ip, port))
            data, ip_recv, port_recv=None, None, None
            try:
                data, (ip_recv, port_recv) = sock.recvfrom(4)
            except socket.timeout:
                pass
            if data=="ACK" and ip_recv == ip:
                print "got ack"
            else:
                print "No ack, got {0} from {1}".format(data, ip_recv)
                try:
                    self._samples_to_send.put(item, block=False)
                except Queue.Full:
                    pass
        sock.close()
        print "send thread done"

    def close(self):
        """
        Kill all the threads gracefully
        :return:
        """
        if self._keep_recv_thread_alive is not None:
            self._keep_recv_thread_alive.clear()
            print "recv closing..."
        if self._keep_send_thread_alive is not None:
            self._keep_send_thread_alive.clear()
            print "send closing..."
        timeout = time.time() + 10
        while time.time() < timeout:
            send_dead = self._send_thread is None or not self._send_thread.is_alive()
            recv_dead = self._recv_thread is None or not self._recv_thread.is_alive()
            if send_dead and recv_dead:
                break
        if time.time() >= timeout:
            sys.stderr.write("send/receive threads did not close graceully!\n")
            return False
        return True


    def plot(self, block=False):
        import numpy as np
        from matplotlib.mlab import griddata
        import matplotlib.pyplot as plt
        self.matplotlib_imported = True

        if len(self._data_points) < 5:
            return
        coords = [np.array([d.lat, d.lon]) for d in self._data_points]
        z = [d.value for d in self._data_points]
        lower_left = np.minimum.reduce(coords)
        upper_right = np.maximum.reduce(coords)
        print np.linalg.norm(upper_right - lower_left)
        if np.linalg.norm(upper_right - lower_left) < 0.0001:
            return  # Points are not varied enough to plot

        # fig, ax = plt.subplot(1,1)
        plt.clf()
        x = [c[0] for c in coords]
        y = [c[1] for c in coords]
        xi = np.linspace(lower_left[0], upper_right[0], 200)
        yi = np.linspace(lower_left[1], upper_right[1], 200)
        zi = griddata(x, y, z, xi, yi)
        CS = plt.contour(xi, yi, zi, 15, linewidths=0.5, colors='k')
        CS = plt.contourf(xi, yi, zi, 15, cmap=plt.cm.rainbow,
                  vmax=abs(zi).max(), vmin=-abs(zi).max())
        plt.scatter(x, y, marker='o', c='b', s=5, zorder=10)
        plt.xlim(lower_left[0], upper_right[0])
        plt.ylim(lower_left[1], upper_right[1])
        plt.title('Air data samples')
        if block:
            plt.plot()
            plt.show()
        else:
            plt.pause(0.05)

    def save(self, filename="sensor_data.json"):
        with open(filename, 'w') as data_file:
            data = map(lambda s:  s.data, self._data_points)
            json.dump(data, data_file, indent=True)

    def load(self, filename="sensor_data.json"):
        with open(filename) as data_file:
            data = json.load(data_file)
            if data is not None:
                self._data_points = map(lambda d: AirSample(data=d), data)
            else:
                self._data_points = []

class AutoPilot(object):
    sim_speedup = 1
    instance = -1
    # global_db = AirSampleDB()
    #
    # # When simulating swarms, prevent multiple processes from doing strange things
    # lock_db = multiprocessing.Lock()

    def __init__(self, simulated=False, sim_speedup = None):
        AutoPilot.instance += 1
        self.instance = AutoPilot.instance
        self.groundspeed = 7
        if sim_speedup is not None:
            AutoPilot.sim_speedup = sim_speedup     # Everyone needs to go the same speed
            simulated = True

        # Altitude relative to starting location
        # All further waypoints will use this altitude
        self.hold_altitude = 5
        self.vehicle = None
        self.sitl = None
        if simulated:
            self.air_sensor = FakeAirSensor(self)
        else:
            self.air_sensor = RealAirSensor(self)
        self.air_sensor.daemon = True

        self.sensor_readings = AirSampleDB()
        self.sensor_readings.sync_to("192.168.1.88", 6001)

        @self.air_sensor.callback
        def got_air_sample(value):
            loc = self.get_global_location()
            # loc = self.get_bullshit_location()
            if loc is not None:
                self.sensor_readings.record(AirSample(loc, value))

        self.air_sensor.start()

    def update_exploration(self):
        """
        Pick another waypoint to explore

        Algorithm right now is very simple:
        Find the coordinate of the highest gas value that we've recorded so far
        Perturb that coordinate randomly
        Go to perturbed coordinate

        :return:
        """
        if self.get_local_location() is None:
            return

        waypoint = None
        if len(self.sensor_readings) == 0:
            waypoint = Waypoint(self.vehicle.location.global_relative_frame.lat,
                                self.vehicle.location.global_relative_frame.lon,
                                self.hold_altitude)
        else:
            # Find the place with the maximum reading
            max_place = self.sensor_readings.max_sample()
            waypoint = Waypoint(max_place.lat,
                                max_place.lon,
                                self.hold_altitude)
            self.sensor_readings.save()

        sigma = 0.0001
        new_wp = Waypoint(random.gauss(waypoint.lat,sigma),
                        random.gauss(waypoint.lon,sigma),
                        waypoint.alt_rel)
        print "Drone {0} exploring new waypoint at {1}".format(self.instance, new_wp)
        self.goto_waypoint(new_wp)


    def run_mission(self):
        self.load_waypoints()
        self.start_wp()
        self.goto_waypoints()
        self.RTL_and_land()

    def load_waypoints(self):
        waypoint_list = read_wp_file()
        self.waypoints = []
        for NED in waypoint_list:
            self.waypoints.append(Waypoint(NED[0], NED[1], NED[2]))

    def start_wp(self):
        self.bringup_drone()
        self.arm_and_takeoff(15)
        print "altitude: " + str(self.vehicle.location.local_frame.down)

    def goto_waypoints(self):
        for wp in self.waypoints:
            self.goto_waypoint(wp)

    def bringup_drone(self, connection_string = None):
        """
        Call this once everything is set up and you're ready to fly

        :param connection_string: Connect to an existing mavlink (SITL or the actual ArduPilot)
                                  Provide None and it'll start its own simulator
        :return:
        """
        if not connection_string:
            # Start SITL if no connection string specified
            print "Starting SITL"
            self.sitl = dronekit_sitl.SITL()
            self.sitl.download('copter','3.3',verbose=True)
            sitl_args = ['--model', 'quad',
                         '--home=32.990756,-117.128362,243,0',
                         '--speedup', str(AutoPilot.sim_speedup),
                         '--instance', str(self.instance)]
            working_dir = tempfile.mkdtemp()
            self.sitl.launch(sitl_args,
                             verbose=True,
                             await_ready=True,
                             restart=True,
                             wd=working_dir)
            time.sleep(6)  # Allow time for the parameter to go back to EEPROM
            connection_string = "tcp:127.0.0.1:{0}".format(5760 + 10*self.instance)
            new_sysid = self.instance + 1
            vehicle = connect(connection_string, wait_ready=True)
            while vehicle.parameters["SYSID_THISMAV"] != new_sysid:
                vehicle.parameters["SYSID_THISMAV"] = new_sysid
                time.sleep(0.1)
            time.sleep(5)   # allow eeprom write
            vehicle.close()
            self.sitl.stop()
            # Do it again, and this time SYSID_THISMAV will have changed
            self.sitl.launch(sitl_args,
                             verbose=True,
                             await_ready=True,
                             restart=True,
                             use_saved_data=True,
                             wd=working_dir)
        else:
            # Connect to existing vehicle
            print 'Connecting to vehicle on: %s' % connection_string
        print "Connect to {0}, instance {1}".format(connection_string, self.instance)
        self.vehicle = connect(connection_string, wait_ready=True)
        print "Success {0}".format(connection_string)

    def stop(self):
        self.sensor_readings.close()

    def arm_and_takeoff(self, aTargetAltitude):
        """
        Arm vehicle and fly to aTargetAltitude.
        """
        self.hold_altitude = aTargetAltitude
        print "Basic pre-arm checks"
        # Don't try to arm until autopilot is ready
        while not self.vehicle.is_armable:
            print " Waiting for vehicle {0} to initialise...".format(self.instance)
            time.sleep(1.0 / AutoPilot.sim_speedup)

        print "Getting vehicle commands"
        cmds = self.vehicle.commands
        cmds.download()
        cmds.wait_ready()

        print "Home location is " + str(self.vehicle.home_location)

        print "Arming motors"
        # Copter should arm in GUIDED mode
        self.vehicle.mode = VehicleMode("GUIDED")
        self.vehicle.armed = True

        # Confirm vehicle armed before attempting to take off
        while not self.vehicle.armed:
            print " Waiting for vehicle {0} to arm...".format(self.instance)
            self.vehicle.mode = VehicleMode("GUIDED")
            self.vehicle.armed = True
            time.sleep(1.0 / AutoPilot.sim_speedup)

        print "Taking off!"
        self.vehicle.simple_takeoff(aTargetAltitude) # Take off to target alt

        # Wait until the self.vehicle reaches a safe height before processing
        # the goto (otherwise the command after Vehicle.simple_takeoff will
        # execute immediately).
        while True:
            print "Vehicle {0} altitude: {1}".format(self.instance,
                                                     self.vehicle.location.global_relative_frame.alt)
            #Break and return from function just below target altitude.
            if (self.vehicle.location.global_relative_frame.alt >= 
                aTargetAltitude*0.90):
                print "Reached target altitude"
                break
            time.sleep(1.0 / AutoPilot.sim_speedup)

    def poll(self):
        return "Location: " + str(self.vehicle.location.local_frame)

    def get_local_location(self):
        if self.vehicle is not None and self.vehicle.location is not None:
            loc = self.vehicle.location.local_frame
            if loc.north is not None and loc.east is not None:
                return self.vehicle.location.local_frame
        return None

    def get_global_location(self):
        if self.vehicle is not None and self.vehicle.location is not None:
            loc = self.vehicle.location.global_frame
            if loc.lat is not None and loc.lon is not None:
                return self.vehicle.location.global_frame
        return None

    def get_bullshit_location(self):
        return dronekit.LocationGlobal(random.gauss(0,10),random.gauss(0,10),random.gauss(20,5))

    def goto_relative(self, north, east, altitude):
        location = relative_to_global(self.vehicle.home_location,
                                      north,
                                      east,
                                      altitude)
        self.goto_global_rel(location)

    def goto_waypoint(self, wp):
        '''
        Go to a waypoint and block until we get there
        :param wp: :py:class:`Waypoint`
        :return:
        '''
        # global_rel = self.wp_to_global_rel(wp)
        global_rel = dronekit.LocationGlobalRelative(wp.lat, wp.lon, wp.alt_rel)
        self.goto_global_rel(global_rel)

    def wp_to_global_rel(self, waypoint):
        waypoint_global_rel = relative_to_global(
                self.vehicle.home_location,
                waypoint.dNorth,
                waypoint.dEast,
                waypoint.alt_rel
                )
        return waypoint_global_rel

    def goto_global_rel(self, global_relative):
        offset = get_distance_meters(
                self.vehicle.location.global_relative_frame,
                global_relative
                )
        self.vehicle.simple_goto(global_relative, groundspeed=self.groundspeed)
        grf = self.vehicle.location.global_relative_frame
        alt_offset = abs(grf.alt - global_relative.alt)
        while offset > 2 and alt_offset > 0.8 and self.vehicle.mode.name == "GUIDED":
            grf = self.vehicle.location.global_relative_frame
            offset = get_distance_meters(grf, global_relative)
            alt_offset = abs(grf.alt - global_relative.alt)
            time.sleep(1)
        print "Arrived at global_relative."

    def RTL_and_land(self):
        home_hover = relative_to_global(
                self.vehicle.home_location,
                0,
                0,
                15
                )
        self.goto_global_rel(home_hover)
        self.vehicle.mode = VehicleMode("LAND")
        self.shutdown_vehicle()

    def shutdown_vehicle(self):
        #Close vehicle object before exiting script
        print "Closing vehicle"
        self.vehicle.close()
