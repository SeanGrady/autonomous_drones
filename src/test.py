import nose.tools
from nose.tools import \
    assert_equals, \
    assert_is_not_none, \
    assert_is_none, \
    assert_true
import point_follower
import dronekit
import time

def test_airsample_sync():
    sender = point_follower.AirSampleDB()
    receiver = point_follower.AirSampleDB()
    sender.sync_to("127.0.0.1", 6001)
    receiver.sync_from(6001)
    assert_is_none(sender._recv_thread)
    assert_is_none(receiver._send_thread)

    air_sample = point_follower.AirSample(dronekit.LocationGlobal(39.039955, 125.755627, 10), 1.0)
    sender.record(air_sample)
    time.sleep(0.5)     # Allow receiver some time to think
    assert_is_not_none(receiver.max_sample())
    assert_equals(air_sample, receiver.max_sample())
    print receiver._data_points

    print "\n\n2nd receiver instance"
    assert_true(receiver.close(), "Receiver didn't close right")
    receiver = point_follower.AirSampleDB()
    receiver.sync_from(6001)
    sender.sync_to("127.0.0.1", 6001)


    air_sample2 = point_follower.AirSample(dronekit.LocationGlobal(39.039955, 125.755627, 10), 1.0)
    air_sample2.timestamp = air_sample.timestamp
    assert_equals(air_sample, air_sample2)
    print "sending 2nd sample"
    sender.record(air_sample2)  # this will do nothing, we've already recorded it
    assert_equals(len(sender), 1)
    air_sample3 = point_follower.AirSample(dronekit.LocationGlobal(39.039957, 125.755620, 10), 1.1)
    sender.record(air_sample3)
    assert_equals(len(sender), 2)
    time.sleep(0.5)     # Let the receiver get it
    assert_equals(air_sample3, receiver.max_sample())

    assert_true(sender.close(), "Sender didn't close gracefully")
    assert_true(receiver.close(), "Receiver didn't close gracefully")

def test_can_plot():
    db = point_follower.AirSampleDB()
    db.load()
    db.plot(block=False)


if __name__ == "__main__":
    test_can_plot()


