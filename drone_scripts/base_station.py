from code import interact
import argparse
import requests
import json
import time
from collections import deque


class DroneCoordinator(object):
    def __init__(self, primary_drone_ip, secondary_drone_ip=None):
        self.primary_drone_addr = 'http://' + primary_drone_ip + ':5000/'
        if secondary_drone_ip:
            self.secondary_drone_addr = 'http://' + secondary_drone_ip + ':5000/'
        self.primary_height = 5
        self.secondary_height = 3
        self.max_id = 0
        self.points_investigated = 0
        self.establish_database_connection()
        self.areas_of_interest = deque([])
        self.establish_database_connection()

    def demo_control_loop(self):
        grid_mission = self.load_mission('demo_mission.json')
        self.launch_drone(self.primary_drone_addr)
        self.send_mission(grid_mission, self.primary_drone_addr)
        while True:
            data = self.get_data()
            clean_data = self.clean_data(data)
            self.find_areas_of_interest(clean_data)
            while self.areas_of_interest:
                self.investigate_next_area()
            time.sleep(1)

    def make_url(self, address, path):
        url = address + path
        return url

    def launch_drone(self, drone_address):
        url = self.make_url(drone_address, 'launch')
        start_time = json.dumps({'start_time':time.time()})
        r = requests.post(url, start_time)
        return r

    def send_mission(self, mission_json, drone_address):
        url = self.make_url(drone_address, 'mission')
        mission_string = json.dumps(mission_json)
        r = requests.post(url, mission_string)
        return r

    def create_goto_mission(self, relative_point, name):
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
                    'action': 'go',
                    'points': [name],
                    'repeat': 0,
                },
            ],
        }
        return mission_dict

    def load_mission(self, filename):
        with open(filename) as fp:
            mission = json.load(fp)
        return mission

    def establish_database_connection(self):
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_data(self):
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

    def clean_data(self, points):
        data = []
        for time, reading, lat, lon, alt, id in points:
            if 'co2' in reading and bool(lat):
                dat = [lat, lon, reading['co2']['CO2'], id]
                data.append(dat)
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
        #print "Removed {0} duplicates".format(len(delete))
        return data
    
    def find_areas_of_interest(self, clean_data):
        for lat, lon, reading, id in clean_data:
            if reading > self.co2_threshold and id > self.max_id:
                self.areas_of_interest.append((lat, lon, reading, id))
        self.max_id = max(self.areas_of_interest, key=lambda point: point[3])

    def investigate_next_area(self):
        lat, lon, reading = self.areas_of_interest.popleft()
        name = 'auto_generated_point_' + str(self.points_investigated)
        mission = self.create_goto_mission([lat, lon, self.secondary_height], name)
        self.send_mission(mission, self.secondary_drone_addr)
        self.points_investigated += 1

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

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('primary_ip')
    parser.add_argument('secondary_ip')
    args = parser.parse_args()

    dc = DroneCoordinator(args.primary_ip, args.secondary_ip)
