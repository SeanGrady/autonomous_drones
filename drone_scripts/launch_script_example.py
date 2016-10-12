from code import interact
import requests
import json
import time

url = 'http://localhost:5000/'
#url = 'http://192.168.1.37:5000/'

def launch_drone():
    path = 'launch'
    start_time = json.dumps({'start_time':time.time()})
    r = requests.post(url+path, start_time)
    print r

def send_mission(mission_json):
    path = 'mission'
    mission_string = json.dumps(mission_json)
    r = requests.post(url+path, mission_string)
    print r

def create_goto_mission(point, name):
    mission_dict = { 
        'points': {
            name: {
                'N': point[0],
                'E': point[1],
                'D': point[2],
            },
        },
        'plan': [
            {
                'action': 'go',
                'points': [name],
                'repeat': 0,
            },
        ],
    }
    return mission_dict

if __name__ == '__main__':
    launch_drone()
    mission = create_goto_mission([10,10,10], 'test')
    interact(local=locals())
