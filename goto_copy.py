"""
simple_goto.py: GUIDED mode "simple goto" example (Copter Only)

Demonstrates how to arm and takeoff in Copter and how to navigate to points using Vehicle.simple_goto.

Full documentation is provided at http://python.dronekit.io/examples/simple_goto.html
"""

import dronekit
from dronekit import connect, VehicleMode, LocationGlobalRelative, LocationGlobal
import time
import math

#Set up option parsing to get connection string
import argparse
parser = argparse.ArgumentParser(description='Commands vehicle using vehicle.simple_goto.')
parser.add_argument('--connect',
                   help="Vehicle connection target string. If not specified, SITL automatically started and used.")
args = parser.parse_args()

connection_string = args.connect
sitl = None


#Start SITL if no connection string specified
if not args.connect:
    """
    print "Starting copter simulator (SITL)"
    from dronekit_sitl import SITL
    sitl = SITL()
    sitl.download('copter', '3.3', verbose=True)
    sitl_args = ['-I0', '--model', 'quad', '--home=-35.363261,149.165230,584,353']
    sitl.launch(sitl_args, await_ready=True, restart=True)
    connection_string = 'tcp:127.0.0.1:14550'
    """
    connection_string = '127.0.0.1:14550'


# Connect to the Vehicle
print 'Connecting to vehicle on: %s' % connection_string
vehicle = connect(connection_string, wait_ready=True)


def relative_to_global(original_location, dNorth, dEast, alt_rel):
    """
    Returns a LocationGlobal object containing the latitude/longitude `dNorth` and `dEast` metres from the
    specified `original_location`. The returned LocationGlobal has the same `alt` value
    as `original_location`.

    The function is useful when you want to move the vehicle around specifying locations relative to
    the current vehicle position.

    The algorithm is relatively accurate over small distances (10m within 1km) except close to the poles.

    For more information see:
    http://gis.stackexchange.com/questions/2951/algorithm-for-offsetting-a-latitude-longitude-by-some-amount-of-meters
    """
    assert isinstance(original_location, LocationGlobal) or isinstance(original_location, LocationGlobalRelative)

    earth_radius=6378137.0 #Radius of "spherical" earth
    # Coordinate offsets in radians
    dLat = dNorth/earth_radius
    dLon = dEast/(earth_radius*math.cos(math.pi*original_location.lat/180))

    # New position in decimal degrees
    newlat = original_location.lat + (dLat * 180/math.pi)
    newlon = original_location.lon + (dLon * 180/math.pi)
    return LocationGlobalRelative(newlat, newlon, alt_rel)


def arm_and_takeoff(aTargetAltitude):
    """
    Arms vehicle and fly to aTargetAltitude.
    """

    print "Basic pre-arm checks"
    # Don't try to arm until autopilot is ready
    while not vehicle.is_armable:
        print " Waiting for vehicle to initialise..."
        time.sleep(1)

    print "Getting vehicle commands"
    cmds = vehicle.commands
    cmds.download()
    cmds.wait_ready()

    print "Home location is " + str(vehicle.home_location)

    print "Arming motors"
    # Copter should arm in GUIDED mode
    vehicle.mode = VehicleMode("GUIDED")
    vehicle.armed = True

    # Confirm vehicle armed before attempting to take off
    while not vehicle.armed:
        print " Waiting for arming..."
        time.sleep(1)

    print "Taking off!"
    vehicle.simple_takeoff(aTargetAltitude) # Take off to target altitude

    # Wait until the vehicle reaches a safe height before processing the goto (otherwise the command
    #  after Vehicle.simple_takeoff will execute immediately).
    while True:
        print " Altitude: ", vehicle.location.global_relative_frame.alt
        #Break and return from function just below target altitude.
        if vehicle.location.global_relative_frame.alt>=aTargetAltitude*0.95:
            print "Reached target altitude"
            break
        time.sleep(1)


alt = 10
arm_and_takeoff(10)
print "altitude: " + str(vehicle.location.local_frame.down)

# print "Set default/target airspeed to 3"
# vehicle.airspeed = 3
vehicle.groundspeed=10

print "Going towards first point for 30 seconds ..."
point1 = relative_to_global(vehicle.home_location, 40, 40, 10)
vehicle.simple_goto(point1, groundspeed=10)
print str(vehicle.home_location)


# sleep so we can see the change in map
time.sleep(10)

print "Going towards second point for 30 seconds (groundspeed set to 10 m/s) ..."
print str(vehicle.home_location)
point2 = relative_to_global(vehicle.home_location, 0, 40, 10)
vehicle.simple_goto(point2, groundspeed=10)



# sleep so we can see the change in map
time.sleep(30)

print "Returning to Launch"
vehicle.mode = VehicleMode("RTL")

#Close vehicle object before exiting script
print "Close vehicle object"
vehicle.close()

# Shut down simulator if it was started.
if sitl is not None:
    sitl.stop()
