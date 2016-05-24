import drone_control
from multiprocessing import Process
import time

class SwarmSimulator(object):
    """
    A wrapper to handle multiple AutoPilot instances in parallel
    """

    @staticmethod
    def manage_drone(drone):
        drone.bringup_drone()
        drone.arm_and_takeoff(20)
        while True:
            drone.update_exploration()
            time.sleep(1)

    def __init__(self, n=1):
        """
        :param n: Number of drones to simulate
        """
        self.processes = []
        self.drones = []
        for i in xrange(n):
            self.drones.append(drone_control.AutoPilot(simulated=True))

    def start(self):
        for drone in self.drones:
            self.processes.append(Process(target=SwarmSimulator.manage_drone, args=(drone, )))
            self.processes[-1].start()
        for p in self.processes:
            p.join()


if __name__ == '__main__':
    s = SwarmSimulator(5)
    s.start()

