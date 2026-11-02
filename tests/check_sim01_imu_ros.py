"""独立ROS IMU fixture观察器：真实MAVLink字节、采样时钟、值和默认关闭图。"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ['MAVLINK20'] = '1'

import rospy
from mavros.mavlink import convert_to_rosmsg
from mavros_msgs.msg import Mavlink
from pymavlink.dialects.v20 import common
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState, ImuSample
from ufm_ros_contract import from_ros_imu


def wait(check, timeout=8.):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if check():
            return True
        time.sleep(.02)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run')
    parser.add_argument('run_id')
    parser.add_argument('--enabled', action='store_true')
    args = parser.parse_args()
    rospy.init_node('imu_fixture_observer', disable_signals=True)
    sender = common.MAVLink(None, srcSystem=1, srcComponent=1)
    seen = {'source': [], 'adapted': [], 'clock': [], 'state': []}
    subscribers = [
        rospy.Subscriber('/uav/sim/imu', ImuSample,
                         lambda msg: seen['source'].append(from_ros_imu(msg)), queue_size=100),
        rospy.Subscriber('/uav/sensors/imu', ImuSample,
                         lambda msg: seen['adapted'].append(from_ros_imu(msg)), queue_size=100),
        rospy.Subscriber('/clock', Clock, lambda msg: seen['clock'].append(msg.clock.to_nsec()), queue_size=100),
        rospy.Subscriber('/uav/sensors/state', AircraftState,
                         lambda msg: seen['state'].append(msg.header.sample_id), queue_size=100),
    ]
    pub = rospy.Publisher('/uav/imu_fixture/mavlink', Mavlink, queue_size=100)
    errors = []
    try:
        if not wait(lambda: pub.get_num_connections() == 1):
            raise RuntimeError('source_not_connected')
        if args.enabled and not wait(lambda: all(s.get_num_connections() == 1 for s in subscribers[:2])):
            raise RuntimeError('imu_subscriptions_not_connected')
        for index in range(1, 23):
            us = index * 1_000_000
            imu = common.MAVLink_highres_imu_message(
                us, 1., 2., -9.8, .1, -.2, .3, *([0.] * 7), 63)
            odo = common.MAVLink_odometry_message(
                us, 1, 12, 1., 2., 3., [1., 0., 0., 0.], 4., 5., 6.,
                0., 0., 0., [1.] * 21, [1.] * 21, 3, 8, 0)
            imu.pack(sender)
            odo.pack(sender)
            pub.publish(convert_to_rosmsg(imu, stamp=rospy.Time(0)))
            pub.publish(convert_to_rosmsg(odo, stamp=rospy.Time(0)))
            time.sleep(.045)
        if not wait(lambda: len(seen['clock']) >= 15 and bool(seen['state'])):
            raise RuntimeError('clock_or_state_missing')
        if args.enabled:
            if not wait(lambda: len(seen['source']) >= 15 and len(seen['adapted']) >= 15):
                raise RuntimeError('imu_messages_missing')
            sources = {row['header']['timestamp']: row for row in seen['source']}
            if len(sources) != len(seen['source']):
                raise RuntimeError('duplicate_source_imu')
            for adapted in seen['adapted']:
                raw = sources.get(adapted['header']['timestamp'])
                if raw is None:
                    raise RuntimeError('adapted_imu_without_source')
                h, ah = raw['header'], adapted['header']
                if (h['timestamp'] != ah['timestamp'] or h['timestamp'] not in seen['clock'] or
                        h['sample_id'] != ah['sample_id'][len('sensors.imu:'):] or
                        h['run_id'] != args.run_id or ah['run_id'] != args.run_id or
                        h['frame_id'] != 'body_frd' or ah['frame_id'] != 'imu' or
                        raw['acceleration_type'] != 'specific_force' or
                        adapted['acceleration_type'] != 'specific_force' or
                        adapted['calibration_id'] != 'sim_pilot_virtual_flu_v1' or
                        raw['acceleration_covariance'] is not None or
                        adapted['acceleration_covariance'] is not None):
                    raise RuntimeError('imu_contract_mismatch')
                for lhs, rhs in zip(adapted['linear_acceleration'],
                                    [raw['linear_acceleration'][0], -raw['linear_acceleration'][1],
                                     -raw['linear_acceleration'][2]]):
                    if abs(lhs - rhs) > 1e-6:
                        raise RuntimeError('imu_axis_or_value_mismatch')
                for lhs, rhs in zip(adapted['angular_velocity'],
                                    [raw['angular_velocity'][0], -raw['angular_velocity'][1],
                                     -raw['angular_velocity'][2]]):
                    if abs(lhs - rhs) > 1e-6:
                        raise RuntimeError('imu_gyro_axis_or_value_mismatch')
                if (abs(raw['linear_acceleration'][0] - 1.) > 1e-6 or
                        abs(raw['linear_acceleration'][1] - 2.) > 1e-6 or
                        abs(raw['linear_acceleration'][2] + 9.8) > 1e-5 or
                        raw['angular_velocity_covariance'] is not None or
                        adapted['angular_velocity_covariance'] is not None):
                    raise RuntimeError('imu_source_value_or_quality_mismatch')
        elif (seen['source'] or seen['adapted'] or any(
                name in ('/uav/sim/imu', '/uav/sensors/imu') for name, _ in rospy.get_published_topics())):
            raise RuntimeError('disabled_imu_published_or_advertised')
        time.sleep(.1)
        before = len(seen['clock'])
        before_source, before_adapted = len(seen['source']), len(seen['adapted'])
        regression = common.MAVLink_highres_imu_message(
            500_000, 1., 2., -9.8, .1, -.2, .3, *([0.] * 7), 63)
        regression.pack(sender)
        pub.publish(convert_to_rosmsg(regression, stamp=rospy.Time(0)))
        if args.enabled:
            if not wait(lambda: len(seen['source']) == before_source + 1 and
                        len(seen['adapted']) == before_adapted + 1):
                raise RuntimeError('imu_terminal_missing')
            if (seen['source'][-1]['header']['status'] != 'unavailable' or
                    seen['adapted'][-1]['header']['status'] != 'unavailable' or
                    not seen['adapted'][-1]['header']['reason'].startswith('terminal:')):
                raise RuntimeError('imu_terminal_not_fail_closed')
        time.sleep(.1)
        if len(seen['clock']) != before:
            raise RuntimeError('clock_advanced_after_regression')
        if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
            raise RuntimeError('wrong_python')
    except (Exception, KeyboardInterrupt) as exc:
        errors.append(str(exc))
    finally:
        for sub in subscribers:
            sub.unregister()
        result = dict(passed=not errors, errors=errors, enabled=args.enabled,
                      counts={name: len(values) for name, values in seen.items()}, python=sys.executable)
        (Path(args.run) / 'imu-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        rospy.signal_shutdown('imu fixture complete')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
