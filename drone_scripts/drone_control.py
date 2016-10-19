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
from flask import Flask, request
from contextlib import contextmanager
from collections import deque


app = Flask(__name__)


class FlaskServer(threading.Thread):
    def __init__(self):
        super(FlaskServer, self).__init__()
        self.daemon = True
        self.start()

    @app.route('/launch', methods=['POST'])
    def launch_func():
        print "entered flask launch function"
        time = json.loads(request.data)
        pub.sendMessage(
            'flask-messages.launch',
            arg1=time,
        )
        return 'received launch command'

    @app.route('/mission', methods=['POST'])
    def mission_func():
        print "entered flask mission function"
        print request.data
        mission = json.loads(request.data)
        pub.sendMessage(
            'flask-messages.mission',
            arg1=mission,
        )
        return 'received mission'

    @app.route('/RTL_and_land', methods=['GET'])
    def RTL_and_land_func():
        print "entered flask RTL function"
        pub.sendMessage(
            'flask-messages.RTL',
            arg1=True,
        )
        return 'RTL and landing'

    @app.route('/land', methods=['GET'])
    def land_func():
        print "entered flask land function"
        pub.sendMessage(
            'flask-messages.land',
            arg1=True,
        )
        return 'landing'

    @app.route('/ack', methods=['GET'])
    def ack_func():
        print "entered flask ack function"
        return 'ack'

    def run(self):
        app.run('0.0.0.0')

