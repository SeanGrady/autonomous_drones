'''
This file should read from mission_setup.json and add everything to the database
that needs to be added before each mission:
   *The mission details: Name, Location, etc
   *Which Drones are on the mission
   *Which sensors are on each drone
'''

import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from models import *
from datetime import datetime
from code import interact

with open('mission_setup.json') as fp:
    setup = json.load(fp)

db_name = 'mission_data_test'
db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

#setup a mission and associate drones (creates all mission_drones needed)
new_mission = Missions(name=setup['mission_name'],
                   date=datetime.now(),
                   location=setup['location'])

drones = session.query(
            Drones
         ).filter(
            Drones.name.in_(setup['drone_names'])
         ).all()
#import pdb; pdb.set_trace()
new_mission.drones = drones
session.add(new_mission)

#setup the according mission_drone_sensors record(s)
mission_drone_sensors = []
for sensor_id, drone_name in setup['sensors'].iteritems():
    sensor_id = int(sensor_id)
    print drone_name, sensor_id, setup['mission_name']
    #import pdb; pdb.set_trace()
    mission_drone = session.query(
        MissionDrones,
    ).join(
        Drones,
    ).join(
        Missions,
    ).filter(
        Drones.name == drone_name,
        Missions.name == setup['mission_name']
    ).one()
    print mission_drone
    sensor = session.query(Sensors).filter(Sensors.id == sensor_id).one()
    mission_drone.sensors.append(sensor)

session.commit()
session.close()
