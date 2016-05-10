import json
from dronekit import LocationGlobal, LocationGlobalRelative
import math

def relative_to_global(original_location, dNorth, dEast, alt_rel):
    """
    Returns a LocationGlobal object containing the latitude/longitude dNorth
    and dEast metres from the specified original_location, at altitude of
    alt_rel, relative to the home location.
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

def get_distance_meters(aLocation1, aLocation2):
    """
    Returns the ground distance in metres between two LocationGlobal or
    LocationGlobalRelative objects.

    This method is an approximation, and will not be accurate over large
    distances and close to the earth's poles. It comes from the ArduPilot test
    code:
    https://github.com/diydrones/ardupilot/blob/master/Tools/autotest/common.py
    """
    dlat = aLocation2.lat - aLocation1.lat
    dlong = aLocation2.lon - aLocation1.lon
    return math.sqrt((dlat*dlat) + (dlong*dlong)) * 1.113195e5

class Waypoint(object):
    def __init__(self, dNorth, dEast, alt_rel):
        self.dNorth = dNorth
        self.dEast = dEast
        self.alt_rel = alt_rel

def read_wp_file():
    with open('waypoints.json') as wp_file:
        return json.load(wp_file)
