import json
from dronekit import LocationGlobal, LocationGlobalRelative, LocationLocal
import math
from geopy.distance import vincenty

def relative_to_global(original_location, dNorth, dEast, alt_rel):
    """
    Returns a LocationGlobalRelative object containing the latitude/longitude
    dNorth and dEast metres from the specified original_location, at altitude
    of alt_rel, relative to the home location.
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

def relative_to_waypoint(global_rel):
    return 

def lat_lon_distance(lat1, lon1, lat2, lon2):
    return vincenty((lat1, lon1), (lat2, lon2)).meters

def get_ground_distance(aLocation1, aLocation2):
    """
    Returns the ground distance in metres between two global locations
    (LocationGlobal or LocationGlobalRelative) or two local locations
    (LocationLocal)

    This method is an approximation, and will not be accurate over large
    distances and close to the earth's poles. It comes from the ArduPilot test
    code:
    https://github.com/diydrones/ardupilot/blob/master/Tools/autotest/common.py

    """
    if isinstance(aLocation1, (LocationGlobal, LocationGlobalRelative)) and\
        isinstance(aLocation2, (LocationGlobal, LocationGlobalRelative)):
        return lat_lon_distance(aLocation1.lat, aLocation1.lon, aLocation2.lat, aLocation2.lon)
    else:
        assert isinstance(aLocation1, LocationLocal)
        assert isinstance(aLocation2, LocationLocal)
        dy = aLocation1.north - aLocation2.north
        dx = aLocation1.east - aLocation2.east
        return math.sqrt(dx*dx + dy*dy)

def get_distance(location1, location2):
    """
    Get the distance between 2 location objects
    They must be of the same type

    :param location1:
    :param location2:
    :return:
    """
    d = get_ground_distance(location1, location2)
    dAlt = None
    if isinstance(location1, LocationGlobal) and isinstance(location2, LocationGlobal):
        dAlt = location1.alt - location2.alt
    elif isinstance(location1, LocationGlobalRelative) and isinstance(location2, LocationGlobalRelative):
        dAlt = location1.alt - location2.alt
    else:
        assert isinstance(location1, LocationLocal)
        assert isinstance(location2, LocationLocal)
        dAlt = location1.down - location2.down
    return math.sqrt(d**2 + dAlt**2)

class Waypoint(object):
    def __init__(self, lat, lon, alt_rel):
        assert lat is not None
        assert lon is not None
        assert alt_rel is not None
        self.lat = lat
        self.lon = lon
        self.alt_rel = alt_rel

    def __str__(self):
        return "Waypoint at ({0}, {1}), alt {2}m (AMSL)".format(self.lat, self.lon, self.alt_rel)
