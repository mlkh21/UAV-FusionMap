#!/usr/bin/env python
"""SIM-01C真实MAVLink故障输入驱动。

本工具只向场景私有ROS Master的输入话题发布fixture。``driver-result.json``中的
``passed``仅表示连接建立且注入计划完整，不表示source/sensors的故障契约通过；后者由
场景观察器根据terminal、诊断和valid输出独立判断。
"""
import argparse
import collections
import json
import os
import sys
import time
from pathlib import Path


# ODOMETRY的msgid为331，必须让mavros.mavlink按MAVLink2转换。本变量只作用于driver进程。
os.environ['MAVLINK20'] = '1'

EXPECTED_PYTHON = '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python'
SCENARIOS = tuple('C-F%d' % value for value in (0, 1, 2, 3, 4, 5, 7))


def normalize_scenario(value):
    candidate = value.strip().upper()
    if candidate.startswith('F'):
        candidate = 'C-' + candidate
    if candidate not in SCENARIOS:
        raise ValueError('unsupported_scenario:' + value)
    return candidate


def build_highres_imu(time_usec):
    """构造满足生产解码字段掩码的HIGHRES_IMU。"""
    from pymavlink.dialects.v20 import common

    return common.MAVLink_highres_imu_message(
        time_usec,
        0., 0., -9.80665,
        0., 0., 0.,
        0., 0., 0.,
        1013.25, 0., 0., 20.,
        63,
    )


def build_odometry(time_usec, reset_counter=3):
    """构造生产入口接受的NED/FRD、autopilot估计ODOMETRY。"""
    from pymavlink.dialects.v20 import common

    return common.MAVLink_odometry_message(
        time_usec,
        1, 12,
        1., 2., 3.,
        [1., 0., 0., 0.],
        4., 5., 6.,
        0., 0., 0.,
        [1.] * 21,
        [1.] * 21,
        reset_counter,
        8,
        0,
    )


