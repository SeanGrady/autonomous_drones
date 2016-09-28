import re
import argparse
from code import interact
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import Column, DateTime, Integer, Float, String, create_engine, ForeignKey, JSON
from sqlalchemy.orm import relationship, sessionmaker, backref

Base = declarative_base()

#sneaky regex
def snake_case(string):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', string)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

#I've did a clever thing :D
class MyMixin(object):

    # I've did a weird thing here because I want class names to be singular but
    # table names to be plural. This is maybe worse than hardcoding table names
    # but I'm lazy? Will have to think about it. Also maybe I don't want table
    # names to be plural?
    @declared_attr
    def __tablename__(cls):
        return (snake_case(cls.__name__) + 's')

    id = Column(Integer, primary_key=True)


#TODO: need a name column, or something. IDing actual hardware by database
#primary key is probably not the thing.
class Sensor(MyMixin, Base):
    sensor_type_id = Column(Integer, ForeignKey('sensor_types.id'))
    name = Column(String(50))
    sensor_type = relationship("SensorType", back_populates="extant_sensors")

    mission_drones = association_proxy(
            "mission_drone_sensors",
            "mission_drone",
            creator=lambda sensor: MissionDroneSensor(
                    sensor=sensor,
                    mission_drone=None
            ),
    )

class SensorType(MyMixin, Base):
    sensor_type = Column(String(100), nullable=False)

    extant_sensors = relationship("Sensor", back_populates="sensor_type")

class SensorRead(MyMixin, Base):
    sensor_instance = Column(Integer, ForeignKey('mission_drone_sensors.id'))
    mission_drone_sensor = relationship(
            "MissionDroneSensor",
            back_populates='sensor_readings'
    )

    event_id = Column(Integer, ForeignKey('events.id'))
    event = relationship("Event", back_populates='sensor_reading')

    mission_time = Column(Float)
    data_type = Column(String(50))

    __mapper_args__ = {'polymorphic_on': data_type}

class Event(MyMixin, Base):
    sensor_reading = relationship("SensorRead", uselist=False, back_populates='event')

    event_type_id = Column(Integer, ForeignKey('event_types.id'))
    event_type = relationship("EventType", back_populates='existing_events')

    event_data = Column(JSON)    

class EventType(MyMixin, Base):
    event_type = Column(String(100))

    existing_events = relationship("Event", back_populates='event_type')

class MissionDroneSensor(MyMixin, Base):
    readings = relationship("SensorRead", back_populates='mission_drone_sensor')

    mission_drone_id = Column(Integer, ForeignKey('mission_drones.id'))
    mission_drone = relationship(
                        'MissionDrone',
                        backref=backref('mission_drone_sensors',
                                        cascade="all, delete-orphan")
    )

    sensor_id = Column(Integer, ForeignKey('sensors.id'))
    sensor = relationship("Sensor", backref=backref('mission_drone_sensors',
                                        cascade="all, delete-orphan")
    )

    sensor_readings = relationship(
            "SensorRead",
            back_populates='mission_drone_sensor'
    )

    def __init__(self, sensor=None, mission_drone=None):
        self.sensor = sensor 
        self.mission_drone = mission_drone
    
class MissionDrone(MyMixin, Base):
    mission_id = Column(Integer, ForeignKey('missions.id'))
    # mission = relationship("Mission", back_populates='drones')
    mission = relationship("Mission", backref=backref('mission_drones',
                                        cascade="all, delete-orphan")
    )

    drone_id = Column(Integer, ForeignKey('drones.id'))
    drone = relationship("Drone", backref=backref('mission_drones',
                                                cascade="all, delete-orphan")
    )

    # sensors = relationship("Sensor", secondary='mission_drone_sensors')
    sensors = association_proxy(
            "mission_drone_sensors",
            "sensor",
            creator=lambda sensor: MissionDroneSensor(
                    sensor=sensor,
                    mission_drone=None
            ),
    )

    def __init__(self, drone=None, mission=None):
        self.drone = drone
        self.mission = mission

class Mission(MyMixin, Base):
    name = Column(String(100), nullable=False)
    date = Column(DateTime, nullable=False)
    location = Column(String(100), nullable=False)

    # drones = relationship("MissionDrone", back_populates="mission")
    # drones = relationship("Drone", secondary='mission_drones')
    drones = association_proxy(
            'mission_drones',
            'drone',
            creator=lambda drone: MissionDrone(drone=drone, mission=None),
    )

class Drone(MyMixin, Base):
    name = Column(String(100), nullable=False)
    FAA_ID = Column(String(100), nullable=False)

    # missions = relationship("MissionDrone", back_populates='drone')
    # missions = relationship("Mission", secondary='mission_drones')
    missions = association_proxy(
            'mission_drones',
            'mission',
            creator=lambda mission: MissionDrone(drone=None, mission=mission),
    )

#TODO: Ask Ryan what to do about frequently changing data structure
class AirSensorRead(SensorRead):
    __tablename__ = 'air_sensor_reads'
    #__tablename__ = snake_case(cls.__name__)
    __mapper_args__ = {'polymorphic_identity': 'air_sensor'}

    id = Column(Integer, ForeignKey('sensor_reads.id'), primary_key=True)
    AQI = Column(Integer)

class GPSSensorRead(SensorRead):
    __tablename__ = 'GPS_sensor_reads'
    #__tablename__ = snake_case(cls.__name__)
    __mapper_args__ = {'polymorphic_identity': 'GPS'}

    id = Column(Integer, ForeignKey('sensor_reads.id'), primary_key=True)
    #remember that these should be global to avoid confusion
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
                '-f',
                '--fuss',
                help=('allow you to fuss with the sqlalchemy metadata without '
                      'actually fussing with the database/running the code'),
                action="store_true"
                )
    args = parser.parse_args()
    db_name = 'mission_data'
    db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    if args.fuss:
        Session = sessionmaker(bind=engine)
        session = Session()
        md = Base.metadata
        print "Active session is available as 'session'"
        print "MetaData object is available as 'md'"
        interact(local=locals())
