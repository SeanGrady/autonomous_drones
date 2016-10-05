from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from models import *

class NimasObject(object):
    def __init__(self):
        self.db_url = 'mysql+mysqldb://root:password@localhost/' + db_name

    def create_database_connection(self):
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

    def add_record_example(self, data):
        with self.scoped_session() as session:
            air_event_type = session.query(
                EventType,
            ).filter(
                EventType.event_type == 'air_sensor_data',
            ).one()
            new_event_instance = Event(
                event_type=air_event_type,
                event_data={'sensor':'GDP_ground_sensor'},
            )
            reading = AirSensorRead(
                air_data=data,
                mission_drone_sensor=GDP_sensor,
                event=new_event_instance,
                mission_time=