class MavlinkFaultDriver:
    """发布一个场景的真实MAVLink ROS fixture并保存单调发送台账。"""

    def __init__(self, run, run_id, scenario, input_topic='/mavlink/from',
                 connection_timeout_wall_s=10., ready_files=None):
        import rospy
        from mavros_msgs.msg import Mavlink
        from pymavlink.dialects.v20 import common

        self.run = Path(run)
        if not self.run.is_dir():
            raise ValueError('run_directory_required')
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError('run_id_required')
        if not isinstance(input_topic, str) or not input_topic.startswith('/'):
            raise ValueError('absolute_input_topic_required')
        if connection_timeout_wall_s <= 0:
            raise ValueError('positive_connection_timeout_required')
        self.run_id = run_id
        self.scenario = normalize_scenario(scenario)
        self.input_topic = input_topic
        self.connection_timeout_wall_s = float(connection_timeout_wall_s)
        self.ready_files = ([self.run / 'source-audit.jsonl.ready.json',
                             self.run / 'sensor-audit.jsonl.ready.json']
                            if ready_files is None else [Path(value) for value in ready_files])
        self.events_path = self.run / 'driver-events.jsonl'
        self.result_path = self.run / 'driver-result.json'
        self.events_file = self.events_path.open('x')
        self.publisher = rospy.Publisher(input_topic, Mavlink, queue_size=1000)
        self.sender = common.MAVLink(None, srcSystem=1, srcComponent=1)
        self.event_seq = 0
        self.last_event_monotonic_ns = None
        self.last_send_monotonic_ns = None
        self.sent_counts = collections.Counter()
        self.closed = False

    def record(self, action, **values):
        receipt_ns = time.monotonic_ns()
        if (self.last_event_monotonic_ns is not None and
                receipt_ns < self.last_event_monotonic_ns):
            raise RuntimeError('driver_monotonic_regression')
        self.event_seq += 1
        self.last_event_monotonic_ns = receipt_ns
        event = dict(
            event_seq=self.event_seq,
            run_id=self.run_id,
            scenario=self.scenario,
            action=action,
            receipt_monotonic_ns=receipt_ns,
        )
        event.update(values)
        self.events_file.write(json.dumps(event, sort_keys=True) + '\n')
        self.events_file.flush()
        return event

    def wait_for_connection(self):
        import rospy

        self.record('wait_for_source_subscriber', input_topic=self.input_topic)
        deadline = time.monotonic() + self.connection_timeout_wall_s
        while time.monotonic() < deadline:
            if rospy.is_shutdown():
                raise RuntimeError('ros_shutdown_before_driver_ready')
            connections = self.publisher.get_num_connections()
            if connections >= 1:
                self.record('source_subscriber_ready', connections=connections)
                return
            time.sleep(.01)
        raise RuntimeError('source_subscriber_connection_timeout')

    def wait_for_audits(self):
        """等待生产节点真实连接门槛写出的PublicationAudit ready标记。"""
        import rospy

        self.record('wait_for_audit_ready',
                    ready_files=[str(path) for path in self.ready_files])
        deadline = time.monotonic() + self.connection_timeout_wall_s
        last_error = None
        while time.monotonic() < deadline:
            if rospy.is_shutdown():
                raise RuntimeError('ros_shutdown_before_audit_ready')
            ready = []
            for path in self.ready_files:
                try:
                    value = json.loads(path.read_text())
                    if value.get('ready') is not True:
                        raise ValueError('ready_not_true')
                    if value.get('python') != EXPECTED_PYTHON:
                        raise ValueError('unexpected_audit_python:' + str(value.get('python')))
                    ready.append(path)
                except FileNotFoundError:
                    pass
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    last_error = str(path) + ':' + str(exc)
            if len(ready) == len(self.ready_files):
                self.record('audit_ready', ready_files=[str(path) for path in ready])
                return
            time.sleep(.01)
        suffix = ':' + last_error if last_error else ''
        raise RuntimeError('publication_audit_ready_timeout' + suffix)

    def publish(self, message, action, reset_counter=None):
        """先用pymavlink编码，再转换成mavros_msgs/Mavlink并发布。"""
        import rospy
        from mavros.mavlink import convert_to_bytes, convert_to_rosmsg

        wire = bytes(message.pack(self.sender))
        ros_message = convert_to_rosmsg(message, stamp=rospy.Time(0))
        if bytes(convert_to_bytes(ros_message)) != wire:
            raise RuntimeError('mavlink_ros_roundtrip_mismatch')
        start_ns = time.monotonic_ns()
        self.publisher.publish(ros_message)
        end_ns = time.monotonic_ns()
        msgid = message.get_msgId()
        msg_type = 'HIGHRES_IMU' if msgid == 105 else 'ODOMETRY'
        fields = dict(
            publish_start_monotonic_ns=start_ns,
            publish_end_monotonic_ns=end_ns,
            msg_type=msg_type,
            msgid=msgid,
            time_usec=message.time_usec,
            wire_hex=wire.hex(),
        )
        if reset_counter is not None:
            fields['reset_counter'] = reset_counter
        self.record(action, **fields)
        self.last_send_monotonic_ns = end_ns
        self.sent_counts[msg_type] += 1

    def publish_imu(self, time_usec, action):
        self.publish(build_highres_imu(time_usec), action)

    def publish_odometry(self, time_usec, action, reset_counter=3):
        self.publish(build_odometry(time_usec, reset_counter), action,
                     reset_counter=reset_counter)

    def publish_pair(self, time_usec, action, reset_counter=3):
        self.publish_imu(time_usec, action + '_imu')
        self.publish_odometry(time_usec, action + '_odometry', reset_counter)

    def normal_warmup(self):
        # 源窗口按仿真时间判定；快速推进12个1秒样本，不伪装实时飞行频率。
        self.record('normal_warmup_start', samples=12, sim_step_usec=1_000_000)
        for index in range(12):
            self.publish_pair((index + 1) * 1_000_000, 'warmup', reset_counter=3)
            time.sleep(.02)
        self.record('normal_warmup_complete', last_time_usec=12_000_000)
        return 12_000_000

    def continue_one_stream(self, kind, last_time_usec, duration_wall_s=2.7,
                            period_wall_s=.05):
        self.record('single_stream_start', continued_stream=kind,
                    planned_duration_wall_s=duration_wall_s)
        deadline = time.monotonic() + duration_wall_s
        current = last_time_usec
        while time.monotonic() < deadline:
            current += 50_000
            if kind == 'imu':
                self.publish_imu(current, 'continue_imu')
            else:
                self.publish_odometry(current, 'continue_odometry')
            time.sleep(period_wall_s)
        self.record('single_stream_complete', continued_stream=kind,
                    last_time_usec=current)

    def run_scenario(self):
        self.wait_for_connection()
        self.wait_for_audits()
        if self.scenario == 'C-F0':
            self.record('no_input_complete', sent_messages=0)
            return

        last = self.normal_warmup()
        if self.scenario == 'C-F1':
            self.record('stall_imu', last_imu_time_usec=last)
            self.continue_one_stream('odometry', last)
        elif self.scenario == 'C-F2':
            self.record('stall_odometry', last_odometry_time_usec=last)
            self.continue_one_stream('imu', last)
        elif self.scenario == 'C-F3':
            self.record('pause_both_start', last_time_usec=last,
                        planned_duration_wall_s=2.3)
            time.sleep(2.3)
            self.record('pause_both_complete')
            for index in range(8):
                last += 50_000
                self.publish_pair(last, 'post_terminal_recovery')
                time.sleep(.02)
            self.record('post_terminal_recovery_complete', samples=8,
                        last_time_usec=last)
        elif self.scenario == 'C-F4':
            regressed = last - 1_000_000
            self.publish_imu(regressed, 'inject_imu_regression')
            self.record('imu_regression_complete', previous_time_usec=last,
                        injected_time_usec=regressed)
        elif self.scenario == 'C-F5':
            self.publish_odometry(last + 50_000, 'inject_estimator_reset',
                                  reset_counter=4)
            self.record('estimator_reset_complete', previous_reset_counter=3,
                        injected_reset_counter=4)
        elif self.scenario == 'C-F7':
            for index in range(8):
                last += 50_000
                self.publish_pair(last, 'fresh_run_normal')
                time.sleep(.02)
            self.record('fresh_run_normal_complete', samples=8,
                        last_time_usec=last)
        # 给最后一帧实际TCPROS传输机会；不使用可能被冻结的ROS仿真时间。
        time.sleep(.2)

    def close(self, errors):
        if self.closed:
            return
        self.closed = True
        try:
            self.publisher.unregister()
        finally:
            self.events_file.close()
        result = dict(
            passed=not errors,
            errors=list(errors),
            run_id=self.run_id,
            scenario=self.scenario,
            input_topic=self.input_topic,
            events=self.event_seq,
            sent_counts=dict(self.sent_counts),
            last_send_monotonic_ns=self.last_send_monotonic_ns,
            python=sys.executable,
            meaning='passed仅表示连接和注入计划完整，不表示SIM-01C场景验收通过',
        )
        with self.result_path.open('x') as stream:
            stream.write(json.dumps(result, indent=2, sort_keys=True) + '\n')
        print(json.dumps(result, sort_keys=True), flush=True)
        return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='SIM-01C真实MAVLink故障输入驱动')
    parser.add_argument('run', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('scenario', help='C-F0..C-F5或C-F7；也接受F0等简写')
    parser.add_argument('--input-topic', default='/mavlink/from')
    parser.add_argument('--connection-timeout-wall-s', type=float, default=10.)
    parser.add_argument('--ready-file', action='append', default=None,
                        help='可重复；默认等待run内source/sensor audit ready标记')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    errors = []
    driver = None
    try:
        if sys.executable != EXPECTED_PYTHON:
            raise RuntimeError('unexpected_python:' + sys.executable)
        import rospy

        rospy.init_node('sim01c_mavlink_fault_driver', disable_signals=True)
        driver = MavlinkFaultDriver(
            args.run,
            args.run_id,
            args.scenario,
            input_topic=args.input_topic,
            connection_timeout_wall_s=args.connection_timeout_wall_s,
            ready_files=args.ready_file,
        )
        driver.run_scenario()
    except (Exception, KeyboardInterrupt) as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    finally:
        result = driver.close(errors) if driver is not None else None
        try:
            import rospy
            rospy.signal_shutdown('SIM-01C fault driver complete')
        except Exception:
            pass
    return 0 if result is not None and result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
