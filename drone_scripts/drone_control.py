"""
Provide the main classes for the drone-based part of the project.

FlaskServer:
    Flask server that runs on each drone to handle http requests.

LoggerDaemon:
    Daemon thread to receive all logging info and store it in the database.

Pilot:
    Class that interfaces directly with the Dronekit vehicle object.

Navigator:
    Class to handle the high-level navigation and mission execution.
"""
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
import rf_readings
import csv
from pubsub import pub
from flask import Flask, request
from contextlib import contextmanager
from collections import deque


app = Flask(__name__)


class FlaskServer(threading.Thread):
    """Provide a flask server for managing HTTP requests to/from the drone.

    This class is set up using the Flask documentation. It inherits from the
    threading.Thread class, and therfore needs a run() method and to specificy
    self.daemon. 

    This class communicates with the other objects on the drone via the
    PyPubSub API.

    """

    def __init__(self):
        """Construct an instance of FlaskServer."""
        super(FlaskServer, self).__init__()
        self.daemon = True
        self.start()

    @app.route('/launch', methods=['POST'])
    def launch_func():
        """Post the current time and a launch command to the launch topic."""
        print "entered flask launch function"
        time = json.loads(request.data)
        pub.sendMessage(
            'flask-messages.launch',
            arg1=time,
        )
        return 'received launch command'

    @app.route('/mission', methods=['POST'])
    def mission_func():
        """Receive and then post a JSON mission to the mission topic."""
        print "entered flask mission function"
        #print request.data
        mission = json.loads(request.data)
        pub.sendMessage(
            'flask-messages.mission',
            arg1=mission,
        )
        return 'received mission'

    @app.route('/RTL_and_land', methods=['GET'])
    def RTL_and_land_func():
        """Publish True to the RTL topic."""
        print "entered flask RTL function"
        pub.sendMessage(
            'flask-messages.RTL',
            arg1=True,
        )
        return 'RTL and landing'

    @app.route('/land', methods=['GET'])
    def land_func():
        """Publish True to the land topic."""
        print "entered flask land function"
        pub.sendMessage(
            'flask-messages.land',
            arg1=True,
        )
        return 'landing'

    @app.route('/ack', methods=['GET'])
    def ack_func():
        """Send an acknowledgement to whoever sent the request."""
        print "entered flask ack function"
        return 'ack'

    def run(self):
        """Start the flask server on the local ip and then start the thread."""
        app.run('0.0.0.0')

