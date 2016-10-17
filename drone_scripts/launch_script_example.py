from code import interact
import requests
import json
import time

#url = 'http://localhost:5000/'
_url = 'http://192.168.42.1:5000/'

def launch_drone():
    path = 'launch'
    start_time = json.dumps({'start_time':time.time()})
    r = requests.post(_url+path, start_time)
    print r

def send_mission(mission_json, url):
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

def run_test(ip):
    url = 'http://' + ip + ':5000/'
    mission = create_goto_mission([10,10,10], 'test')
    mission2 = create_goto_mission([-10,-10,10], 'test2')
    send_mission(mission, url)
    send_mission(mission2, url)

if __name__ == '__main__':
    launch_drone()
    interact(local=locals())
