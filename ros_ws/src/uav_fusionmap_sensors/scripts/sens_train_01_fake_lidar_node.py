#!/usr/bin/env python
"""Training-only Radar/IR fixture and separate fake-LiDAR supervision."""
import json
import sys
import threading
import time
from pathlib import Path
import rospy
import yaml
from rosgraph_msgs.msg import Clock
from std_msgs.msg import String
from uav_fusionmap_msgs.msg import AircraftState, InfraredFrame, RadarFrame
from ufm_ros_contract import from_ros_state
from ufm_ros_contract.perf01a_codec import to_ros_radar, to_ros_infrared
from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.training_stream import TrainingScanBuffer


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('sens_train_01_fake_lidar')
    run_id = rospy.get_param('~run_id')
    with Path(rospy.get_param('~config_path')).open(encoding='utf-8') as handle:
        config = yaml.safe_load(handle)
    count = int(rospy.get_param('~count', 20))
    if not 1 <= count <= 40:
        raise ValueError('bounded training fixture count required')
    buffer = TrainingScanBuffer(run_id, config, range(100_000_000, (count + 1) * 100_000_000,
                                                     100_000_000))
    radar_pub = rospy.Publisher('/uav/training/radar', RadarFrame, queue_size=20)
    ir_pub = rospy.Publisher('/uav/training/infrared', InfraredFrame, queue_size=20)
    supervision_pub = rospy.Publisher('/uav/training/lidar_supervision', String, queue_size=20)
    lock = threading.RLock()
    last_activity = [time.monotonic()]

    def publish(samples):
        for sample in samples:
            radar_pub.publish(to_ros_radar(sample['radar']))
            ir_pub.publish(to_ros_infrared(sample['infrared']))
            supervision_pub.publish(String(data=json.dumps(sample, allow_nan=False)))
        rospy.set_param('~published', buffer.published)
        rospy.set_param('~received_states', len(buffer.states))

    def reject(error):
        rospy.set_param('~rejected', str(error))
        rospy.logerr('training fixture rejected sample: %s', error)
        rospy.signal_shutdown('training fixture rejected sample')

    def receive_clock(message):
        try:
            with lock:
                publish(buffer.advance_clock(message.clock.to_nsec()))
                last_activity[0] = time.monotonic()
        except (ValueError, KeyError, TypeError) as error:
            reject(error)

    def receive_state(message):
        try:
            with lock:
                source = from_ros_state(message)
                state = adapt_state(source, {'odom_origin_policy':'px4_estimator_local_origin',
                                             'body_origin_policy':'source_body_virtual_flu'})
                publish(buffer.push_state(state))
                last_activity[0] = time.monotonic()
        except (ValueError, KeyError, TypeError) as error:
            reject(error)

    clock_sub = rospy.Subscriber('/clock', Clock, receive_clock, queue_size=20)
    state_sub = rospy.Subscriber('/uav/sim/state', AircraftState, receive_state, queue_size=20)
    deadline = time.monotonic()+15
    while not rospy.is_shutdown() and not supervision_pub.get_num_connections():
        if time.monotonic() >= deadline:
            raise RuntimeError('training recorder not connected')
        time.sleep(.02)
    if not rospy.is_shutdown():
        last_activity[0] = time.monotonic()
        rospy.set_param('~ready', run_id)
    while not rospy.is_shutdown():
        with lock:
            if buffer.published < count and time.monotonic() - last_activity[0] > 5:
                reject(ValueError('training state/clock input timeout with incomplete scan'))
        time.sleep(.02)


if __name__ == '__main__':
    main()
