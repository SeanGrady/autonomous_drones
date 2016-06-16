import dronekit
from dronekit import connect, VehicleMode
import dronekit_sitl
from nav_utils import relative_to_global, get_ground_distance, Waypoint
import nav_utils
import threading
import random
import json
import tempfile
import socket
import Queue
import cPickle
import time
import sys
import hardware
import csv


class LocationSample(object):
    """
    One sample of data at a particular drone location

    Examples of data: air quality index, bandwidth (mbps)

    Can also store the drone's attitude and velocity at that location
    """

    num_values = 11

    @staticmethod
    def load(pickled):
        array = cPickle.loads(pickled)
        if len(array) != LocationSample.num_values:
            return None
        return LocationSample(data=array)

    def __init__(self, location=None, value=None, attitude=None, velocity=None, data=None):
        if location is not None and value is not None:
            assert isinstance(location, dronekit.LocationGlobal)
            self._data = [location.lat,
                          location.lon,
                          location.alt,
                          value,
                          time.time()]
            if attitude is not None:
                assert isinstance(attitude, dronekit.Attitude)
                self._data += [attitude.pitch, attitude.roll, attitude.yaw]
            else:
                self._data += [0, 0, 0]

            if velocity is not None:
                assert len(velocity) == 3
                self._data += velocity
            else:
                self._data += [0, 0, 0]
        else:
            assert data is not None
            assert len(data) == LocationSample.num_values
            self._data = data

    def __eq__(self, other):
        if hasattr(other, "_data"):
            return self._data == other._data
        return False

    def __str__(self):
        return "({0}, {1}) {2}m value={3},roll,pitch,yaw={4},{5},{6}".format(self.lat,
                                                                             self.lon,
                                                                             self.altitude,
                                                                             self.value,
                                                                             self.roll,
                                                                             self.pitch,
                                                                             self.yaw)

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

    @property
    def roll(self):
        return self._data[5]

    @property
    def pitch(self):
        return self._data[6]

    @property
    def yaw(self):
        return self._data[7]

    @timestamp.setter
    def timestamp(self, new):
        self._data[4] = new

    def distance(self, other):
        assert isinstance(other, LocationSample)
        return nav_utils.lat_lon_distance(self._data[0], self._data[1],
                                          other._data[0], other._data[1])


