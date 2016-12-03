"""
This script plots data (currently air or RF data) from the database. It should
be run from the command line with an argument that is either 'air' or 'RF':

python matlabplotting.py 'air'

python matlabplotting.py 'RF'

It's also setup to 'replay' the plot in real time
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, cast
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, aliased
from sqlalchemy.ext.declarative import declarative_base
from models import *
import numpy as np
from scipy.spatial import ConvexHull
from matplotlib.mlab import griddata
import matplotlib.pyplot as plt
from code import interact
import json
import time
import copy


class RTPlotter(object):
    def __init__(self, datatype):
        self.establish_database_connection()
        self.read_config('../database_files/mission_setup.json')
        self.datatype = datatype
        self.real_time = False
        self.start_time = time.time()
        plt.ion()
        self.plot_realtime()

    def generate_plot(self):
        """Generate a plot, limited by timestamps if 'self.real_time' is True.

        This function is long and complicated, but it's plotting so what can
        you do. Chris wrote the vast majority of it and is in general much more
        experienced with plotting stuff than I am, so questions should probably
        go to him. I can tell you that qhull and griddata are troublesome.

        Griddata is written in C and doesn't raise errors properly, so if it
        breaks the program will segfault and you can't catch it in a try/except
        block or anything else. 

        qhull and griddata both complain when they haven't enough points to
        plot, and for some reason adding points to qhull one at a time seems to
        break often. \(O_o)/
        """
        if self.datatype == 'air':
            air_points = self.get_air_data()
            #print air_points
            air_data = self.clean_data(air_points)
            data = air_data
        elif self.datatype == 'RF':
            RF_points = self.get_RF_data()
            RF_data = self.clean_data(RF_points)
            data = RF_data
        pos_points = self.get_pose_data()
        # This whole thing is weird and doesn't work well. 
        if self.real_time:
            time_disparity = int(time.time() - self.start_time)
            mission_start = min(pos_points, key=lambda x: x[3])[3]
            sliced_data = []
            for point in data:
                disp = point[3] - mission_start
                if disp <= time_disparity:
                    sliced_data.append(point)
            sliced_pos_points = []
            for point in pos_points:
                disp = point[3] - mission_start
                if disp <= time_disparity:
                    sliced_pos_points.append(point)
            data = copy.deepcopy(sliced_data)
            pos_points = copy.deepcopy(sliced_pos_points)
            # should be 5 if using qhull
            if len(data) < 6:
                self.start_time -= 5.0
                return False

        '''
        try:
            hull = ConvexHull(data)
        except:
            return False
        flat = hull.simplices.flatten()
        index = list(set(flat))
        #interact(local=locals())
        points = np.array(data)[index]
        x = [point[0] for point in points]
        y = [point[1] for point in points]
        z = [point[2] for point in points]
        '''
        x = [reading[0] for reading in data]
        y = [reading[1] for reading in data]
        z = [reading[2] for reading in data]
        xmin, xmax = min(x), max(x)
        ymin, ymax = min(y), max(y)
        xi = np.linspace(xmin, xmax, 100)
        yi = np.linspace(ymin, ymax, 100)
        # This griddata thing is exceeingly problematic, it doesn't pass
        # errors up, it just segfaults. I need a Bad Code Whistle.
        zi = griddata(x, y, z, xi, yi)
        #xi, yi, zi = x, y, z
        CS = plt.contour(xi,yi,zi,15,linewidths=0.5,colors='k')
        CS = plt.contourf(xi,yi,zi,15,cmap=plt.cm.jet)
        # colorbar is buggy as hell while in a loop, no time to fuss with now
        plt.colorbar()
        #plt.scatter(32.882220, -117.234546)
        pos_x = [point[0] for point in pos_points]
        pos_y = [point[1] for point in pos_points]
        #print pos_points
        plt.scatter(x, y, s=100)
        plt.plot(pos_x, pos_y, '-m', lw=3)
        #plt.xlim(xmin,xmax)
        #plt.ylim(ymin,ymax)
        plt.gca().invert_yaxis()
        return True

    def get_pose_data(self):
        """Get all the GPS readings for Alpha from the current mission."""
        with self.scoped_session() as session:
            g = aliased(GPSSensorRead)
            data = session.query(
                g.latitude,
                g.longitude,
                g.altitude,
                cast(g.time, Integer),
                g.id,
            ).join(
                g.mission,
                g.drone,
            ).filter(
                Mission.name == self.mission_name,
                Drone.name == 'Alpha',
            ).all()
        return data

    def plot_realtime(self):
        """Make and replot the plot every 0.5 seconds."""
        while True:
            try:
                result = self.generate_plot()
                plt.pause(0.5)
                if(result):
                    plt.clf()
            except KeyboardInterrupt:
                break

    def establish_database_connection(self):
        """Setup database connection and sqlalchemy interface."""
        db_name = 'mission_data'
        #db_url = 'mysql+mysqldb://dronebs:password@192.168.1.88/' + db_name
        db_url = 'mysql+mysqldb://root:password@localhost/' + db_name
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    # TODO: this is in two places in this project now, probs needs to be in
    # like a utils file or something
    @contextmanager
    def scoped_session(self):
        """Provide a context manager for database access."""
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
        """Read config file to get the name of the mission to plot."""
        with open(filename) as fp:
            config = json.load(fp)
        self.mission_name = config['mission_name']

    def get_air_data(self):
        """Get all the air data from Alpha that is matched with a GPS loc."""
        with self.scoped_session() as session:
            a = aliased(AirSensorRead)
            g = aliased(GPSSensorRead)
            data = session.query(
                cast(a.time, Integer),
                a.air_data,
                g.latitude,
                g.longitude,
                g.altitude,
                g.id,
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

    def get_RF_data(self):
        """Get all the RF data that is matched with a GPS loc."""
        with self.scoped_session() as session:
            r = aliased(RFSensorRead)
            g = aliased(GPSSensorRead)
            data = session.query(
                cast(r.time, Integer),
                r.RF_data,
                g.latitude,
                g.longitude,
                g.altitude,
                g.id,
            ).filter(
                cast(r.time, Integer) == cast(g.time, Integer),
            ).join(
                r.mission,
                r.drone
            ).filter(
                Mission.name == self.mission_name,
            ).all()
        return data

    def clean_data(self, points):
        """Clean database data and return a list of lists for plotting.

        This should return whatever generate_plot() needs to do its thing. Be
        careful with the indexes when playing around with it. If you wanted to
        make it more robust, I'd recommend having it return a dictionary and
        changing generate_plot to reference keys instead of indices. 
        """
        data = []
        # this if/else is wonky but what are you gonna do with data with keys
        # like this? :/
        if self.datatype == 'air':
            key = 'co2'
            for time, reading, lat, lon, alt, id in points:
                try:
                    if bool(lat) and (key in reading) and reading[key]['CO2'] > 0:
                        #print reading[key]
                        dat = [lat, lon, reading[key]['CO2'], time]
                        data.append(dat)
                    elif 'CO2' in reading and reading['CO2'] > 0:
                        dat = [lat, lon, reading['CO2'], time]
                        data.append(dat)
                except:
                    pass
        elif self.datatype == 'RF':
            key = 'Signal'
            for time, reading, lat, lon, alt, id in points:
                if bool(lat):
                    dat = [lat, lon, int(reading[key]), id]
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
    parser = argparse.ArgumentParser()
    parser.add_argument('datatype')
    args = parser.parse_args()
    rtp = RTPlotter(args.datatype) 