class LoggerDaemon(threading.Thread):
    """Provide a class to receive logging data and store it in the database.

    LoggerDaemon is the central class for all the logging and data storage that
    the drones need. It can read data from and store data in the database,
    keeps track of the current time, and receives data from the navigator and
    sensors via the PyPubSub API. 

    This class inherets from threading.Thread and is a daemon.

    """

    # TODO: put mission_setup in sane place and fix path
    def __init__(self, pilot, drone_name, config_file='../database_files/mission_setup.json'):
        """Construct an instance of LoggerDaemon.
        
        This stores the Pilot object that created the LoggerDaemon, sets the
        object as a daemon, sets up the database connection and then finds the
        database records associated with the drone and sensor(s) it's running
        on.

        pilot -- a Pilot object to allow the LoggerDaemon access to the
                 dronekit vehicle object.
        drone_name -- the name of the drone the LoggerDaemon is running on,
                      should be a name in the database's drones table.
        config_file -- configuration file to get the current mission_name and
                       drone info from.
        """
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
        """Read the mission config file and store mission and drone information

        This reads and stores the mission name and sensors associated with the
        current mission and drone, in preparation for finding their records in
        the database.
        """
        #TODO: this is bad
        with open(filename) as fp:
            config = json.load(fp)
        for drone in config['drones']:
            if drone['name'] == drone_name:
                self.drone_info = drone
        self.drone_info['mission'] = config['mission_name']

    def mission_time(self):
        """Return the current time in unix era format.

        This function is necessary because the clock on the Raspberry Pi isn't
        real-time and so time.time() returns something bad and wrong, but
        internally consistent.
        """
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
        """Set up the database access via the sqlalchemy interface."""
        # TODO: set up the URL somehow so it's not here and also in the
        # startup thing in /etc/rc.local. How do I into networking anyway?
        db_name = 'mission_data'
        # 192.168.42.19 is the address the basestation should always be on,
        # on the ZyXEL network
        '''
        import machine_config
        if machine == 'laptop':
        '''
        machine = 'laptop'
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
        """Provide a context manager for database access."""
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
        """Set up the subscribers and callbacks for relevant pubsub topics."""
        pub.subscribe(self.air_data_cb, "sensor-messages.air-data")
        pub.subscribe(self.wifi_data_cb, "sensor-messages.wifi-data")
        pub.subscribe(self.mission_data_cb, "nav-messages.mission-data")
        pub.subscribe(self.launch_cb, "flask-messages.launch")

    def launch_cb(self, arg1=None):
        """Set start_seconds and launch_time to appropriate values."""
        if not self._start_seconds:
            time_dict = arg1
            self._start_seconds = time.time()
            self._launch_time = time_dict['start_time']
            print "LoggerDaemon got {0}, {1} from launch".format(arg1, self._launch_time)

    def acquire_sensor_records(self):
        """Find sensor records for this drone and mission.

        This queries the database for all sensor records that are in this drone
        and mission, and then sorts them into the air, GPS and RF sensors
        accordingly based on their names.
        """
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
                elif 'RF' in mds.sensor.name:
                    self.RF_sensor = mds

    def mission_data_cb(self, arg1=None):
        """Add incoming mission event to the database."""
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

    def wifi_data_cb(self, arg1=None):
        """Add incoming wifi data to the database."""
        #print "wifi callback entered: {}".format(arg1)
        current_time = self.mission_time()
        if current_time is not None:
            print 'entered wifi_data_cb'
            data = copy.deepcopy(arg1)
            with self.scoped_session() as session:
                merged_sensor = session.merge(self.RF_sensor)
                RF_event = session.query(
                    EventType,
                ).filter(
                    EventType.event_type == 'RF_sensor_data',
                ).one()
                assoc_event = Event(
                        event_type=RF_event,
                        event_data = {},
                )
                reading = RFSensorRead(
                        RF_data=data,
                        mission_drone_sensor=merged_sensor,
                        event=assoc_event,
                        time=current_time,
                )
                session.add_all([reading, assoc_event])

    def air_data_cb(self, arg1=None):
        """Add incoming air sensor data to the database."""
        current_time = self.mission_time()
        if current_time is not None:
            print 'entered air_data_cb'
            print arg1
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

    def rel_from_glob(self, global_loc):
        """Return the relative coordinates of a GPS location in JSON NE format.
        
        global_loc should be a location object from dronekit that has a lat and
        a lon attribute. The returned value is a JSON string of a dictionary so
        that it can be put directly into the relative attribute of a GPS sensor
        record.
        """
        home = self._pilot.vehicle.home_location
        north = nav_utils.lat_lon_distance(
            home.lat,
            home.lon,
            global_loc.lat,
            home.lon,
        )
        east = nav_utils.lat_lon_distance(
            home.lat,
            home.lon,
            home.lat,
            global_loc.lon,
        )
        return json.dumps({'relative':[north, east]})

    def GPS_recorder(self):
        """Record the drone's current GPS location every half second."""
        # Something better than while True? Thread is already a daemon I guess
        while True:
            location_global = self._pilot.get_global_location()
            current_time = self.mission_time()
            if (location_global
                    and location_global.lat
                    and location_global.lon
                    and location_global.alt
                    and current_time):
                location_relative = self.rel_from_glob(location_global)
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
                            relative=location_relative,
                    )
                    session.add_all([reading, gps_event])
            time.sleep(1)

    def run(self):
        """Start the thread object."""
        self.GPS_recorder()


