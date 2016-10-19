from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, cast
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy.ext.declarative import declarative_base
from models import *
import numpy as np
from matplotlib.mlab import griddata
import matplotlib.pyplot as plt
from code import interact
import json
import time


class RTPlotter(object):
    def __init__(self):
        self.establish_database_connection()
        self.read_config('../database_files/mission_setup.json')
        plt.ion()
        self.plot_realtime()

    def generate_plot(self):
        points = self.get_data()
        print points 
        data = self.clean_data(points)
        x = [lat for lat, lon, reading in data]
        y = [lon for lat, lon, reading in data]
        z = [reading for lat, lon, reading in data]
        print 'testing'
        xmin, xmax = min(x), max(x)
        ymin, ymax = min(y), max(y)
        # x is flipped because negative lon is west...?
        xi = np.linspace(xmin, xmax, 100)
        yi = np.linspace(ymin, ymax, 100)
        zi = griddata(x, y, z, xi, yi)
        CS = plt.contour(xi,yi,zi,15,linewidths=0.5,colors='k')
        CS = plt.contourf(xi,yi,zi,15,cmap=plt.cm.jet)
        # colorbar is buggy as hell while in a loop, no time to fuss with now
        plt.colorbar()
        plt.scatter(x,y,marker='o',c='b',s=5)
        plt.xlim(xmin,xmax)
        plt.ylim(ymin,ymax)

    def plot_realtime(self):
        while True:
            try:
                self.generate_plot()
                plt.pause(0.05)
                plt.clf()
            except KeyboardInterrupt:
                break

    def establish_database_connection(self):
        db_name = 'mission_data'
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    # TODO: this is in two places in this project now, probs needs to be in
    # like a utils file or something
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

    def read_config(self, filename):
        with open(filename) as fp:
            config = json.load(fp)
        self.mission_name = config['mission_name']

    def get_data(self):
        with self.scoped_session() as session:
            a = aliased(AirSensorRead)
            g = aliased(GPSSensorRead)
            data = session.query(
                cast(a.time, Integer),
                a.air_data,
                g.latitude,
                g.longitude,
                g.altitude
            ).filter(
                cast(a.time, Integer) == cast(g.time, Integer),
            ).join(
                a.mission,
            ).filter(
                Mission.name == self.mission_name,
            ).all()
        return data

    def clean_data(self, points):
        """
        data = []
        for time, reading, lat, lon, alt in points:
            try:
                data.append([lat, lon, reading['co2']['CO2']])
            except Exception as e:
                print 'foo'
        """
        #data = [[lat, lon, reading['co2']['CO2']] for time, reading, lat, lon, alt in points]
        data = []
        for time, reading, lat, lon, alt in points:
            if 'co2' in reading and bool(lat):
                dat = [lat, lon, reading['co2']['CO2']]
                data.append(dat)
            elif 'CO2' in reading and bool(lat):
                dat = [lat, lon, reading['CO2']]
                data.append(dat)
        data.sort()
        delete = []
        for i in xrange(len(data) - 1):
            if data[i][0:2] == data[i + 1][0:2]:
                delete.append(i)
        for i in reversed(delete):
            data.pop(i)
        #print "Removed {0} duplicates for plotting".format(len(delete))
        return data

if __name__ == '__main__':
   rtp = RTPlotter() 
