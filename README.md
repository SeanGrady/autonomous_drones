# The Drone Project

![Finding a single fire](/screenshots/plume_discovery_path.png)
_Finding and mapping a single fire by an initial grid search to discover the smoke plume, gradient tracking to find the source, and subsequent area mapping._

![Distractions](/screenshots/fiesta_island_plot.png)
_Map of a fire and smoke plume on a windy beach, you can see where the drones got a little distracted by lots of car exhaust from the parking lot in the upper left._

![Watching multiple simulated drones with APM planner](/screenshots/top_gun.png)
_Watching multiple simulated drones with APM planner._


## Project Notes
* Things ending in *mission.py are missions meant to be run on the drone. 
* All the tests are currently in ``src/test.py`` 
* ``simulator.py`` is the most up-to-date way to run multiple instances of the drone in the SITL (software-in-the-loop) simulator. 
* Use [APM Planner](http://www.ardupilot.org/planner2/) to connect to the simulated drone to get some visual output about what it's doing. For simulated drone instance N, each drone instance listens on port 5760 + 10*N for connections from a ground control station (such as APM Planner). 


Provided in this repo:
* Scripts to launch dronekit-sitl sessions. `simulator.py` allows for arbitrary numbers of drones 



## Installing Non-Python Dependencies
The only thing you should need is ``iperf``, which is needed for WiFi bandwidth measurements. Use your system's package manager. e.g.

    sudo apt-get install iperf
    brew install iperf 
    ...etc...


## Installing Python Dependencies
**For a host machine (not a drone):**

    pip install -r requirements_host.txt
This will install extra packages needed to run the simulator. 


**For the drone:**

    pip install -r requirements_drone.txt

## Running the tests

    cd src
    nosetests -v test.py 
One of the tests starts a simulator instance and waits for it to explore waypoints, so it may take a while. Run it with the ``-s`` option to get more output. 