class LoggerDaemon(threading.Thread):
    # TODO: put mission_setup in sane place and fix path
    def __init__(self, pilot, drone_name, config_file='../database_files/mission_setup.json'):
        super(LoggerDaemon, self).__init__()
        self._pilot = pilot
        self.daemon = True
        self.establish_database_connection()
        self._start_seconds = None
        self.read_config(config_file, drone_name)
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

    def mission_time(self):
        if self._start_seconds is not None:
            miss_seconds = time.time() - self._start_seconds
            miss_time = miss_seconds + self._launch_time
            '''
            print "Calculated time: {0}\n miss_seconds: {1}\n start_seconds: {2}\n".format(
                miss_time,
                miss_seconds,
                self._start_seconds,
            )
            '''
            return miss_time
        else:
            return None

    def establish_database_connection(self):
        # TODO: set up the URL somehow so it's not here and also in the
        # startup thing in /etc/rc.local. How do I into networking anyway?
        db_name = 'mission_data'
        # 192.168.42.19 is the address the basestation should always be on,
        # on the ZyXEL network
        '''
        import machine_config
        if machine == 'laptop':
        '''
        machine = 'drone'
        if machine == 'laptop':
            db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        elif machine == 'drone':
            db_url = 'mysql+mysqldb://dronebs:password@192.168.1.88/' + db_name
        else:
            print ("machine not recognized, attempting to connect to database"+
                  " locally (this will probably error)...")
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
        pub.subscribe(self.launch_cb, "flask-messages.launch")

    def launch_cb(self, arg1=None):
        if not self._start_seconds:
            time_dict = arg1
            self._start_seconds = time.time()
            self._launch_time = time_dict['start_time']
            print "LoggerDaemon got {0}, {1} from launch".format(arg1, self._launch_time)

    def flask_cb(self, arg1=None):
        print "LoggerDaemon got {}".format(arg1)

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
            # look it's the screwy part
            for mds in mission_drone_sensors:
                if 'air' in mds.sensor.name:
                    self.air_sensor = mds
                elif 'GPS' in mds.sensor.name:
                    self.GPS_sensor = mds

    def mission_data_cb(self, arg1=None):
        print 'entered mission_data_cb'
        event_dict = copy.deepcopy(arg1)
        event_json = event_dict
        with self.scoped_session() as session:
            mission_event = session.query(
                EventType,
            ).filter(
                EventType.event_type == 'mission_event',
            ).one()
            new_event = Event(
                    event_type=mission_event,
                    event_data=event_json,
            )
            session.add(new_event)

    def air_data_cb(self, arg1=None):
        current_time = self.mission_time()
        if current_time is not None:
            print 'entered air_data_cb'
            data = copy.deepcopy(arg1)
            with self.scoped_session() as session:
                merged_sensor = session.merge(self.air_sensor)
                air_event = session.query(
                    EventType,
                ).filter(
                    EventType.event_type == 'air_sensor_data',
                ).one()
                assoc_event = Event(
                        event_type=air_event,
                        event_data = {}
                )
                reading = AirSensorRead(
                        air_data=data,
                        mission_drone_sensor=merged_sensor,
                        event=assoc_event,
                        time=current_time
                )
                session.add_all([reading, assoc_event])

    def GPS_recorder(self):
        #I guess I could find something better than True? But the thread is
        # already a daemon
        while True:
            location_global = self._pilot.get_global_location()
            current_time = self.mission_time()
            if (location_global
                    and location_global.lat
                    and location_global.lon
                    and location_global.alt
                    and current_time):
                with self.scoped_session() as session:
                    merged_sensor = session.merge(self.GPS_sensor)
                    gps_event = session.query(
                        EventType,
                    ).filter(
                        EventType.event_type == 'auto_nav',
                    ).one()
                    assoc_event = Event(
                            event_type=gps_event,
                            event_data = {}
                    )
                    reading = GPSSensorRead(
                            time=current_time,
                            mission_drone_sensor=merged_sensor,
                            event = assoc_event,
                            latitude=location_global.lat,
                            longitude=location_global.lon,
                            altitude=location_global.alt,
                    )
                    session.add_all([reading, gps_event])
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

    def __init__(self, simulated=False, simulated_air_sensor=False, sim_speedup=None):
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
        hardware.AirSensor(self, simulated=simulated_air_sensor)

        LoggerDaemon(self, "Alpha")

        #I haven't looked at this thoroughly yet and I don't need it right now
        '''
        self.speed_readings = SampleDB(json_file=None, csv_file="speed_data.csv")
        if simulated:
            self.speed_readings.sync_to("127.0.0.1", 6001)
        else:
            self.speed_readings.sync_to("192.168.42.19", 6001)

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
        self.shutdown_vehicle()

    def arm_and_takeoff(self, target_alt):
        """
        Arm vehicle and fly to target_alt.
        """
        if self.vehicle.armed == True:
            return
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

    def land_drone(self):
        print "Vehicle {0} landing".format(self.instance)
        self.vehicle.mode = VehicleMode("LAND")

    def return_to_launch(self):
        print "Vehicle {0} returning to home location".format(self.instance)
        self.goto_relative(0, 0, 15)

    def shutdown_vehicle(self):
        # Close vehicle object before exiting script
        print "Closing vehicle"
        self.vehicle.close()


class Navigator(object):
    def __init__(self, simulated=False, simulated_air_sensor=True, takeoff_alt=5):
        print "I'm a Navigator!"
        self._waypoint_index = 0
        self.takeoff_alt = takeoff_alt
        self.simulated = simulated
        self.simulated_air_sensor = simulated_air_sensor
        self.bringup_ip = None
        #should this be in the init function or part of the interface?
        #also should there be error handling?
        self.launch_mission = self.load_launch_mission()
        self.instantiate_pilot()
        self.setup_subs()
        FlaskServer()
        self.mission_queue = deque([])
        self.event_loop()

    def load_launch_mission(self):
        with open('launch_mission.json', 'r') as fp:
            mission = json.load(fp)
        return mission

    def event_loop(self):
        print "entering run loop"
        while True:
            try:
                time.sleep(.01)
                if self.mission_queue:
                    next_mission = self.mission_queue.popleft()
                    self.execute_mission(next_mission)
            except KeyboardInterrupt:
                self.pilot.RTL_and_land()
                break

    def setup_subs(self):
        print "setting up subs"
        pub.subscribe(self.launch_cb, "flask-messages.launch")
        pub.subscribe(self.mission_cb, "flask-messages.mission")
        pub.subscribe(self.land_cb, "flask-messages.land")
        pub.subscribe(self.RTL_cb, "flask-messages.RTL")

    def mission_cb(self, arg1=None):
        print "Navigator entered mission_cb with data {0}".format(arg1)
        mission_json = arg1
        parsed_mission = self.parse_mission(mission_json)
        self.mission_queue.append(parsed_mission)

    def launch_cb(self, arg1=None):
        print "Navigator entered launch callback"
        launch_mission = self.launch_mission
        self.mission_queue.append(launch_mission)
        #self.liftoff(5)

    def land_cb(self, arg1=None):
        print "Navigator entered land callback"
        self.pilot.land_drone()

    def RTL_cb(self, arg1=None):
        print "Navigator entered RTL callback"
        self.pilot.return_to_launch()
        self.pilot.land_drone()

    def triggered_mission(self, arg1=None):
        mission_json = load_mission('test_mission.json')
        parsed_mission = self.parse_mission(mission_json)
        self.execute_mission(parsed_mission)
        self.event_loop()

    def stop(self):
        self.pilot.stop()

    def instantiate_pilot(self):
        if not self.simulated:
            self.bringup_ip = "udp:127.0.0.1:14550"
        self.pilot = Pilot(
                simulated=self.simulated,
                simulated_air_sensor=self.simulated_air_sensor,
        )
        self.pilot.bringup_drone(connection_string=self.bringup_ip)

    def launch(self, event):
        #altitude should be in meters
        altitude = self.takeoff_alt
        if not self.pilot.vehicle.armed:
            self.pilot.arm_and_takeoff(altitude)
            print "Vehicle {0} ready for guidance".format(self.pilot.instance)
            return
        print "Vehicle {0} already armed".format(self.pilot.instance)

    def load_mission(self, filename):
        if self.pilot.get_local_location() is None:
            sys.stderr.write(
                    "Cannot load waypoints until we know our home location\n"
            )
            return

        with open(filename) as fp:
            mission = json.load(fp)
        return mission


    def parse_mission(self, mission_json):
        for name, POI in mission_json["points"].iteritems():
            POI["GPS"] = self.meters_to_waypoint(POI)
        return mission_json

    def meters_to_waypoint(self, POI):
        global_rel = relative_to_global(
                self.pilot.vehicle.home_location,
                POI['N'],
                POI['E'],
                POI['D']
        )
        return global_rel
    
    def execute_mission(self, mission):
        try:
            self.current_mission = mission
            for event in mission["plan"]:
               action = getattr(self, event['action'])
               #publish event start
               event_start_dict = {
                       'task':event['action'],
                       'action':'start',
               }
               pub.sendMessage(
                       'nav-messages.mission-data',
                       arg1=event_start_dict
               )
               #do the thing
               action(event)
               #publish event end
               event_end_dict = {
                       'task':event['action'],
                       'action':'end',
               }
               pub.sendMessage(
                       'nav-messages.mission-data',
                       arg1=event_end_dict
               )
        except Exception as e:
            print "Exception! RTL initiated"
            print e
            self.pilot.RTL_and_land()
            self.stop()

    def go(self, event):
        name = event['points'][0]
        point = self.current_mission["points"][name]
        global_rel = point["GPS"]
        print "Moving to {}".format(name)
        self.pilot.goto_waypoint(global_rel)

    def patrol(self, event):
        count = event['repeat']
        for i in range(count):
            print "patrolling..."
            for name in event['points']:
		print "going to {}".format(name)
                point = self.current_mission['points'][name]
                self.pilot.goto_waypoint(point['GPS'])
        print "Finished patrolling"

    def RTL(self, event):
        self.pilot.return_to_launch()

    def land(self, event):
        self.pilot.land_drone()
