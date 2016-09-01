from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from models import *
import dronekit
from dronekit import VehicleMode
import copy
from code import interact
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
from pubsub import pub
from contextlib import contextmanager


class LoggerDaemon(threading.Thread):
    # TODO: put mission_setup in sane place and fix path
    def __init__(self, pilot, drone_name, config_file='../database_files/mission_setup.json'):
        super(LoggerDaemon, self).__init__()
        self._pilot = pilot
        self.daemon = True
        self.establish_database_connection()
        self._start_time = time.time()
        self.get_event_list()
        self.config = self.read_config(config_file, drone_name)
        self.acquire_sensor_records()
        self.setup_subs()
        self.start()

    def read_config(self, filename, drone_name):
        #TODO: this is bad
        with open(filename) as fp:
            config = json.load(fp)
        for drone in config['drones']:
            if drone['name'] == drone_name:
                self.drone_info = drone
        self.drone_info['mission'] = config['mission_name']

    def get_event_list(self):
        pass

    def mission_time(self):
        miss_time = time.time() - self._start_time
        return miss_time

    def establish_database_connection(self):
        db_name = 'mission_data'
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    @contextmanager
    def scoped_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def setup_subs(self):
        pub.subscribe(self.air_data_cb, "sensor-messages.air-data")
        pub.subscribe(self.mission_data_cb, "nav-messages.mission-data")

    def acquire_sensor_records(self):
        print "ACQUIRING RECORDS"
        #This whole function is sort of screwy
        #TODO: implement a better method of associating sensors with a drone
        # that supports multiple air sensors being logged
        with self.scoped_session() as session:
            mission_drone_sensors = session.query(
                MissionDroneSensor,
            ).join(
                MissionDrone,
                Drone,
                Mission,
                Sensor,
            ).filter(
                Drone.name==self.drone_info['name'],
                Mission.name==self.drone_info['mission'],
                Sensor.name.in_(self.drone_info['sensors'])
            ).all()
            print mission_drone_sensors,
            print self.drone_info
            # look its the screwy part
            for mds in mission_drone_sensors:
                if 'air' in mds.sensor.name:
                    self.air_sensor = mds
                elif 'GPS' in mds.sensor.name:
                    self.GPS_sensor = mds
            self.event = session.query(
                Event,
            ).one()

    def mission_data_cb(self, arg1=None):
        pass

    def air_data_cb(self, arg1=None):
        print 'TESTING'
        data = copy.deepcopy(arg1)
        with self.scoped_session() as session:
            merged_sensor = session.merge(self.air_sensor)
            merged_event = session.merge(self.event)
            reading = AirSensorRead(
                    AQI=data['fake_reading'],
                    mission_drone_sensor=merged_sensor,
                    event=merged_event,
                    mission_time=self.mission_time(),
            )
            session.add(reading)

    def GPS_recorder(self):
        #I guess I could find something better than True? But the thread is
        # already a daemon
        while True:
            location_global = self._pilot.get_global_location()
            if location_global is not None:
                with self.scoped_session() as session:
                    merged_sensor = session.merge(self.GPS_sensor)
                    merged_event = session.merge(self.event)
                    reading = GPSSensorRead(
                            mission_time=self.mission_time(),
                            mission_drone_sensor=merged_sensor,
                            latitude=location_global.lat,
                            longitude=location_global.lon,
                            altitude=location_global.alt,
                            event = merged_event,
                    )
                    session.add(reading)
            time.sleep(1)

    def run(self):
        self.GPS_recorder()


