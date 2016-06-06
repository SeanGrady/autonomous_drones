import nose.tools
from nose.tools import \
    assert_equals, \
    assert_is_not_none, \
    assert_is_none, \
    assert_true
import drone_control
import dronekit
import dronekit_sitl
from dronekit import LocationGlobal
import time
import nav_utils

def test_airsample_sync():
    sender = drone_control.SampleDB()
    receiver = drone_control.SampleDB()
    sender.sync_to("127.0.0.1", 6001)
    receiver.sync_from(6001)
    assert_is_none(sender._recv_thread)
    assert_is_none(receiver._send_thread)

    air_sample = drone_control.LocationSample(dronekit.LocationGlobal(39.039955, 125.755627, 10), 1.0)
    sender.record(air_sample)
    time.sleep(0.5)     # Allow receiver some time to think
    assert_is_not_none(receiver.max_sample())
    assert_equals(air_sample, receiver.max_sample())
    print receiver._data_points

    print "\n\n2nd receiver instance"
    assert_true(receiver.close(), "Receiver didn't close right")
    receiver = drone_control.SampleDB()
    receiver.sync_from(6001)
    sender.sync_to("127.0.0.1", 6001)


    air_sample2 = drone_control.LocationSample(dronekit.LocationGlobal(39.039955, 125.755627, 10), 1.0)
    air_sample2.timestamp = air_sample.timestamp
    assert_equals(air_sample, air_sample2)
    print "sending 2nd sample"
    sender.record(air_sample2)  # this will do nothing, we've already recorded it
    assert_equals(len(sender), 1)
    air_sample3 = drone_control.LocationSample(dronekit.LocationGlobal(39.039957, 125.755620, 10), 1.1)
    sender.record(air_sample3)
    assert_equals(len(sender), 2)
    time.sleep(0.5)     # Let the receiver get it
    assert_equals(air_sample3, receiver.max_sample())

    assert_true(sender.close(), "Sender didn't close gracefully")
    assert_true(receiver.close(), "Receiver didn't close gracefully")

def test_can_plot():
    db = drone_control.SampleDB()
    db.load("../data/sensor_data.json")
    db.plot(time=2.0)

def test_distance_sanity():
    l1 = LocationGlobal(32.990704, -117.128622, 234)
    l2 = LocationGlobal(32.990833, -117.127986, 234)
    nose.tools.assert_almost_equal(nav_utils.get_distance(l1, l2), 61.1, 1)

def test_explore_waypoints():
    drone = drone_control.AutoPilot(simulated=True, sim_speedup=2)
    drone.bringup_drone()
    drone.arm_and_takeoff(20)
    drone.load_waypoints("test_waypoints.json")
    expected = [
        LocationGlobal(32.991124, -117.128359, 258),
        LocationGlobal(32.990756, -117.127933, 258),
        LocationGlobal(32.990399, -117.128357, 258),
        LocationGlobal(32.990761, -117.128784, 258)
    ]
    i=0
    while drone.goto_next_waypoint(ground_tol=2.0, alt_tol=2.0):
        # print "Location is {0}".format(drone.get_global_location())
        # Verify we are at the right place
        distance = nav_utils.get_distance(drone.get_global_location(), expected[i])
        nose.tools.assert_less(distance, 2.9, "Drone did not arrive at waypoint"
                                              " accurately enough, offset={0}".format(distance))
        i += 1

# def test_master():
#     sitl = dronekit_sitl.SITL()
#     sitl.download('copter', '3.3', verbose=True)
#     sitl_args = ['--model', 'quad',
#                  '--home=32.990756,-117.128362,243,0']
#     sitl.launch(sitl_args,
#                  verbose=True,
#                  await_ready=True,
#                  restart=True)
#
#     connection_string = "tcp:127.0.0.1:{0}".format(5760)
#     vehicle = dronekit.connect(connection_string, wait_ready=True, heartbeat_timeout=30)
#     assert_true(vehicle is not None)

if __name__ == "__main__":
    # test_distance_sanity()
    test_explore_waypoints()
    # test_master()
    # test_wtf()
    # test_can_plot()

