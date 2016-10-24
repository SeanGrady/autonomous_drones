"""
Module name: MissionGenerator.py
Author: Michael Ostertag
Python Version: 2.7

missionGenerator creates a series of points (North, East, Altitude) in
meters from a user provider dictionary. The output is a JSON string that can be
used in XX for generating flight patterns.
"""

import json
import numpy as np
import math

class MissionGenerator:
    def __init__(self): # Nothing to initialize right now...
        return
        
    ## Generate mission plan from incoming dictionary
    def createMission(self, dict_In):
        # Define helper functions
        def generateBoxPoints(dict_In):
            N_max = dict_In['height']
            W_max = -dict_In['width']
            altitude = dict_In['altitude']
            rotation = math.radians(dict_In['rotation'])
            stepSize = 1;
            
            # Establish corners of box
            c1 = np.array([    0,     0, altitude]) # SE
            c2 = np.array([    0, W_max, altitude]) # SW
            c3 = np.array([N_max, W_max, altitude]) # NW
            c4 = np.array([N_max,     0, altitude]) # NE
        
            path = np.vstack((c1, c2))
            
            # If filled, set 1 m step, starting at home position 
            if (dict_In['filled']):
                if (N_max > 0):
                    N_steps = range(2, N_max, 2)
                else:
                    N_steps = range(N_max, -2, 2)           
                N_inc = math.copysign(stepSize, N_max)
            
                for N_i in N_steps:
                    if (N_i == N_max):
                        path = np.vstack((path, c3, c4))
                        break
                    
                    path = np.vstack((path, np.array([N_i - N_inc, W_max, altitude]), 
                        np.array([N_i - N_inc,     0, altitude]), 
                        np.array([    N_i,     0, altitude]), 
                        np.array([    N_i, W_max, altitude])))
        
            else:
                 path = np.vstack((path, c3, c4))
                 
            # Rotate using rotation matrix
            matrix_Rotation = np.matrix([[ math.cos(-rotation), -math.sin(-rotation), 0], 
                                          [math.sin(-rotation),  math.cos(-rotation), 0], 
                                           [                0,                   0, 1]])
            path = path * matrix_Rotation.T
                 
            # Add offset to generated path
            path += np.array(np.append(dict_In['loc_start'], 0))
            
            return (path.tolist())
            
        def generateCirclePoints(dict_In):
            R = dict_In['radius']
            altitude = dict_In['altitude']
            stepSize_m = 2

            num_Points = math.floor(2*R*math.pi / stepSize_m)
            
            stepSize_rad = 2*math.pi / num_Points
            
            path = [0, R, altitude]         
            
            for angle_rad in np.linspace(stepSize_rad, 2*math.pi, num_Points):
                path = np.vstack((path, 
                    [R*math.sin(angle_rad), R*math.cos(angle_rad), altitude]))
            
            # TODO If filled, spiral out
             
            # Add offset to generated path
            path += np.array(np.append(dict_In['loc_start'], 0))
            
            return (path.tolist())
        
        def createPlanElement(action, points, repeat):
            temp = {
                'action' : action,
                'points' : points,
                'repeat' : repeat,
            }

            return temp
            
        # Set to defaults if required
        if not('shape' in dict_In):
            # WARNING
            dict_In['shape'] = 'box'
        if not('loc_start' in dict_In):
            # WARNING
            dict_In['loc_start'] = np.array([0, 0])
        if not('filled' in dict_In):
            # WARNING
            dict_In['filled'] = True
        if not('altitude' in dict_In):
            # WARNING
            dict_In['altitude'] = 5
        if not('repetition' in dict_In):
            # WARNING
            dict_In['repetition'] = 1
        
        # Generate list of points based on shape. If params are missing, fill with 
        # defaults      
        if (dict_In['shape'] == 'box'):
            if not('height' in dict_In):
                # WARNING
                dict_In['height'] = 10
            if not('width' in dict_In):
                # WARNING
                dict_In['width'] = 10
            if not('rotation' in dict_In):
                # WARNING
                dict_In['rotation'] = 0
        
            points = generateBoxPoints(dict_In);        
            
        elif (dict_In['shape'] == 'circle'):
            if not('radius' in dict_In):
                # WARNING
                dict_In['radius'] = 3
                
            points = generateCirclePoints(dict_In);
            
        else :
            # ERROR. Shape is not supported in this version.
            print 'ERROR'
        
        # Generate JSON string using points
        mission = {}
        mission['points'] = {}
        mission['points']['home'] = {
            'N' : 0,
            'E' : 0,
            'D' : 5,
        }

        mission['plan'] = [createPlanElement('go', ['home'], 0)]

        # if points were successfully generated, then load into a patrol mission
        if (points):
            mission['plan'].append(createPlanElement('go', ['p0'], 0))
            list_Points = []
            for ind, point in enumerate(points):
                mission['points']['p'+str(ind)] = {
                    'N' : point[0], 
                    'E' : point[1], 
                    'D' : point[2],
                }
                list_Points.append('p'+str(ind))

            mission['plan'].append(createPlanElement('patrol', list_Points, 
                dict_In['repetition']))

            mission['plan'].append(createPlanElement('go', ['home'], 0))
            
        mission['plan'].append(createPlanElement('land', ['home'], 0))
    
        return json.dumps(mission, sort_keys=True, indent=2) # json.dumps(mission) # uncomment for utilitarian print out

    def create_config_dict(self,
            shape, height, width, rotation, radius, altitude, filled, 
            loc_start):
        dict_Config = {
            'shape': shape,
            'height': height,
            'width': width,
            'rotation': rotation,
            'radius': radius,
            'altitude': altitude,
            'filled': filled,
            'loc_start': loc_start,
        }
        return dict_Config


if __name__ == '__main__':
    # Test script for function
    '''
    dict_Config = {}
    dict_Config['shape'] = 'box' # 'circle'
    dict_Config['height'] = 8      # North in meters (only for box)
    dict_Config['width'] = 10      # West in meters (only for box)
    dict_Config['rotation'] = 45   # Rotation in degrees around SW corner
    dict_Config['radius'] = 10     # Radius in meters (only for circle)
    dict_Config['altitude'] = 5    # Altitude in meters
    dict_Config['filled'] = True   # T/F for whether area is criss-crossed
    dict_Config['loc_start'] = np.array([10, 10]) # Start location that offsets all
                                    # points, including home
    '''
    theGenerator = MissionGenerator()
    config = theGenerator.create_config_dict(
        'circle', 8, 8, 0, 5, 3, True, np.array([0,0]),
    )
    with open('auto_gen_mission.json', 'w') as infile:
        infile.write(theGenerator.createMission(config))

