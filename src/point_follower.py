import dronekit
from dronekit import connect, VehicleMode
import dronekit_sitl
import time
import math
import argparse
from nav_utils import relative_to_global, get_distance_meters, Waypoint, read_wp_file
import threading
import random
import json

import numpy as np
from matplotlib.mlab import griddata
import matplotlib.pyplot as plt


def some_listener(self, attr_name, value):
    print "self {0}".format(self)
    print "callback {0} {1}".format(attr_name, value)


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


class AirSampleDB(object):
    '''
    A place to store and easily retrieve recorded air samples

    For now, it's just an array
    '''

    def __init__(self):
        self._data_points = []

    def __len__(self):
        return len(self._data_points)

    def record(self, location, value):
        assert isinstance(location, dronekit.LocationLocal)
        for i,v in enumerate(self._data_points):
            if get_distance_meters(location, v[0]) < 0.01:
                # Too close to existing point, just change the old one
                self._data_points[i] = (location, value)
                return
        self._data_points.append((location, value))


    def max_sample(self):
        return max(self._data_points, key=lambda lv: lv[1])

    def min_sample(self):
        return min(self._data_points, key=lambda lv: lv[1])

    def average(self):
        if len(self._data_points)==0:
            return None
        return reduce(lambda s,v: s+v[1], self._data_points) / len(self._data_points)

    def plot(self, block=False):
        if len(self._data_points) < 5:
            return
        coords = [np.array([l[0].east, l[0].north]) for l in self._data_points]
        z = [l[1] for l in self._data_points]
        lower_left = np.minimum.reduce(coords)
        upper_right = np.maximum.reduce(coords)
        print np.linalg.norm(upper_right - lower_left)
        if np.linalg.norm(upper_right - lower_left) < 0.1:
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
            data = map(lambda lv: [lv[0].east,
                                   lv[0].north,
                                   lv[0].down,
                                   lv[1]],
                       self._data_points)
            json.dump(data, data_file, indent=True)

    def load(self, filename="sensor_data.json"):
        with open(filename) as data_file:
            data = json.load(data_file)
            if data is not None:
                self._data_points = \
                    map(lambda d: (dronekit.LocationLocal(d[1], d[0], d[2]), d[3]), data)
            else:
                self._data_points = []



class AutoPilot(object):
    sim_speedup = 1
    instance = -1
    global_db = AirSampleDB()

    def __init__(self, sim_speedup = None):
        AutoPilot.instance += 1
        self.instance = AutoPilot.instance
        self.groundspeed = 7
        if sim_speedup is not None:
            AutoPilot.sim_speedup = sim_speedup     # Everyone needs to go the same speed

        # Altitude relative to starting location
        # All further waypoints will use this altitude
        self.hold_altitude = 20
        self.vehicle = None
        self.sitl = None
        self.air_sensor = FakeAirSensor(self)
        self.sensor_readings = AutoPilot.global_db

        @self.air_sensor.callback
        def got_air_sample(value):
            loc = self.get_local_location()
            if loc is not None:
                self.sensor_readings.record(loc, value)

        self.air_sensor.start()

    def update_exploration(self):
        '''
        Pick another waypoint to explore

        Algorithm right now is very simple:
        Find the coordinate of the highest gas value that we've recorded so far
        Perturb that coordinate randomly
        Go to perturbed coordinate

        :return:
        '''
        if self.get_local_location() is None:
            return

        waypoint = None
        if len(self.sensor_readings)==0:
            waypoint = Waypoint(self.vehicle.location.local_frame.north,
                                self.vehicle.location.local_frame.east,
                                self.hold_altitude)
        else:
            # Find the place with the maximum reading
            max_place = self.sensor_readings.max_sample()
            waypoint = Waypoint(max_place[0].north,
                                max_place[0].east,
                                self.hold_altitude)
            self.sensor_readings.save()

        sigma = 20.0
        new_wp = Waypoint(random.gauss(waypoint.dNorth,sigma),
                        random.gauss(waypoint.dEast,sigma),
                        waypoint.alt_rel)
        print "Drone {0} exploring new waypoint at {1}".format(self.instance, new_wp)
        self.sensor_readings.plot()
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
            sitl_args = ['-I0',
                         '--model', 'quad',
                         '--home=32.990756,-117.128362,243,0',
                         '--speedup', str(AutoPilot.sim_speedup),
                         '--instance', str(self.instance)]
            self.sitl.launch(sitl_args, verbose=True, await_ready=True, restart=True)
            connection_string = "tcp:127.0.0.1:{0}".format(5760 + 10*self.instance)
        else:
            # Connect to existing vehicle
            print 'Connecting to vehicle on: %s' % connection_string
        print "Connect to {0}, instance {1}".format(connection_string, self.instance)
        self.vehicle = connect(connection_string, wait_ready=False)
        print "Success {0}".format(connection_string)
        # msg = self.vehicle.message_factory.param_set_encode(
        #     0, 0,
        #     "SYSID_THISMAV",
        #     self.instance*10 + 2,
        #     9
        # )
        # self.vehicle.send_mavlink(msg)
        # self.vehicle.add_attribute_listener('location.local_frame', some_listener)
        # self.vehicle.add_attribute_listener('mode', some_listener)

    def arm_and_takeoff(self, aTargetAltitude):
        """
        Arm vehicle and fly to aTargetAltitude.
        """
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

    def goto_waypoint(self, wp):
        '''
        Go to a waypoint and block until we get there
        :param wp: :py:class:`Waypoint`
        :return:
        '''
        global_rel = self.wp_to_global_rel(wp)
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
        while offset > 2 and self.vehicle.mode.name == "GUIDED":
            offset = get_distance_meters(
                    self.vehicle.location.global_relative_frame,
                    global_relative
                    )
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
