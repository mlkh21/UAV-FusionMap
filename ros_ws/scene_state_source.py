"""Simulation wrapper: Gazebo ENU/FLU truth to the existing AircraftState contract."""
import argparse
import sys

import rospy
from nav_msgs.msg import Odometry
from uav_fusionmap_msgs.msg import AircraftState
from ufm_ros_contract import to_ros_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('scene_state_source')
    publisher = rospy.Publisher('/uav/sim/state', AircraftState, queue_size=20)

    def receive(message):
        if message.header.frame_id != 'scene_world' or message.child_frame_id != 'base_link':
            rospy.logerr_throttle(1., 'scene source frame mismatch')
            return
        stamp = message.header.stamp.to_nsec()
        position, orientation, velocity = message.pose.pose.position, message.pose.pose.orientation, message.twist.twist.linear
        value = dict(header=dict(schema_version='0.1', timestamp=stamp, clock_id='sim:' + args.run_id,
            run_id=args.run_id, sample_id='gazebo.state:' + str(stamp), frame_id='scene_world',
            source_type='simulation', status='valid', reason=''),
            position=[position.x,position.y,position.z], orientation_xyzw=[orientation.x,orientation.y,orientation.z,orientation.w],
            linear_velocity=[velocity.x,velocity.y,velocity.z], body_frame_id='base_link', velocity_frame_id='base_link',
            state_source='ground_truth', quality=dict(confidence=None, uncertainty=dict(status='unavailable',
                kind='', value=None, unit='', source='Gazebo functional scene; not measured covariance')))
        publisher.publish(to_ros_state(value))

    subscriber = rospy.Subscriber('/uav/scene/body_odometry', Odometry, receive, queue_size=20)
    rospy.spin()


if __name__ == '__main__':
    main()