class Pilot(object):
    """Provide basic piloting functionality and interface to sensors.

    This class is intended to contain all the basic fuctionality of flying the
    drone from place to place, interfacing with sensors, and acessing/updating
    the information in dronekit's vehicle object (which in turn is the API used
    to interact with the instance of ardupilot running on the drone).
    
    Chris originally wrote most of this class, so if my documentation is
    unclear or lacking he might be able to provide clarification. A lot of the
    code in this class is probably superflous by this point (for example, I'm
    pretty sure self.hold_altitude does nothing) but it works, and refactoring
    hasn't been high on the list of priorities, so if you're going to dig into
    this class be aware it might be confusing. 

    """

    sim_speedup = 1
    instance = -1

    # global_db = AirSampleDB()
    #
    # # When simulating swarms, prevent multiple processes from doing strange things
    # lock_db = multiprocessing.Lock()

    def __init__(self, simulated=False, simulated_RF_sensor=False, simulated_air_sensor=False, sim_speedup=None):
        """Construct an instance of the Pilot class.

        This instantiates the sensors, real or simulated, and the LoggerDaemon.

        simulated -- Are we running this on the simulator?
        simulated_RF_sensor -- Use simulated data if True, real RF data else
        simulated_air_sensor -- Use simulated data if True, real air data else
        sim_speedup -- Factor to speed up the simulator, e.g. 2.0 = twice as
                       fast. Somewhat glitchy on higher values.
        """
        Pilot.instance += 1
        self.instance = Pilot.instance
        print "I'm a pilot, instance number {0}".format(self.instance)
        self.groundspeed = .5
        if sim_speedup is not None:
            Pilot.sim_speedup = sim_speedup  # Everyone needs to go the same speed
            simulated = True

        # Altitude relative to starting location
        # All further waypoints will use this altitude
        self.hold_altitude = None

        self.vehicle = None
        self.sitl = None
        hardware.AirSensor(simulated=simulated_air_sensor)
        rf_readings.RSSISensor(simulated=simulated_RF_sensor)

        LoggerDaemon(self, "Alpha")

    def bringup_drone(self, connection_string=None):
        """Connect to a dronekit vehicle or instantiate an sitl simulator.

        Call this once everything is set up and you're ready to fly.
        
        This is some deep magic related to running multiple drones at once. We
        don't technically need it, since the network architecture I've set up
        has the drones all be independant (if you want to simulate multiple
        drones with the current setup you run multiple instances of the SITL
        simulator). Chris got this all working by talking with the dronekit
        devs, so he knows a lot more about it than I do.

        connection_string -- Connect to an existing mavlink (SITL or the actual
                             ArduPilot). Provide None and it'll start its own
                             simulator.
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
        """Properly close the vehicle object."""
        self.shutdown_vehicle()

    def arm_and_takeoff(self, target_alt):
        """Arm vehicle and fly to target_alt."""
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
        """Return string with the vehicle's current location (local frame)."""
        return "Location: " + str(self.vehicle.location.local_frame)

    def get_local_location(self):
        """Return the vehicle's NED location as a LocationGlobalRelative."""
        if self.vehicle is not None and self.vehicle.location is not None:
            loc = self.vehicle.location.local_frame
            if loc.north is not None and loc.east is not None:
                return self.vehicle.location.local_frame
        return None

    def get_attitude(self):
        """Return the current altitude."""
        if self.vehicle is not None:
            return self.vehicle.attitude

    def get_velocity(self):
        """Return the current velocity."""
        if self.vehicle is not None:
            vel = self.vehicle.velocity
            if vel.count(None) == 0:
                return self.vehicle.velocity
        return None

    def get_global_location(self):
        """Return the vehicle's current GPS location as a LocationGlobal."""
        if self.vehicle is not None and self.vehicle.location is not None:
            loc = self.vehicle.location.global_frame
            if loc.lat is not None and loc.lon is not None:
                return self.vehicle.location.global_frame
        return None

    def goto_relative(self, north, east, altitude_relative):
        """Go to a NED location.

        This is basically just a wrapper for goto_waypoint to allow it to use
        NED coordinates. nort, ease and altitude_relative should be in meters.
        """
        location = relative_to_global(self.vehicle.home_location,
                                      north,
                                      east,
                                      altitude_relative)
        self.goto_waypoint(location)

    def goto_waypoint(self, global_relative, ground_tol=0.8, alt_tol=1.0, speed=50):
        """Go to a waypoint and block until we get there.

        global_relative -- A LocationGlobalRelative, the waypoint
        ground_tol -- the error tolerance for the horizontal distance from the
                      waypoint in meters.
        alt_tol -- the error tolerance for the vertical distance from the
                   waypoint in meters.
        speed -- the maximum speed the drone will try to move at, in cm/s. Note
                 that there are cases where the drone will move faster than
                 this, so DO NOT use this as a safety cutoff.
        """
        self.vehicle.parameters['WPNAV_SPEED'] = speed
        if self.vehicle.mode != "GUIDED":
            print "Vehicle {0} aborted goto_waypoint due to mode switch to {1}".format(self.instance, self.vehicle.mode.name)
            return False
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
        print "Arrived at global_relative."
        return True

    def RTL_and_land(self):
        """Return to home location and land the drone."""
        print "Vehicle {0} returning to home location".format(self.instance)
        self.goto_relative(0, 0, 7)
        print "Vehicle {0} landing".format(self.instance)
        self.vehicle.mode = VehicleMode("LAND")

    def land_drone(self):
        """Land the drone at its current location."""
        print "Vehicle {0} landing".format(self.instance)
        self.vehicle.mode = VehicleMode("LAND")

    def return_to_launch(self):
        """Return to the home location."""
        print "Vehicle {0} returning to home location".format(self.instance)
        self.goto_relative(0, 0, 15)

    def shutdown_vehicle(self):
        """Properly close the vehicle object."""
        print "Closing vehicle"
        self.vehicle.close()


