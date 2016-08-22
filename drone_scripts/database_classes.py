from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SensorReading(Base):
    __tablename__ = 'sensor_readings'

    id = Column(Integer, primary_key=True)
    AQI = Column(Integer)
    mission_time = Column(Integer)
    lat = Column(Float)
    lon = Column(Float)
    alt = Column(Float)
