"""
This'll load the json data from the file into a list. I know it's simple but I hate looking
up file IO everytime I have to do something like this in a new language, so
while I'm here anyway I've done it so you don't have to.
"""

import json


with open('oct_09_air_data.json', 'r') as data_file:
    data = json.load(data_file)
    adjusted_data = [read - 500 for read in data]
    print "Here's the data with 500 off each reading"
    print adjusted_data