class Navigator(object):
    def __init__(self, simulated=False, simulated_RF_sensor=True, simulated_air_sensor=True, takeoff_alt=5):
        print "I'm a Navigator!"
        self._waypoint_index = 0
        self.takeoff_alt = takeoff_alt
        self.simulated = simulated
        self.simulated_air_sensor = simulated_air_sensor
        self.simulated_RF_sensor = simulated_RF_sensor
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
                    if self.pilot.vehicle.mode != 'GUIDED':
                        self.mission_queue = deque([])
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
        #print "Navigator entered mission_cb with data {0}".format(arg1)
        print "Navigator entered mission_cb"
        mission_json = arg1
        self.mission_queue.append(mission_json)

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
                simulated_RF_sensor=self.simulated_RF_sensor,
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
    
    def execute_mission(self, unparsed_mission):
        try:
            if unparsed_mission['plan'][0]['action'] != 'launch':
                mission = self.parse_mission(unparsed_mission)
            else:
                # look at the terrible thing I'm doing! :D
                # ... D:
                mission = unparsed_mission
            self.current_mission = mission
            for event in mission["plan"]:
               if mission['plan'][0]['action'] != 'launch' and (self.pilot.vehicle.mode != 'GUIDED'):
	           print 'aborting mission due to check'
                   self.mission_queue = deque([])
                   return
	       print 'mission executing action {}'.format(event['action'])
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
            print "Exception! RTL initiated", e
            self.pilot.RTL_and_land()
            self.stop()

    def go(self, event):
        name = event['points'][0]
        point = self.current_mission["points"][name]
        global_rel = point["GPS"]
        print "Moving to {}".format(name)
        self.pilot.goto_waypoint(global_rel, speed=70)

    def patrol(self, event):
        count = event['repeat']
        for i in range(count):
            print "patrolling..."
            for name in event['points']:
		print "going to {}".format(name)
                point = self.current_mission['points'][name]
                self.pilot.goto_waypoint(point['GPS'], speed=10)
        print "Finished patrolling"

    def RTL(self, event):
        self.pilot.return_to_launch()

    def land(self, event):
        self.pilot.land_drone()
