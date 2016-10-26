from pprint import pprint
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, cast
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy.ext.declarative import declarative_base
from models import *
import json
import requests
import time


class GDPPoster(object):
    def __init__(self):
        self.max_id_alpha = 0
        self.max_id_beta= 0
        self.mission_name = 'berkeley_test_6'
        self.clear_gdp_plot()
        self.establish_database_connection()
        self.post_loop()

    def post_loop(self):
        while True:
            data = self.get_gps_data('Alpha')
            clean_data = self.clean_data(data)
            self.send_new_poses_alpha(clean_data)
            data = self.get_gps_data('Beta')
            clean_data = self.clean_data(data)
            self.send_new_poses_beta(clean_data)
            time.sleep(0.5)

    def clear_gdp_plot(self):
        # TODO: implement this
        '''
        url = 'http://swarmnuc1022.eecs.berkeley.edu/8082?x=' + str(x) + '&y=' + str(y)
        response = request.get(url)
        '''
        pass

    def establish_database_connection(self):
        db_name = 'mission_data'
        #db_url = 'mysql+mysqldb://dronebs:password@192.168.1.88/' + db_name
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def post_position_data(self, data, drone):
        x, y = data
        if drone == 'Alpha':
            try:
                url = 'http://swarmnuc1022.eecs.berkeley.edu/8082?x=' + str(x) + '&y=' + str(y)
            except:
                pass
        elif drone == 'Beta':
            try:
                url = 'http://swarmnuc1022.eecs.berkeley.edu/8083?x=' + str(x) + '&y=' + str(y)
            except:
                pass
        response = requests.get(url)

    def send_new_poses_alpha(self, clean_data):
        for id, lat, lon in clean_data:
            if id > self.max_id_alpha:
                #print lat, lon
                self.post_position_data([lat, lon], 'Alpha')
        if clean_data:
            self.max_id_alpha = max(clean_data, key=lambda point: point[0])

    def send_new_poses_beta(self, clean_data):
        for id, lat, lon in clean_data:
            if id > self.max_id_beta:
                #print lat, lon
                self.post_position_data([lat, lon], 'Beta')
        if clean_data:
            self.max_id_beta = max(clean_data, key=lambda point: point[0])

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

    def get_gps_data(self, drone):
        with self.scoped_session() as session:
            g = aliased(GPSSensorRead)
            data = session.query(
                g.latitude,
                g.longitude,
                g.id,
            ).join(
                g.mission,
                g.drone,
            ).filter(
                Mission.name == self.mission_name,
                Drone.name == drone,
            ).all()
        return data

    def clean_data(self, points):
        data = []
        # this if/else is wonky but what are you gonna do with data with keys
        # like this? :/
        key = 'co2'
        for lat, lon, id in points:
            try:
                dat = (id, lat, lon)
                data.append(dat)
            except:
                pass
        data = set(data)
        raw_data = sorted(data, key=lambda x: x[0])
        return raw_data

if __name__ == '__main__':
    poster = GDPPoster()
