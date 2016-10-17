from code import interact
import requests
import json
import time


class DroneCoordinator(object):
    def __init__(self, primary_drone_ip, secondary_drone_ip):
        self.primary_drone_ip = primary_drone_ip
        self.secondary_drone_ip = secondary_drone_ip

    def launch_drone(self, drone_ip):
        path = 'launch'
        url = 'http://' + drone_ip + ':5000/'
        start_time = json.dumps({'start_time':time.time()})
        r = requests.post(_url+path, start_time)
        print r
