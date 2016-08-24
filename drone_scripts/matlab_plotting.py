# Saving this for later
    def plot(self, block=False, time=0.05):
        """
        Plot the currently stored data as a contour plot using matplotlib

        In the plot:
        x,y are lon, lat
        z is the sensor value for that location

        :param block:
        :return:
        """
        import numpy as np
        from matplotlib.mlab import griddata
        import matplotlib.pyplot as plt
        self.matplotlib_imported = True

        if len(self._data_points) < 5:
            return
        try:
            all = [[d.lon, d.lat, d.value] for d in self._data_points]
            all.sort()
            delete = []
            for i in xrange(len(all) - 1):
                if all[i][0:2] == all[i + 1][0:2]:
                    delete.append(i)
            for i in reversed(delete):
                all.pop(i)
            print "Removed {0} duplicates for plotting".format(len(delete))
            coords = [np.array(a[0:2]) for a in all]
            z = [a[2] for a in all]

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
