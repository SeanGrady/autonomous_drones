from pprint import pprint
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, cast
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy.ext.declarative import declarative_base
from models import *
import json

class SequenceGetter(object):
    def __init__(self):
        self.mission_name = 'berkeley_test_5'
        self.establish_database_connection()

    def establish_database_connection(self):
        db_name = 'mission_data'
        #db_url = 'mysql+mysqldb://dronebs:password@192.168.1.88/' + db_name
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def get_sequence(self):
        data = self.get_air_data()
        clean_data = self.clean_data(data)
        '''
        pprint(clean_data)
        json_string = json.dumps(clean_data)
        with open('dumped_sequence.json', 'w') as fp:
            fp.write(json_string)
        '''
        return clean_data

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

    def get_air_data(self):
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
        # this if/else is wonky but what are you gonna do with data with keys
        # like this? :/
        key = 'co2'
        for time, reading, lat, lon, alt, id in points:
            try:
                if bool(lat) and reading[key]['CO2'] > 0:
                    #print reading[key]
                    dat = (id, reading[key]['CO2'])
                    data.append(dat)
            except:
                pass
        data = set(data)
        raw_data = sorted(data, key=lambda x: x[0])
        raw_data = [reading for id, reading in raw_data]
        return raw_data

if __name__ == '__main__':
    sg = SequenceGetter()
    sequence = sg.get_sequence()
