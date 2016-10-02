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


class RTPlotter(object):
    def __init__(self):
        self.establish_database_connection()
        self.read_config('../database_files/mission_setup.json')
        self.data = self.get_data()
        self.plot()

    def plot_realtime(self):
        pass

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
                cast(a.mission_time, Integer),
                a.air_data,
                g.latitude,
                g.longitude,
                g.altitude
            ).filter(
                cast(a.mission_time, Integer) == cast(g.mission_time, Integer),
            ).all()
        return data

    def plot(self, block=False, time=0.05):
        """
        Plot the currently stored data as a contour plot using matplotlib

        In the plot:
        x,y are lon, lat
        z is the sensor value for that location

        :param block:
        :return:
        """
        self.matplotlib_imported = True

        if len(self.data) < 5:
            return
        try:
            #all_points = [[d.lon, d.lat, d.value] for d in self._data_points]
            # TODO: figure out how to split this next line properly
            all_points = [[lon, lat, data['CO2']] for time, data, lat, lon, alt in self.data]
            all_points.sort()
            delete = []
            for i in xrange(len(all_points) - 1):
                if all_points[i][0:2] == all_points[i + 1][0:2]:
                    delete.append(i)
            for i in reversed(delete):
                all_points.pop(i)
            print "Removed {0} duplicates for plotting".format(len(delete))
            coords = [np.array(a[0:2]) for a in all_points]
            z = [a[2] for a in all_points]

            first = z[0]
            all_same = True
            for val in z:
                if val != first:
                    all_same = False
                    break
            if all_same:
                print "all values are the same, not plotting"
                return

            lower_left = np.minimum.reduce(coords)
            upper_right = np.maximum.reduce(coords)
            print np.linalg.norm(upper_right - lower_left)
            if np.linalg.norm(upper_right - lower_left) < 0.00001:
                print "points are not varied enough, not plotting"
                return  # Points are not varied enough to plot

            # fig, ax = plt.subplot(1,1)
            plt.clf()
            x = [c[0] for c in coords]
            y = [c[1] for c in coords]
            xi = np.linspace(lower_left[0], upper_right[0], 200)
            yi = np.linspace(lower_left[1], upper_right[1], 200)
            zi = griddata(x, y, z, xi, yi)
            CS_lines = plt.contour(xi, yi, zi, 15, linewidths=0.5, colors='k')
            CS_colors = plt.contourf(xi, yi, zi, 15, cmap=plt.cm.rainbow,
                                     vmax=abs(zi).max(), vmin=-abs(zi).max())
            cbar = plt.colorbar(CS_colors)
            cbar.ax.set_ylabel("Value")
            cbar.add_lines(CS_lines)
            plt.scatter(x, y, marker='o', c='b', s=5, zorder=10)
            plt.xlim(lower_left[0], upper_right[0])
            plt.ylim(lower_left[1], upper_right[1])
            plt.title('Air data samples')
            plt.xlabel("Longitude")
            plt.ylabel("Latitude")
            if block:
                plt.plot()
                plt.show()
            else:
                plt.pause(time)
            
        except ValueError as e:
            print e.__repr__()  # STFU

if __name__ == '__main__':
   rtp = RTPlotter() 