class SampleDB(object):
    """
    A place to store and easily retrieve recorded samples associated with a lat/lon

    For now, the data structure is just an array
    """

    def __init__(self, json_file="sensor_data.csv", csv_file=None):
        self._json_file = json_file
        self._csv_file = csv_file
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

    def record(self, sample):
        """
        Record a data point, and transmit it to the remote receiver if desired
        Also log it to a CSV

        :param sample: :py:class:`LocationSample`
        :return:
        """
        assert isinstance(sample, LocationSample)
        self._lock_db.acquire()
        if sample not in self._data_points:
            self._data_points.append(sample)
            if self._csv_file is not None:
                with open(self._csv_file, 'ab') as file:
                    writer = csv.writer(file)
                    writer.writerow(sample._data)
            self.save_json()
            print "recorded sample {0}".format(sample)
            if self._samples_to_send is not None:
                try:
                    self._samples_to_send.put(sample, block=False)
                    print "queue size {0}".format(self._samples_to_send.qsize())
                except Queue.Full:
                    pass
        else:
            sys.stderr.write("Already sampled {0}, not recording it again\n".format(sample))
        self._lock_db.release()

    def max_sample(self):
        self._lock_db.acquire()
        m = None
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
            avg = reduce(lambda s, v: s + v.value, self._data_points) / len(self)
        self._lock_db.release()
        return avg

    def sync_from(self, port):
        """
        Receive samples on this port
        Send acknowledgements to port+1 (for testing on localhost)

        :param port:
        :return:
        """

        # TODO: close old one if we sync to new port
        self._keep_recv_thread_alive = threading.Event()
        self._keep_recv_thread_alive.set()
        self._recv_thread = threading.Thread(target=SampleDB._recv_thread_entry,
                                             args=(self, port,))
        self._recv_thread.daemon = True
        self._recv_thread.start()

    def _recv_thread_entry(self, port):
        """
        Thread entry method to receive stuff
        :return:
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        sock.bind(("", port))
        while self._keep_recv_thread_alive.is_set():
            try:
                data, (ip, recv_port) = sock.recvfrom(1024)
                # print "got {0} from {1}, i am {2}".format(data, (ip, recv_port), self)
                sock.sendto("ACK", (ip, port + 1))
                air_sample = LocationSample.load(data)
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

        self._lock_db.acquire()  # Prevent record() from doing anything while we change stuff

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
        self._send_thread = threading.Thread(target=SampleDB._send_thread_entry,
                                             args=(self, ip, port,))
        self._send_thread.daemon = True
        self._send_thread.start()

        self._lock_db.release()

    def _send_thread_entry(self, ip, port):
        """
        Thread entry to send stuff
        :param ip: ip address to send to
        :param port: port
        :return:
        """
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
            assert isinstance(item, LocationSample)
            print "sending to {0} {1}".format(ip, port)
            sock.sendto(item.dump(), (ip, port))
            data, ip_recv, port_recv = None, None, None
            try:
                data, (ip_recv, port_recv) = sock.recvfrom(4)
            except socket.timeout:
                pass
            if data == "ACK" and ip_recv == ip:
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

    def plot(self, block=False, time=0.05):
        """
        Plot the currently stored data as a contour plot using matplotlib

        In the plot:
        x,y are lon, lat
        z is the sensor value for that location

        :param block:
        :return:
        """
        import numpy as np
        from matplotlib.mlab import griddata
        import matplotlib.pyplot as plt
        self.matplotlib_imported = True

        if len(self._data_points) < 5:
            return
        try:
            all = [[d.lon, d.lat, d.value] for d in self._data_points]
            all.sort()
            delete = []
            for i in xrange(len(all) - 1):
                if all[i][0:2] == all[i + 1][0:2]:
                    delete.append(i)
            for i in reversed(delete):
                all.pop(i)
            print "Removed {0} duplicates for plotting".format(len(delete))
            coords = [np.array(a[0:2]) for a in all]
            z = [a[2] for a in all]

            first = z[0]
            all_same = True
            for val in z:
                if val != first:
                    all_same = False
                    break
            if all_same:
                print "all values are the same, not plotting"
                return

            lower_left = np.minimum.reduce(coords)
            upper_right = np.maximum.reduce(coords)
            print np.linalg.norm(upper_right - lower_left)
            if np.linalg.norm(upper_right - lower_left) < 0.00001:
                print "points are not varied enough, not plotting"
                return  # Points are not varied enough to plot

            # fig, ax = plt.subplot(1,1)
            plt.clf()
            x = [c[0] for c in coords]
            y = [c[1] for c in coords]
            xi = np.linspace(lower_left[0], upper_right[0], 200)
            yi = np.linspace(lower_left[1], upper_right[1], 200)
            zi = griddata(x, y, z, xi, yi)
            CS_lines = plt.contour(xi, yi, zi, 15, linewidths=0.5, colors='k')
            CS_colors = plt.contourf(xi, yi, zi, 15, cmap=plt.cm.rainbow,
                                     vmax=abs(zi).max(), vmin=-abs(zi).max())
            cbar = plt.colorbar(CS_colors)
            cbar.ax.set_ylabel("Value")
            cbar.add_lines(CS_lines)
            plt.scatter(x, y, marker='o', c='b', s=5, zorder=10)
            plt.xlim(lower_left[0], upper_right[0])
            plt.ylim(lower_left[1], upper_right[1])
            plt.title('Air data samples')
            plt.xlabel("Longitude")
            plt.ylabel("Latitude")
            if block:
                plt.plot()
                plt.show()
            else:
                plt.pause(time)
        except ValueError as e:
            print e.__repr__()  # STFU

    def save_json(self, filename=None):
        """
        Dump all the data points to a JSON file
        :param filename:
        :return:
        """
        if filename is None:
            if self._json_file is None:
                return
            filename = self._json_file
        with open(filename, 'w') as data_file:
            data = map(lambda s: s.data, self._data_points)
            json.dump(data, data_file, indent=True)

    def save_csv(self):
        raise NotImplementedError("TODO")

        # Just dump lat, lon, value
        with open("data.csv", 'wb') as csvfile:
            writer = csv.writer(csvfile)
            for s in self._data_points:
                writer.writerow([s.lat, s.lon, s.value])

    def load(self, filename="sensor_data.json"):
        with open(filename) as data_file:
            data = json.load(data_file)
            if data is not None:
                self._data_points = map(lambda d: LocationSample(data=d), data)
            else:
                self._data_points = []


class AutoPilot(object):
    sim_speedup = 1
    instance = -1

    # global_db = AirSampleDB()
    #
    # # When simulating swarms, prevent multiple processes from doing strange things
    # lock_db = multiprocessing.Lock()

    def __init__(self, simulated=False, sim_speedup=None):
        """

        :param simulated: Are we running this on the simulator? (using dronekit_sitl python)
        :param sim_speedup: Factor to speed up the simulator, e.g. 2.0 = twice as fast.
                            Somewhat glitchy on higher values
        """
        AutoPilot.instance += 1
        self._waypoint_index = 0
        self.instance = AutoPilot.instance
        self.groundspeed = 7
        if sim_speedup is not None:
            AutoPilot.sim_speedup = sim_speedup  # Everyone needs to go the same speed
            simulated = True

        # Altitude relative to starting location
        # All further waypoints will use this altitude
        self.hold_altitude = None

        self.vehicle = None
        self.sitl = None
        if simulated:
            self.air_sensor = hardware.FakeAirSensor(self)
            self.signal_status = hardware.FakeSignalStatus(self)
        else:
            self.air_sensor = hardware.RealAirSensor(self)
            self.signal_status = None  # TODO: actual wifi signal strengths
        self.air_sensor.daemon = True

        self.sensor_readings = SampleDB(json_file="air_samples.json", csv_file=None)

        # self.sensor_readings.sync_to("192.168.1.88", 6001)

        @self.air_sensor.callback
        def got_air_sample(value):
            loc = self.get_global_location()
            # loc = self.get_bullshit_location()
            if loc is not None:
                self.sensor_readings.record(LocationSample(loc, value))

        self.air_sensor.start()

        self.speed_readings = SampleDB(json_file=None, csv_file="speed_data.csv")
        if simulated:
            self.speed_readings.sync_to("127.0.0.1", 6001)
        else:
            self.speed_readings.sync_to("192.168.1.88", 6001)

        self.speed_test = hardware.SpeedTester(self)

        @self.speed_test.callback
        def got_speed_reading(line):
            bps = float(line.split(",")[-1])  # Last value is bits per second
            loc = self.get_global_location()
            att = self.get_attitude()
            vel = self.get_velocity()
            if loc is not None and att is not None:
                self.speed_readings.record(LocationSample(loc, bps, att, vel))
            print "bits per second: " + str(bps)

        self.speed_test.start()

    def naive_exploration(self):
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
            self.sensor_readings.save_json()

        sigma = 0.0001
        new_wp = Waypoint(random.gauss(waypoint.lat, sigma),
                          random.gauss(waypoint.lon, sigma),
                          waypoint.alt_rel)
        print "Drone {0} exploring new waypoint at {1}".format(self.instance, new_wp)
        print "I am at {0}".format(self.get_local_location())
        print "Signal strength {0}".format(self.signal_status.get_rssi())
        self.goto_waypoint(new_wp)

    def run_mission(self):
        self.load_waypoints()
        self.start_and_takeoff()
        self.goto_waypoints()
        self.RTL_and_land()

    def load_waypoints(self, file_name="waypoints.json"):
        if self.get_local_location() is None:  # This returns once a home location is ready
            sys.stderr.write("Cannot load waypoints until we know our home location\n")
            return

        try:
            waypoint_list = None
            with open(file_name) as wp_file:
                waypoint_list = json.load(wp_file)
            self.waypoints = []
            for NED in waypoint_list:
                global_rel = relative_to_global(self.vehicle.home_location, NED[0], NED[1], NED[2])
                self.waypoints.append(Waypoint(global_rel.lat, global_rel.lon, global_rel.alt))
        except StandardError as e:
            sys.stderr.write("Waypoint load error: {0}\n".format(e.__repr__()))

    def start_and_takeoff(self):
        self.bringup_drone()
        self.arm_and_takeoff(15)
        print "altitude: " + str(self.vehicle.location.local_frame.down)

    def goto_waypoints(self, ground_tol=1.0, alt_tol=1.0):
        for _ in self.waypoints:
            self.goto_next_waypoint(ground_tol, alt_tol)

    def goto_next_waypoint(self, ground_tol=1.0, alt_tol=1.0):
        if self._waypoint_index >= len(self.waypoints):
            return False
        self.goto_waypoint(self.waypoints[self._waypoint_index], ground_tol, alt_tol)
        self._waypoint_index += 1
        return True

    def bringup_drone(self, connection_string=None):
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
            self.sitl.download('copter', '3.3', verbose=True)
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
            connection_string = "tcp:127.0.0.1:{0}".format(5760 + 10 * self.instance)
            new_sysid = self.instance + 1
            vehicle = connect(connection_string, wait_ready=True)
            while vehicle.parameters["SYSID_THISMAV"] != new_sysid:
                vehicle.parameters["SYSID_THISMAV"] = new_sysid
                time.sleep(0.1)
            time.sleep(5)  # allow eeprom write
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

    def arm_and_takeoff(self, target_alt):
        """
        Arm vehicle and fly to target_alt.
        """
        self.hold_altitude = target_alt
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
        self.vehicle.simple_takeoff(target_alt)  # Take off to target alt

        # Wait until the self.vehicle reaches a safe height before processing
        # the goto (otherwise the command after Vehicle.simple_takeoff will
        # execute immediately).
        while True:
            print "Vehicle {0} altitude: {1}".format(self.instance,
                                                     self.vehicle.location.global_relative_frame.alt)
            # Break and return from function just below target altitude.
            if (self.vehicle.location.global_relative_frame.alt >=
                    target_alt * 0.90):
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

    def get_attitude(self):
        if self.vehicle is not None:
            return self.vehicle.attitude

    def get_velocity(self):
        if self.vehicle is not None:
            vel = self.vehicle.velocity
            if vel.count(None) == 0:
                return self.vehicle.velocity
        return None

    def get_global_location(self):
        if self.vehicle is not None and self.vehicle.location is not None:
            loc = self.vehicle.location.global_frame
            if loc.lat is not None and loc.lon is not None:
                return self.vehicle.location.global_frame
        return None

    def get_bullshit_location(self):
        return dronekit.LocationGlobal(random.gauss(0, 10), random.gauss(0, 10), random.gauss(20, 5))

    def get_signal_strength(self):
        return self.signal_status.get_rssi()

    def goto_relative(self, north, east, altitude_relative):
        location = relative_to_global(self.vehicle.home_location,
                                      north,
                                      east,
                                      altitude_relative)
        self.goto_waypoint(Waypoint(location.lat, location.lon, altitude_relative))

    def wp_to_global_rel(self, waypoint):
        waypoint_global_rel = relative_to_global(
            self.vehicle.home_location,
            waypoint.dNorth,
            waypoint.dEast,
            waypoint.alt_rel
        )
        return waypoint_global_rel

    def goto_waypoint(self, wp, ground_tol=1.0, alt_tol=1.0):
        """
        Go to a waypoint and block until we get there
        :param wp: :py:class:`Waypoint`
        :return:
        """
        assert isinstance(wp, Waypoint)
        global_relative = dronekit.LocationGlobalRelative(wp.lat, wp.lon, wp.alt_rel)
        self.vehicle.simple_goto(global_relative, groundspeed=self.groundspeed)
        good_count = 0  # Count that we're actually at the waypoint for a few times in a row
        while self.vehicle.mode.name == "GUIDED" and good_count < 5:
            grf = self.vehicle.location.global_relative_frame
            offset = get_ground_distance(grf, global_relative)
            alt_offset = abs(grf.alt - global_relative.alt)
            if offset < ground_tol and alt_offset < alt_tol:
                good_count += 1
            else:
                good_count = 0
            time.sleep(0.2)
        print "Arrived at global_relative."

    def RTL_and_land(self):
        self.goto_relative(0, 0, 15)
        self.vehicle.mode = VehicleMode("LAND")
        self.shutdown_vehicle()

    def shutdown_vehicle(self):
        # Close vehicle object before exiting script
        print "Closing vehicle"
        self.vehicle.close()
