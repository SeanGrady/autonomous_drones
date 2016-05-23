import dronekit
import point_follower
import time

SIMULATED=False

drone = None

try:
  if SIMULATED:
      drone = point_follower.AutoPilot(simulated=True)
      drone.bringup_drone()
  else:
      drone = point_follower.AutoPilot(simulated=False)
      drone.bringup_drone("udp:127.0.0.1:14550")
      # while True:
        # time.sleep(1)   # just let it get samples
      

  print "delaying"
  # time.sleep(30)
  print "GOGOGOG"
  drone.arm_and_takeoff(5)

  for i in xrange(10):
      drone.goto_relative(0,0,i*1 + 5)
      time.sleep(10)
except KeyboardInterrupt:
  drone.stop()

