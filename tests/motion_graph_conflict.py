"""Negative graph fixture: advertise a second clock, never publish a fake time."""
import time
import rospy
from rosgraph_msgs.msg import Clock

rospy.init_node('motion_conflicting_clock')
publisher=rospy.Publisher('/clock',Clock,queue_size=1)
while not rospy.is_shutdown():time.sleep(.05)
