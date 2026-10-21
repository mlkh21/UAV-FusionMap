#!/usr/bin/env python
"""Short isolated simulation state and clock source for training fixtures."""
import sys
import time
from pathlib import Path
import rospy
import yaml
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState
from ufm_ros_contract import to_ros_state
from ufm_simulation.perf01a_fixture import make_training_fixture_state


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('sens_train_01_source')
    run_id = rospy.get_param('~run_id')
    count = int(rospy.get_param('~count', 20))
    if not run_id or count < 1 or count > 40:
        raise ValueError('fixture run_id/count invalid')
    with Path(rospy.get_param('~config_path')).open(encoding='utf-8') as handle:
        config = yaml.safe_load(handle)
    duration = int(config['lidar']['scan_duration_ns'])
    if duration not in (0, 200_000_000):
        raise ValueError('ROS fixture supports zero or 200 ms scans only')
    half = duration // 2
    stamps = range(100_000_000 - half, count * 100_000_000 + half + 1, 100_000_000)
    state_pub = rospy.Publisher('/uav/sim/state', AircraftState, queue_size=20)
    clock_pub = rospy.Publisher('/clock', Clock, queue_size=20)
    deadline = time.monotonic() + 15
    while not rospy.is_shutdown():
        if (state_pub.get_num_connections() and clock_pub.get_num_connections()
                and rospy.get_param('/sens_train_01_recorder/ready', '') == run_id
                and rospy.get_param('/sens_train_01_fake_lidar/ready', '') == run_id):
            break
        if time.monotonic() > deadline:
            raise RuntimeError('training subscribers not ready')
        time.sleep(.02)
    for index, stamp in enumerate(stamps):
        if rospy.is_shutdown():
            break
        clock_pub.publish(Clock(clock=rospy.Time(stamp // 1_000_000_000, stamp % 1_000_000_000)))
        state_pub.publish(to_ros_state(make_training_fixture_state(run_id, index, stamp, config)))
        rospy.set_param('~published_states', index + 1)
        rospy.set_param('~published_clocks', index + 1)
        time.sleep(.1)
    rospy.set_param('~done', run_id)
    rospy.spin()


if __name__ == '__main__':
    main()
