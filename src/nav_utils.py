import json
from dronekit import LocationGlobal, LocationGlobalRelative, LocationLocal
import math

def relative_to_global(original_location, dNorth, dEast, alt_rel):
    """
    Returns a LocationGlobal object containing the latitude/longitude dNorth
    and dEast metres from the specified original_location, at altitude of
    alt_rel, relative to the home location.
    """
    assert isinstance(original_location, LocationGlobal) or \
           isinstance(original_location, LocationGlobalRelative)

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
    Returns the ground distance in metres between two global locations (LocationGlobal or
    LocationGlobalRelative) or two local locations (LocationLocal)

    This method is an approximation, and will not be accurate over large
    distances and close to the earth's poles. It comes from the ArduPilot test
    code:
    https://github.com/diydrones/ardupilot/blob/master/Tools/autotest/common.py
    """
    if isinstance(aLocation1, (LocationGlobal, LocationGlobalRelative)) and\
        isinstance(aLocation2, (LocationGlobal, LocationGlobalRelative)):
        dlat = aLocation2.lat - aLocation1.lat
        dlong = aLocation2.lon - aLocation1.lon
        return math.sqrt((dlat*dlat) + (dlong*dlong)) * 1.113195e5
    else:
        assert isinstance(aLocation1, LocationLocal)
        assert isinstance(aLocation2, LocationLocal)
        dy = aLocation1.north - aLocation2.north
        dx = aLocation1.east - aLocation2.east
        return math.sqrt(dx*dx + dy*dy)

class Waypoint(object):
    def __init__(self, dNorth, dEast, alt_rel):
        assert dNorth is not None and -1 <= dNorth/50e3 <= 1
        assert dEast is not None and -1 <= dEast/50e3 <= 1
        assert alt_rel is not None
        self.dNorth = dNorth
        self.dEast = dEast
        self.alt_rel = alt_rel

    def __str__(self):
        return "Waypoint at ({0}, {1})m, alt {2}m (AMSL)".format(self.dEast, self.dNorth, self.alt_rel)

def read_wp_file():
    with open('waypoints.json') as wp_file:
        return json.load(wp_file)