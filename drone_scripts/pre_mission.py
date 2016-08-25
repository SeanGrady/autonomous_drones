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
import models
import datetime

with open('mission_setup.json') as fp:
    setup_dict = json.load(fp)

db_name = 'simple_test'
db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

#setup a mission
new_mission = Missions(name=setup['name'],
                   date=datetime.now(),
                   location=setup['location'])
session.add(new_mission)

#setup the according mission_drones record(s)
mission_drones = []
for drone_name in setup['drone_names']:
    drone = session.query(Drones).filter(Drones.name == drone_name).one()
    mission_drone = MissionDrones()
    mission_drone.mission = new_mission
    mission_drone.drone = drone
    mission_drones.append(mission_drone)
session.add_all(mission_drones)

#setup the according mission_drone_sensors record(s)
mission_drone_sensors = []
for sensor_id, drone_name in setup['sensors'].iteritems():
    mission_drone = session.query(MissionDrones).\
                           join(Drones, Missions).\
                           filter(Drones.name == drone_name).\
                           filter(Missions.name == setup['name']).\
                           one()
    sensor = session.query(Sensors).filter(Sensors.id == sensor_id).one()
    mission_drone_sensor = MissionDroneSensors()
    mission_drone_sensor.mission_drone = mission_drone
    mission_drone_sensor.sensor = sensor
    mission_drone_sensors.append(mission_drone_sensor)
session.add_all(mission_drone_sensors)

session.commit()
session.close()
