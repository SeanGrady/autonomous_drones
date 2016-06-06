# The Drone Project

![Watching multiple drones with APM planner](https://github.com/sciencectn/drone_python/raw/master/screenshots/top_gun.png)
_Watching multiple simulated drones with APM planner_


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

