"""Provide standalone flask server for testing purposes.

This can be run to provide an interface for testing things that should interact
with the drones. It's pretty simple and the methods are documented in
drone_control.py
"""
from flask import Flask, request
from pubsub import pub
import json

app = Flask(__name__)


class FlaskServer(object):
    def __init__(self):
        self.run()

    @app.route('/launch', methods=['POST'])
    def launch_func():
        print "entered flask launch function"
        time = json.loads(request.data)
        pub.sendMessage(
            'flask-messages.launch',
            arg1=time,
        )
        return 'received launch command'

    @app.route('/mission', methods=['POST'])
    def mission_func():
        print "entered flask mission function"
        #print request.data
        mission = json.loads(request.data)
        pub.sendMessage(
            'flask-messages.mission',
            arg1=mission,
        )
        return 'received mission'

    @app.route('/RTL_and_land', methods=['GET'])
    def RTL_and_land_func():
        print "entered flask RTL function"
        pub.sendMessage(
            'flask-messages.RTL',
            arg1=True,
        )
        return 'RTL and landing'

    @app.route('/land', methods=['GET'])
    def land_func():
        print "entered flask land function"
        pub.sendMessage(
            'flask-messages.land',
            arg1=True,
        )
        return 'landing'

    @app.route('/ack', methods=['GET'])
    def ack_func():
        print "entered flask ack function"
        return 'ack'

    def run(self):
        app.run('0.0.0.0')


if __name__ == '__main__':
    fs = FlaskServer()