class Pilot(object):
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
        Pilot.instance += 1
        self.instance = Pilot.instance
        print "I'm a pilot, instance number {0}".format(self.instance)
        self.groundspeed = 7
        if sim_speedup is not None:
            Pilot.sim_speedup = sim_speedup  # Everyone needs to go the same speed
            simulated = True

        # Altitude relative to starting location
        # All further waypoints will use this altitude
        self.hold_altitude = None

        self.vehicle = None
        self.sitl = None
        if simulated:
            hardware.AirSensor(self, simulated=True)
            #self.signal_status = hardware.FakeSignalStatus(self)
        else:
            hardware.AirSensor(self)
            #self.signal_status = None  # TODO: actual wifi signal strengths

        LoggerDaemon(self, "Alpha")

        #I haven't looked at this thoroughly yet and I don't need it right now
        '''
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
        '''

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
                         '--speedup', str(Pilot.sim_speedup),
                         '--instance', str(self.instance)]
            working_dir = tempfile.mkdtemp()
            self.sitl.launch(sitl_args,
                             verbose=True,
                             await_ready=True,
                             restart=True,
                             wd=working_dir)
            time.sleep(6)  # Allow time for the parameter to go back to EEPROM
            connection_string = "tcp:127.0.0.1:{0}".format(5760 + 10 * self.instance)
            #connection_string = "tcp:127.0.0.1:14550")
            new_sysid = self.instance + 1
            vehicle = dronekit.connect(connection_string, wait_ready=True)
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
            self.vehicle = dronekit.connect(connection_string, wait_ready=True)
            print vehicle
        else:
            # Connect to existing vehicle
            print 'Connecting to vehicle on: %s' % connection_string
            print "Connect to {0}, instance {1}".format(connection_string, self.instance)
            self.vehicle = dronekit.connect(connection_string, wait_ready=True)
            print "Success {0}".format(connection_string)

    def stop(self):
        #TODO: probably things should go here? I guess not right now since the
        #db connections are already thread-local in LoggerDaemon
        pass

    def arm_and_takeoff(self, target_alt):
        """
        Arm vehicle and fly to target_alt.
        """
        self.hold_altitude = target_alt
        print "Basic pre-arm checks"
        # Don't try to arm until autopilot is ready
        while not self.vehicle.is_armable:
            print " Waiting for vehicle {0} to initialise...".format(self.instance)
            time.sleep(1.0 / Pilot.sim_speedup)

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
            time.sleep(1.0 / Pilot.sim_speedup)

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
                print "Reached takeoff altitude of {0} meters".format(target_alt)
                break
            time.sleep(1.0 / Pilot.sim_speedup)

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
        self.goto_waypoint(location)

    def goto_waypoint(self, global_relative, ground_tol=1.0, alt_tol=1.0):
        """
        Go to a waypoint and block until we get there
        :param wp: :py:class:`Waypoint`
        :return:
        """
        #TODO: May want to replace simple_goto with something better
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
        if self.vehicle.mode.name != "GUIDED":
            print "Vehicle {0} aborted goto_waypoint due to mode switch to {1}".format(self.instance, self.vehicle.mode.name)
        print "Arrived at global_relative."

    def RTL_and_land(self):
        print "Vehicle {0} returning to home location".format(self.instance)
        self.goto_relative(0, 0, 15)
        print "Vehicle {0} landing".format(self.instance)
        self.vehicle.mode = VehicleMode("LAND")
        self.shutdown_vehicle()

    def shutdown_vehicle(self):
        # Close vehicle object before exiting script
        print "Closing vehicle"
        self.vehicle.close()


class Navigator(object):
    def __init__(self, simulated=False, takeoff_alt=10):
        print "I'm a Navigator!"
        self._waypoint_index = 0
        self.takeoff_alt = takeoff_alt
        self.simulated = simulated
        self.bringup_ip = None
        #should this be in the init function or part of the interface?
        #also should there be error handling?
        self.instantiate_pilot()

    def stop(self):
        self.pilot.stop()

    def instantiate_pilot(self):
        if not self.simulated:
            self.bringup_ip = "udp:127.0.0.1:14550"
        self.pilot = Pilot(simulated=self.simulated)
        self.pilot.bringup_drone(connection_string=self.bringup_ip)

    def liftoff(self, altitude):
        #altitude should be in meters
        self.pilot.arm_and_takeoff(altitude)
        print "Vehicle {0} ready for guidance".format(self.pilot.instance)

    def load_mission(self, filename):
        if self.pilot.get_local_location() is None:
            sys.stderr.write(
                    "Cannot load waypoints until we know our home location\n"
            )
            return

        with open(filename) as fp:
            self.mission = json.load(fp)
        for name, POI in self.mission["points"].iteritems():
            POI["GPS"] = self.meters_to_waypoint(POI)

    def meters_to_waypoint(self, POI):
        global_rel = relative_to_global(
                self.pilot.vehicle.home_location,
                POI['N'],
                POI['E'],
                POI['D']
        )
        return global_rel

    def execute_mission(self):
        try:
            for event in self.mission["plan"]:
               action = getattr(self, event['action'])
               #TODO: this pub business
               #publish event start
               #pub.sendMessage('nav-messages.mission-data', arg1=
               action(event)
               #publish event end
               #pub.sendMessage('nav-messages.mission-data', arg1=
        finally:
            self.pilot.RTL_and_land()

    def go(self, event):
        name = event['points'][0]
        point = self.mission["points"][name]
        global_rel = point["GPS"]
        print "Moving to {}".format(name)
        self.pilot.goto_waypoint(global_rel)

    def patrol(self, event):
        count = event['repeat']
        for i in range(count):
            print "patrolling..."
            for name in event['points']:
                point = self.mission['points'][name]
                self.pilot.goto_waypoint(point['GPS'])
        print "Finished patrolling"
