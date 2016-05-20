import nose.tools
from nose.tools import assert_equals, assert_is_not_none, assert_is_none
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
    time.sleep(1)
    assert_is_not_none(receiver.max_sample())
    assert_equals(air_sample, receiver.max_sample())
    sender.close()
    receiver.close()

if __name__ == "__main__":
    test_airsample_sync()


