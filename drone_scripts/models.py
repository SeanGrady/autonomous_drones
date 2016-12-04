"""Provide the database schema information sqlalchemy needs to run the ORM.

arguments:
    -f, --fuss  -- Allow you to fuss with the sqlalchemy metadata without
                   actually fussing with the database/running the code.
    -l, --local -- Use localhost for database connection.

This describes all the classes that sqlalchemy maps to the database tables, and
the relationships between them. It's some heavy stuff, if you want to dig into
it you're going to need to go on a voyage of discovery through the sqlalchemy
documentation. The 1.1 ORM tutorial is pretty helpful, and the sqlalchemy docs
in general are excellent.

As far as documenting each individual model, the standard is to not write
docstrings for them because they're tables and everything about them should
be obvious. It's really not obvious, though, if you're new to databases and
ORMs, so I will call out which tables are association tables and which are base
tables. I'll also of course put docstrings for any funny business that goes on.

You can run this from the command line to create all the tables in the database
if you're starting from scratch (it won't hurt to run it on an already
configured database). You can also run it with the -f or --fuss flag to have it
drop you into a python interpreter with a sqlalchemy session open if you want,
for example, to test out queries or see what python objects a specific query
returns, or to debug problems with sqlalchemy or queries or what have you.
"""
import re
import argparse
from code import interact
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import Column, DateTime, Integer, Float, String, create_engine, ForeignKey, JSON
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.orm import relationship, sessionmaker, backref, aliased

Base = declarative_base()

#sneaky regex
def snake_case(string):
    """Take a string in CamelCase and return it in snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', string)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


#I've did a clever thing :D
class MyMixin(object):
    """Provide a mixin class for the database tables defined later.
    
    This class defines the things common to all the models in this file, namely
    the id column and the table name. The other models then get inheret both
    mysql's base class and the mixin class.
    
    I've done sort of a weird thing here with the __tablename__ attribute
    because I want class names to be singular and CamelCase (because it's
    Python) but table names to be plural and snake_case, and hardcoding all the
    table names is for scrubs.
    """
    @declared_attr
    def __tablename__(cls):
        return (snake_case(cls.__name__) + 's')

    id = Column(Integer, primary_key=True)


class Sensor(MyMixin, Base):
    """Table for all the physical air/RF/GPS sensors that there are."""
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
    """Table for all the sensor types that there are."""
    sensor_type = Column(String(100), nullable=False)

    extant_sensors = relationship("Sensor", back_populates="sensor_type")


class SensorRead(MyMixin, Base):
    """Polymorphic table for all the sensor readings.

    This is some intense stuff, it's explained in the project's documentation.
    """
    mission_drone_sensor_id = Column(
            Integer,
            ForeignKey('mission_drone_sensors.id')
    )
    mission_drone_sensor = relationship(
            "MissionDroneSensor",
            back_populates='sensor_readings'
    )

    event_id = Column(Integer, ForeignKey('events.id'))
    event = relationship("Event", back_populates='sensor_reading')

    time = Column(DOUBLE(precision=12,scale=2))
    data_type = Column(String(50))

    __mapper_args__ = {'polymorphic_on': data_type}

    mission = relationship(
        'Mission',
        secondary='join(MissionDroneSensor, MissionDrone, MissionDroneSensor.mission_drone_id == MissionDrone.id)',
        primaryjoin='SensorRead.mission_drone_sensor_id == MissionDroneSensor.id',
        secondaryjoin='MissionDrone.mission_id == Mission.id',
        viewonly=True,
        uselist=False,
    )

    drone = relationship(
        'Drone',
        secondary='join(MissionDroneSensor, MissionDrone, MissionDroneSensor.mission_drone_id == MissionDrone.id)',
        primaryjoin='SensorRead.mission_drone_sensor_id == MissionDroneSensor.id',
        secondaryjoin='MissionDrone.drone_id == Drone.id',
        viewonly=True,
        uselist=False,
    )


class Event(MyMixin, Base):
    """Table for the events logged by the drones."""
    sensor_reading = relationship("SensorRead", uselist=False, back_populates='event')

    event_type_id = Column(Integer, ForeignKey('event_types.id'))
    event_type = relationship("EventType", back_populates='existing_events')

    event_data = Column(JSON)    


class EventType(MyMixin, Base):
    """Table for all the types of events which can be logged."""
    event_type = Column(String(100))

    existing_events = relationship("Event", back_populates='event_type')


class MissionDroneSensor(MyMixin, Base):
    """Association table between the MissionDrone and Sensor tables."""
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
    """Association table between the Mission and Drone tables."""
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
    """Table for all the missions that have been run."""
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
    """Table for all the drones that there are."""
    name = Column(String(100), nullable=False)
    FAA_ID = Column(String(100), nullable=False)

    # missions = relationship("MissionDrone", back_populates='drone')
    # missions = relationship("Mission", secondary='mission_drones')
    missions = association_proxy(
            'mission_drones',
            'mission',
            creator=lambda mission: MissionDrone(drone=None, mission=mission),
    )


class AirSensorRead(SensorRead):
    """Sub-table for air sensor reads."""
    __tablename__ = 'air_sensor_reads'
    #__tablename__ = snake_case(cls.__name__)
    __mapper_args__ = {'polymorphic_identity': 'air_sensor'}

    id = Column(Integer, ForeignKey('sensor_reads.id'), primary_key=True)
    air_data = Column(JSON)


class GPSSensorRead(SensorRead):
    """Sub-table for GPS sensor reads."""
    __tablename__ = 'GPS_sensor_reads'
    #__tablename__ = snake_case(cls.__name__)
    __mapper_args__ = {'polymorphic_identity': 'GPS_sensor'}

    id = Column(Integer, ForeignKey('sensor_reads.id'), primary_key=True)
    #remember that these should be global to avoid confusion
    latitude = Column(Float(precision='12,9'))
    longitude = Column(Float(precision='12,9'))
    altitude = Column(Float(precision='12,9'))
    relative = Column(JSON)


class RFSensorRead(SensorRead):
    """Sub-table for RF sensor reads."""
    __tablename__ = 'RF_sensor_reads'
    #__tablename__ = snake_case(cls.__name__)
    __mapper_args__ = {'polymorphic_identity': 'RF_sensor'}

    id = Column(Integer, ForeignKey('sensor_reads.id'), primary_key=True)
    #remember that these should be global to avoid confusion
    RF_data = Column(JSON)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
                '-f',
                '--fuss',
                help=('allow you to fuss with the sqlalchemy metadata without '
                      'actually fussing with the database/running the code'),
                action="store_true"
                )
    parser.add_argument(
                '-l',
                '--local',
                help=('use localhost for database connection'),
                action="store_true"
                )
    args = parser.parse_args()
    db_name = 'mission_data'
    if args.local:
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
    else:
        db_url = 'mysql+mysqldb://drone:drone1@192.168.1.88/' + db_name
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    if args.fuss:
        Session = sessionmaker(bind=engine)
        session = Session()
        md = Base.metadata
        print "Active session is available as 'session'"
        print "MetaData object is available as 'md'"
        interact(local=locals())
