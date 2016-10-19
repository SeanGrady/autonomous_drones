from code import interact
import requests
import json
import time

def launch_drone(url):
    path = 'launch'
    start_time = json.dumps({'start_time':time.time()})
    r = requests.post(url+path, start_time)
    return r

def send_mission(mission_json, url):
    path = 'mission'
    mission_string = json.dumps(mission_json)
    r = requests.post(url+path, mission_string)
    return r

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
    launch_drone(url)
    mission = create_goto_mission([10,10,10], 'test')
    mission2 = create_goto_mission([-10,-10,10], 'test2')
    send_mission(mission, url)
    send_mission(mission2, url)
    return

def run_test_2(ip):
    url = 'http://' + ip + ':5000/'
    launch_drone(url)
    mission3 = create_goto_mission([10,-10,5], 'test')
    mission4 = create_goto_mission([-10,10,5], 'test2')
    send_mission(mission3, url)
    send_mission(mission4, url)
    return

if __name__ == '__main__':
    interact(local=locals())
