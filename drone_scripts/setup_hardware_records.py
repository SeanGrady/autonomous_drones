"""
This file reads drones_and_sensors.json and sets up the entries in the
sensor_types, sensors, and drones tables needed to start adding missions and
readings. It should be run if the database gets wiped and needs to be reset.
Currently it is not set up to add new drones/sensors/sensor_types, but it could
easily be with modification of drones_and_sensors.json
"""

import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from models import *
from datetime import datetime
from code import interact

with open('../database_files/drones_and_sensors.json') as fp:
    setup = json.load(fp)

db_name = 'mission_data'
db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

for drone in setup['drones']:
    new_drone = Drone(name=drone['name'], FAA_ID=drone['FAA_ID'])
    session.add(new_drone)

for sns_type in setup['sensor_types']:
    new_type = SensorType(sensor_type=sns_type)
    session.add(new_type)

for sensor in setup['sensors']:
    s_type = session.query(SensorType).filter(SensorType.sensor_type==sensor['type']).one()
    new_sensor = Sensor(sensor_type_id=s_type.id, name=sensor['name'])
    session.add(new_sensor)

for event_primative in setup['events']:
    new_event_type = EventType(event_type=event_primative['type'])
    session.add(new_event_type)

session.commit()
session.close()
