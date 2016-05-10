import dronekit
from dronekit import connect, VehicleMode, LocationGlobalRelative, LocationGlobal
import time
import math
import argparse
from nav_utils import relative_to_global, get_distance_meters, Waypoint, read_wp_file

#Set up option parsing to get connection string
class AutoPilot(object):
    def __init__(self):
        parser = argparse.ArgumentParser(
                description='Commands vehicle using vehicle.simple_goto.'
                )
        parser.add_argument(
                '--connect',
                help=("Vehicle connection target string. "
                      "If not specified, SITL automatically started and used.")
                )
        args = parser.parse_args()
        self.connection_string = args.connect
        self.groundspeed = 10

    def run_mission(self):
        self.start_wp()
        self.goto_waypoints()
        self.RTL_and_land

    def start_wp(self):
        self.waypoints = read_wp_file()
        self.bringup_drone()
        self.arm_and_takeoff(15)

    def goto_waypoints(self):
        for wp in self.waypoints:
            global_rel = self.wp_to_global_rel(wp)
            self.goto_global_rel(global_rel)

    def bringup_drone(self):
        if not args.connect:
            #Connect to SITL if no connection string specified
            self.connection_string = '127.0.0.1:14550'
        else:
            #Connect to the Vehicle
            print 'Connecting to vehicle on: %s' % connection_string
            self.vehicle = connect(connection_string, wait_ready=True)

    def arm_and_takeoff(aTargetAltitude):
        """
        Arm vehicle and fly to aTargetAltitude.
        """
        print "Basic pre-arm checks"
        # Don't try to arm until autopilot is ready
        while not self.vehicle.is_armable:
            print " Waiting for vehicle to initialise..."
            time.sleep(1)

        print "Getting vehicle commands"
        cmds = self.vehicle.commands
        cmds.download()
        cmds.wait_ready()

        print "Home location is " + str(self.vehicle.home_location)

        print "Arming motors"
        # Copter should arm in GUIDED mode
        self.vehicle.mode = VehicleMode("GUIDED")
        self.vehicle.armed = True

        # Confirm vehicle armed before attempting to take off
        while not self.vehicle.armed:
            print " Waiting for arming..."
            time.sleep(1)

        print "Taking off!"
        self.vehicle.simple_takeoff(aTargetAltitude) # Take off to target alt

        # Wait until the self.vehicle reaches a safe height before processing
        # the goto (otherwise the command after Vehicle.simple_takeoff will
        # execute immediately).
        while True:
            print " Altitude: ", self.vehicle.location.global_relative_frame.alt
            #Break and return from function just below target altitude.
            if (self.vehicle.location.global_relative_frame.alt >= 
                aTargetAltitude*0.95):
                print "Reached target altitude"
                break
            time.sleep(1)

    def wp_to_global_rel(self, waypoint):
        waypoint_global_rel = relative_to_global(
                self.vehicle.home_location,
                waypoint.dNorth,
                waypoint.dEast,
                waypoint.alt_rel
                )
        return waypoint_global_rel

    def goto_global_rel(self, global_relative):
        offset = get_distance_meters(
                self.vehicle.location.global_relative_frame,
                global_relative
                )
        self.vehicle.simple_goto(global_relative, groundspeed=self.groundspeed)
        while offset > 2 and self.vehicle.mode.name == "GUIDED":
            offset = get_distance_meters(
                    self.vehicle.location.global_relative_frame,
                    global_relative
                    )
            time.sleep(1)
        print "Arrived at global_relative."

    def RTL_and_land(self):
        home_hover = relative_to_global(
                self.vehicle.home_location,
                0,
                0,
                15
                )
        self.goto_global_rel_wp(home_hover)
        self.vehicle.mode = VehicleMode("LAND")
        self.shutdown_vehicle()

    def shutdown_vehicle(self):
        #Close vehicle object before exiting script
        print "Closing vehicle"
        self.vehicle.close()

if __name__ == "__main__":
    ap = AutoPilot()
    ap.run_mission()

self.arm_and_takeoff(10)
print "altitude: " + str(self.vehicle.location.local_frame.down)

# print "Set default/target airspeed to 3"
# vehicle.airspeed = 3
self.vehicle.groundspeed=10

print "Going towards first point for 30 seconds ..."
point1 = relative_to_global(self.vehicle.home_location, 40, 40, 10)
self.vehicle.simple_goto(point1, groundspeed=10)
print str(self.vehicle.home_location)

# sleep so we can see the change in map
time.sleep(10)

print "Going towards second point for 30 seconds (groundspeed set to 10 m/s) ..."
print str(self.vehicle.home_location)
point2 = relative_to_global(self.vehicle.home_location, 0, 40, 10)
self.vehicle.simple_goto(point2, groundspeed=10)
