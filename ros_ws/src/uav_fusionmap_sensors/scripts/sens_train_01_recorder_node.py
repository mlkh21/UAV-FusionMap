#!/usr/bin/env python
"""Dedicated training JSONL recorder; exclusive create, never overwrites runs."""
import json
import sys
from pathlib import Path
import rospy
import yaml
from std_msgs.msg import String
from ufm_sensors.training_supervision import validate_training_sample


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('sens_train_01_recorder')
    run_id = rospy.get_param('~run_id')
    with Path(rospy.get_param('~config_path')).open(encoding='utf-8') as handle:
        config = yaml.safe_load(handle)
    output = rospy.get_param('~output_path')
    received = set()
    with open(output, 'x', encoding='utf-8') as stream:
        def receive(message):
            try:
                sample = json.loads(message.data)
                validate_training_sample(sample, config)
                stamp = sample['lidar']['header']['timestamp']
                if sample['run_id'] != run_id or stamp in received:
                    raise ValueError('training record duplicate/run mismatch')
                stream.write(message.data+'\n')
                stream.flush()
                received.add(stamp)
                rospy.set_param('~received', len(received))
            except (ValueError, KeyError, TypeError) as error:
                rospy.logerr('training recorder rejected record: %s', error)
                rospy.signal_shutdown('training recorder rejected record')
        subscription = rospy.Subscriber('/uav/training/lidar_supervision', String, receive, queue_size=20)
        rospy.set_param('~ready', run_id)
        rospy.spin()


if __name__ == '__main__':
    main()
