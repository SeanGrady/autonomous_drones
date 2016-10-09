import requests
import json
import time

url = 'http://localhost:5000/launch'
#url = 'http://192.168.1.37:5000/launch'
start_time = json.dumps({'start_time':time.time()})
r = requests.post(url, start_time)
print r
