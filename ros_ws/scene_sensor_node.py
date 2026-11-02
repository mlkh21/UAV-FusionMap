"""Gazebo scene sensor adapter and diagnostics; no training or research inputs."""
import argparse
import collections
import json
from pathlib import Path
import struct
import sys
import threading

import rospy
import yaml
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Image, PointCloud2
from uav_fusionmap_msgs.msg import AircraftState, InfraredFrame, RadarFrame, SensorBundle
from ufm_ros_contract import from_ros_state
from ufm_ros_contract.perf01a_codec import to_ros_bundle, to_ros_infrared, to_ros_radar
from ufm_sensors.scene_stream import SceneStream
from radar_raw_bridge import decode_radar_cloud


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--require-exact-pose', action='store_true')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    profile = yaml.safe_load(args.profile.read_text())
    stream = SceneStream(args.run_id, profile, require_exact_pose=args.require_exact_pose)
    rospy.init_node('scene_sensor_adapter')
    lock = threading.RLock()
    counts = collections.Counter()
    errors = collections.deque(maxlen=20)
    publisher = {name:rospy.Publisher('/uav/sensors/' + name, cls, queue_size=2) for name, cls in
        (('radar', RadarFrame), ('infrared', InfraredFrame), ('bundle', SensorBundle))}

    def header(stamp, prefix, frame, source='fixture'):
        return dict(schema_version='0.1', timestamp=stamp, clock_id='sim:' + args.run_id,
            run_id=args.run_id, sample_id=prefix + ':' + str(stamp), frame_id=frame,
            source_type=source, status='valid', reason='')

    def quality():
        return dict(confidence=None, uncertainty=dict(status='unavailable', kind='', value=None,
            unit='', source='Gazebo functional scene; no calibrated error model'))

    def publish_ready():
        for bundle in stream.ready():
            publisher['bundle'].publish(to_ros_bundle(bundle))
            counts['bundle'] += 1

    def guarded(callback):
        def receive(message):
            with lock:
                try:
                    callback(message)
                    publish_ready()
                except (ValueError, KeyError, TypeError, struct.error) as exc:
                    errors.append(type(exc).__name__ + ': ' + str(exc))
                    counts['rejected'] += 1
        return receive

    def clock(message):stream.set_clock(message.clock.to_nsec())

    def state(message):
        stream.add('state', from_ros_state(message))
        if stream.failed:
            rospy.set_param('~locked', True)
        counts['state'] += 1

    radar_profile = dict(mode='fixture_only', frame_id='radar', x_field='x', y_field='y', z_field='z',
        position_unit='m', doppler_field='doppler', doppler_unit='m/s', doppler_positive='away',
        doppler_reference='sensor_relative', power_field='power', power_quantity='uncalibrated_intensity',
        power_unit='arbitrary', scan_reference='midpoint')

    def radar(message):
        stamp = message.header.stamp.to_nsec()
        value = decode_radar_cloud(message, radar_profile, dict(run_id=args.run_id,
            clock_id='sim:' + args.run_id, sample_id='gazebo.radar:' + str(stamp),
            scan_start_ns=stamp, scan_end_ns=stamp))
        stream.add('radar', value)
        publisher['radar'].publish(to_ros_radar(value))
        counts['radar'] += 1

    def infrared(message):
        expected = profile['infrared']
        if (message.encoding != '32FC1' or message.header.frame_id != 'thermal_optical' or
                message.width != expected['width'] or message.height != expected['height'] or
                message.step != message.width * 4 or len(message.data) != message.step * message.height):
            raise ValueError('scene infrared layout/frame mismatch')
        stamp = message.header.stamp.to_nsec()
        values = list(struct.unpack(('>' if message.is_bigendian else '<') +
                                   str(message.width * message.height) + 'f', message.data))
        value = dict(header=header(stamp, 'gazebo.infrared', 'thermal_optical'),
            width=message.width, height=message.height, encoding='32FC1', value_unit='fixture_intensity',
            image=values, exposure_start=stamp, exposure_end=stamp,
            camera_info=dict(width=message.width, height=message.height, calibration_id=profile['calibration_id']),
            quality=quality())
        stream.add('infrared', value)
        publisher['infrared'].publish(to_ros_infrared(value))
        counts['infrared'] += 1

    subscriptions = [rospy.Subscriber(topic, cls, guarded(callback), queue_size=5) for topic, cls, callback in
        (('/clock', Clock, clock), ('/uav/sensors/state', AircraftState, state),
         ('/uav/sensors/radar/raw', PointCloud2, radar), ('/uav/sensors/infrared/raw', Image, infrared))]
    rospy.set_param('~ready', args.run_id)

    def save():
        args.audit.write_text(json.dumps(dict(python=sys.executable, counts=dict(counts),
            pairing_rejections=dict(stream.rejected), clock_reset=stream.failed,
            exact_pose_required=args.require_exact_pose, errors=list(errors)), indent=2))
    rospy.on_shutdown(save)
    rospy.spin()


if __name__ == '__main__':
    main()
