"""
A script to coordinate multiple (currently 2) instances of drone_control.py

This script takes two IP addresses representing two drones as well as a
threshold. It then launches and sends missions to the drones based on the
data they collect. While it can run standalone missions and should be easy to
modify for other purposes, currently its primary function is to run the laptop
side of the fire-finding demo used at the October 2016 Terraswarm research
review that was run at UC Berkeley.

The script should be run on the command line as:

python base_station.py 'primaryip' 'secondaryip' threshold

Where the two IP addresses are any valid IPv4 address format, such as
'192.168.0.1', or 'localhost', and 'threshold' is something like 500. When
running the demo, the primary ip should point to the drone that flies the grid
mission, the secondary ip should point to the drone that waits for high
readings before investigating, and the threshold should be the minimum value of
the CO2 sensor that will trigger the second drone (~500-600 seems to work well
in most conditions). If not running the demo , any of these arguments can be
replaced by an empty string ''.

Command line arguments:
primary_ip      -- the IP of the primary drone
secondary_ip    -- the IP of the secondary drone
threshold       -- an integer, or string which works with int()
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, cast
from sqlalchemy.orm import sessionmaker, aliased
import math
from sqlalchemy.ext.declarative import declarative_base
from models import *
import numpy as np
from code import interact
from contextlib import contextmanager
import nav_utils
import argparse
import requests
import json
import time
from MissionGenerator import MissionGenerator
from collections import deque
from itertools import chain, izip


class DroneCoordinator(object):
    """
    A class to coordinate multiple (currently 2) instances of drone_control.py

    This can be imported from other scripts if needed, but is currently set up
    to be run from the command line, as described at the top of the file. 

    """

    def __init__(self, primary_drone_ip, secondary_drone_ip=None, threshold=500):
        """
        Initialize an instance of DroneCoordinator

        If you're thinking about using this from another module, this is a good
        place to look for things you can set on runtime if desired. For example
        primary_height and secondary_height, the config file that is read, or
        how the addresses are constructed from the IPs.
        """
        self.threshold = int(threshold)
        self.read_config('../database_files/mission_setup.json')
        self.primary_drone_addr = 'http://' + primary_drone_ip + ':5000/'
        if secondary_drone_ip:
            self.secondary_drone_addr = 'http://' + secondary_drone_ip + ':5000/'
        self.primary_height = 3
        self.secondary_height = 5

        # Things after this shouldn't be set when the class is constructed
        self.max_id = 0
        self.points_investigated = 0
        self.establish_database_connection()
        self.areas_of_interest = deque([])
        self.establish_database_connection()
        self.mission_generator = MissionGenerator()

    def generate_corner_banana(self):
        """Sometimes you need a corner banana"""
        intervals = range(0, 11, 2)
        south_points = [[0, point] for point in intervals]
        west_points = [[point, 0] for point in intervals] 
        diag_points = [[point, point] for point in intervals]
        #TODO: There has to be a better way to do this. My list comprehension
        # fu is not strong :(
        point_list = []
        for i in range(0, 6, 2):
            point_list.append(south_points[i])
            point_list.append(diag_points[i])
            point_list.append(west_points[i])

            point_list.append(west_points[i+1])
            point_list.append(diag_points[i+1])
            point_list.append(south_points[i+1])
        point_list = point_list[2:]
        point_list = [[lat, lon, 3] for lat, lon in point_list]
        #print point_list
        '''
        point_list = list(
            chain.from_iterable(
                izip(
                    south_points,
                    diag_points,
                    west_points
                )
            )
        )
        print point_list
        '''

    def relative_coords(self, lat1, lon1, lat2, lon2):
        """
        Return the relative vector in meters between two GPS coordinates
        
        This returns the (North, East) distance in meters between two GPS
        coordinates (lat1, lon1), (lat2, lon2). So if (lat2, lon2) is 10 meters
        north and three meters east of (lat1, lon1), this returns (10, 3).
        Distances to the south or west are negative.
        """
        lat_dist = nav_utils.lat_lon_distance(lat1, lon1, lat2, lon1)
        lon_dist = nav_utils.lat_lon_distance(lat1, lon1, lat1, lon2)
        lat_dist = math.copysign(lat_dist, (lat2 - lat1))
        lon_dist = math.copysign(lon_dist, (lon2 - lon1))
        return [lat_dist, lon_dist]

    def get_latest_loc(self, drone_name):
        """Return the latest GPS location of drone_name from the database."""
        if drone_name == 'Beta':
            print 'getting beta data'
            data = self.get_data_beta()
        elif drone_name == 'Alpha':
            data = self.get_data()
        points = data
        # This should probably use keys instead of indexes, otherwise changing
        # get_data/get_data_beta can break this
        latest_point = max(points, key=lambda point: point[5])
        latest_loc = [latest_point[1], latest_point[2]]
        return latest_loc

    def relative_triangle(self, drone_addr, drone_name, point, radius=2):
        """Send a drone to fly a triangle around a GPS coordinate and return.

        This is the function intended to let the second drone 'investigate' the
        points found by the first drone in the demo.

        drone_addr -- address (not IP) of the drone you want to send
        drone_name -- name of the drone you want to send
        point -- the point to fly the triangle around, in [lat, lon] format
        radius -- the radius of the triangle, default 2 meters
        """
        self.launch_drone(drone_addr)
        time.sleep(20)
        latest_loc = self.get_latest_loc(drone_name)
        relative = self.relative_coords(
            latest_loc[0],
            latest_loc[1],
            point[0],
            point[1]
        )
        N = relative[0]
        E = relative[1]
        config_dict = {
            'shape':'triangle',
            'radius':radius,
            'loc_start':np.array([N, E]),
            'altitude': 5,
        }
        mission = self.mission_generator.createMission(config_dict)
        print mission
        self.send_mission(mission, drone_addr) 

    def circle_test(self, drone_address, relative):
        """Fly the drone in a circle to test generation of circle missions."""
        mission_generator = MissionGenerator()
        rel_point = relative['relative']
        N = rel_point[0]
        E = rel_point[1]
        offset = np.array([N, E])
        config = mission_generator.create_config_dict(
            'circle', 0, 0, 0, 3, 4, False, np.array([4,4])
        )
        mission = mission_generator.createMission(config)
        self.launch_drone(drone_address)
        self.send_mission(mission, drone_address)

    def read_config(self, filename):
        """Read a config file to find the current mission_name.

        This is important for database access, you need the mission name so
        that you can correctly read the data from the current flight(s). This
        should definitely be the same mission name any currently flying drones
        are using.
        """
        with open(filename) as fp:
            config = json.load(fp)
        self.mission_name = config['mission_name']

    def run_test_mission(self, filename, drone_address):
        """Launch a drone and send it on a mission from a file."""
        mission = self.load_mission(
                filename
        )
        self.launch_drone(drone_address)
        self.send_mission(mission, drone_address)

    def demo_control_loop(self):
        """Run the October 2016 Terraswarm demo.

        This function sends the primary drone to fly a grid pattern over a
        rectangular area. It then monitors the data gathered by that drone and
        if it crosses the threshold specified when initializing the class, it
        sends the secondary drone to fly a relative triangle mission around the
        point where the threshold was crossed.
        """
        grid_mission = self.load_mission('courtyard1.json')
        self.launch_drone(self.primary_drone_addr)
        self.send_mission(grid_mission, self.primary_drone_addr)
        while True:
            data = self.get_data()
            #print data
            clean_data = self.clean_data(data)
            #print clean_data
            self.find_areas_of_interest(clean_data)
            print self.areas_of_interest
            while self.areas_of_interest:
                self.launch_drone(self.secondary_drone_addr)
                self.investigate_next_area()
                #pass
            time.sleep(1)

    def make_url(self, address, path):
        """Turn an address (not an IP) into a full URL for use with Flask."""
        url = address + path
        return url

    def launch_drone(self, drone_address):
        """Launch the drone at drone_address."""
        url = self.make_url(drone_address, 'launch')
        start_time = json.dumps({'start_time':time.time()})
        r = requests.post(url, start_time)
        return r

    def send_mission(self, mission_json, drone_address):
        """Send a mission (JSON string) to the drone at drone_address."""
        url = self.make_url(drone_address, 'mission')
        mission_string = json.dumps(mission_json)
        r = requests.post(url, mission_string)
        return r

    def create_point_mission(self, action, relative_point, name):
        """Create a mission (JSON string) and return it.

        action -- any valid action that can be used by the mission interface,
                  currently probably only works with 'go' and maybe 'land'.
        relative_point -- point in NED format to be used for the mission
        name -- the name of the point (points in missions need names,
                this can be whatever string your heart desires)
        """
        mission_dict = { 
            'points': {
                name: {
                    'N': relative_point[0],
                    'E': relative_point[1],
                    'D': relative_point[2],
                },
            },
            'plan': [
                {
                    'action': action,
                    'points': [name],
                    'repeat': 0,
                },
            ],
        }
        return mission_dict

    def load_mission(self, filename):
        """Load a mission (JSON string) from a JSON file."""
        with open(filename) as fp:
            mission = json.load(fp)
        return mission

    def establish_database_connection(self):
        """Setup the database connection through the sqlalchemy interface."""
        db_name = 'mission_data'
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_data(self):
        """Return all air sensor data from drone Alpha for current mission.

        This uses the sqlalchemy interface described in models.py to query the
        database for all the air sensor data from drone Alpha and the current
        mission, and match each air sensor reading with a GPS location.
        """
        with self.scoped_session() as session:
            a = aliased(AirSensorRead)
            g = aliased(GPSSensorRead)
            data = session.query(
                cast(a.time, Integer),
                a.air_data,
                g.latitude,
                g.longitude,
                g.altitude,
                a.id,
                g.relative,
            ).filter(
                cast(a.time, Integer) == cast(g.time, Integer),
            ).join(
                a.mission,
                a.drone,
            ).filter(
                Mission.name == self.mission_name,
                Drone.name == 'Alpha',
            ).all()
        return data

    def get_data_beta(self):
        """Return all GPS readings from drone Beta for the current mission."""
        with self.scoped_session() as session:
            g = aliased(GPSSensorRead)
            data = session.query(
                cast(g.time, Integer),
                g.latitude,
                g.longitude,
                g.altitude,
                g.relative,
                g.id,
            ).join(
                g.mission,
                g.drone,
            ).filter(
                Mission.name == self.mission_name,
                Drone.name == 'Beta',
            ).all()
        return data

    def clean_data(self, points):
        """Take list of records from the database and return list of points

        This function 'cleans' the data fetched from the database by get_data
        or get_data_beta (or anything else that fetches database data). It
        removes duplicate records, erroneous/fake/nonsense records, and formats
        the data into a nice list.
        """
        data = []
        for time, reading, lat, lon, alt, id, relative in points:
            # CHANGE for real vs fake
            try:
                #if 'Signal' in reading and bool(lat):
                if 'co2' in reading and bool(lat):
                    #print 'found reading'
                    #dat = [lat, lon, reading['Signal'], id]
                    dat = [lat, lon, reading['co2']['CO2'], id]
                    '''
                    if dat[2] > self.threshold:
                        print "cleaned interest", dat
                    '''
                    data.append(dat)
            except:
                pass
        # sort by ascending CO2 value then by latitude, so that we can remove
        # points with duplicate coordinates, keeping the point with the highest
        # CO2 reading.
        data.sort(key=lambda point: point[2])
        data.sort()
        delete = []
        for i in xrange(len(data) - 1):
            if data[i][0:2] == data[i + 1][0:2]:
                delete.append(i)
        for i in reversed(delete):
            data.pop(i)
        # print "Removed {0} duplicates".format(len(delete))
        return data
    
    def find_areas_of_interest(self, clean_data):
        """Add any sensor readings over the threshold to the list of AoIs.

        This compares all the CO2/GPS pairs in clean_data and adds any readings
        that are above the threshold and haven't been seen yet to the internal
        list of points to investigate. It keeps track of the highest database
        id it's seen so that it knows which points have been looked at before
        and which are new since the last time get_data was called.

        clean_data -- database data returned from self.clean_data()
        """
        for lat, lon, reading, id in clean_data:
            if (int(reading) > self.threshold) and (id > self.max_id):
                print "found interesting thing", reading
                self.areas_of_interest.append((lat, lon, reading, id))
        self.areas_of_interest = deque(sorted(self.areas_of_interest, key=lambda x: x[2], reverse=True))
        if self.areas_of_interest:
            self.max_id = max(self.areas_of_interest, key=lambda point: point[3])

    def investigate_next_area(self):
        """Send the secondary drone to investigate the next AoI."""
        lat, lon, reading, id = self.areas_of_interest.popleft()
        '''
        name = 'auto_generated_investigation_point_' + str(self.points_investigated)
        mission = self.create_point_mission('go', [lat, lon, self.secondary_height], name)
        '''
        self.relative_triangle(
            dc.secondary_drone_addr,
            'Beta',
            [lat, lon],
            radius=1,
        )
        print "launching second drone"
        #self.send_mission(mission, self.secondary_drone_addr)
        self.points_investigated += 1

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

    def get_ack(self, drone_address):
        """Request (and return) an acknowledgement from the drone."""
        url = self.make_url(drone_address, 'ack')
        r = requests.get(url)
        return r


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('primary_ip')
    parser.add_argument('secondary_ip')
    #parser.add_argument('filename')
    parser.add_argument('threshold')
    args = parser.parse_args()

    dc = DroneCoordinator(args.primary_ip, args.secondary_ip, args.threshold)

    dc.demo_control_loop()
    #dc.launch_drone(dc.primary_drone_addr)
    #dc.run_test_mission('courtyard1.json', dc.primary_drone_addr)
    interact(local=locals())

    '''
    dc.launch_drone(dc.primary_drone_addr)
    #dc.launch_drone(dc.secondary_drone_addr)
    '''

    #dc.relative_triangle(dc.secondary_drone_addr, 'Beta', [32.99111557, -117.127052307])
