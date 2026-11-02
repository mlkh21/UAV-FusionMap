"""Test-only unexpected clock publisher for graph/source rejection acceptance."""
import time
import rospy
from rosgraph_msgs.msg import Clock

rospy.init_node('m5_clock_intruder')
publisher = rospy.Publisher('/clock', Clock, queue_size=1)
while not rospy.is_shutdown():
    publisher.publish(Clock(clock=rospy.Time(0, 1)))
    time.sleep(.05)
