import dronekit
from dronekit import connect, VehicleMode
import dronekit_sitl
import time
import math
import argparse
from nav_utils import relative_to_global, get_distance_meters, Waypoint, read_wp_file
import threading
import numpy as np
import random

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
                    reading += random.gauss(0,0.08) # fuzz it up a little

                    # reading = max(, 0)
                    print "Got air sensor reading: {0}".format(reading)
                    self._callback(reading)
                    time.sleep(5)


class AutoPilot(object):
    def __init__(self):
        self.groundspeed = 7

        # Altitude relative to starting location
        # All further waypoints will use this altitude
        self.hold_altitude = 20
        self.vehicle = None
        self.sitl = None
        self.air_sensor = FakeAirSensor(self)
        self.air_data_points = []

        @self.air_sensor.callback
        def got_air_sample(value):
            loc = self.get_local_location()
            if loc is not None:
                self.air_data_points.append((loc, value))

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
        if len(self.air_data_points)==0:
            waypoint = Waypoint(self.vehicle.location.local_frame.north,
                                self.vehicle.location.local_frame.east,
                                self.hold_altitude)
        else:
            # Find the place with the maximum reading
            max_place = max(self.air_data_points, key=lambda lv: lv[1])
            waypoint = Waypoint(max_place[0].north,
                                max_place[0].east,
                                self.hold_altitude)

        sigma = 10.0
        new_wp = Waypoint(random.gauss(waypoint.dNorth,sigma),
                        random.gauss(waypoint.dEast,sigma),
                        waypoint.alt_rel)
        print "Exploring new waypoint at {0}".format(new_wp)
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
        if not connection_string:
            # Start SITL if no connection string specified
            print "Starting SITL"
            self.sitl = dronekit_sitl.SITL()
            self.sitl.download('copter','3.3',verbose=True)
            sitl_args = ['-I0',
                         '--model', 'quad',
                         '--home=32.990756,-117.128362,243,0',
                         '--speedup', '1']
            self.sitl.launch(sitl_args, verbose=True, await_ready=True, restart=True)
            connection_string = 'tcp:127.0.0.1:5760'
        else:
            # Connect to existing vehicle
            print 'Connecting to vehicle on: %s' % connection_string
        self.vehicle = connect(connection_string, wait_ready=True)
        # self.vehicle.add_attribute_listener('location.local_frame', some_listener)
        # self.vehicle.add_attribute_listener('mode', some_listener)

    def arm_and_takeoff(self, aTargetAltitude):
        """
        Arm vehicle and fly to aTargetAltitude.
        """
        print "Basic pre-arm checks"
        # Don't try to arm until autopilot is ready
        while not self.vehicle.is_armable:
            print " Waiting for vehicle to initialise..."
            time.sleep(1)

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
            print " Waiting for arming..."
            time.sleep(1)

        print "Taking off!"
        self.vehicle.simple_takeoff(aTargetAltitude) # Take off to target alt

        # Wait until the self.vehicle reaches a safe height before processing
        # the goto (otherwise the command after Vehicle.simple_takeoff will
        # execute immediately).
        while True:
            print " Altitude: ", self.vehicle.location.global_relative_frame.alt
            #Break and return from function just below target altitude.
            if (self.vehicle.location.global_relative_frame.alt >= 
                aTargetAltitude*0.95):
                print "Reached target altitude"
                break
            time.sleep(1)


    def poll(self):
        return "Location: " + str(self.vehicle.location.local_frame)

    def get_local_location(self):
        if self.vehicle is not None and self.vehicle.location is not None:
            loc = self.vehicle.location.local_frame
            if loc.north is not None and loc.east is not None:
                return self.vehicle.location.local_frame
        return None

    def goto_waypoint(self, wp):
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
