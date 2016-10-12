import json
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from models import *


mission_name = "black_mountain_oct_9"
db_name = "mission_data"
db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)
session = Session()

air_records = session.query(
    AirSensorRead,
).join(
    AirSensorRead.mission,
).filter(
    Mission.name == mission_name,
).all()

CO2_readings = []
for thing in air_records:
    if 'co2' in thing.air_data:
        CO2_readings.append(thing.air_data['co2']['CO2'])

with open('oct_09_air_data.json', 'w') as fp:
    json.dump(CO2_readings, fp)
