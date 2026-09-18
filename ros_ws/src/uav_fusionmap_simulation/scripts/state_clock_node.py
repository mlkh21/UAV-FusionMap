#!/usr/bin/env python
"""只包装simulation源入口；采样时钟来自有效IMU，超时使用单调墙钟。"""
import threading
import time
import sys

import rospy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from mavros.mavlink import convert_to_bytes
from mavros_msgs.msg import Mavlink
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState
from ufm_ros_contract import to_ros_state
from ufm_ros_contract.audit import PublicationAudit
from ufm_simulation.mavlink_source import decode_source_packet
from ufm_simulation.source_timeline import SourceTimeline


def main():
    rospy.init_node('state_clock')
    run_id = rospy.get_param('~run_id')
    warmup = rospy.get_param('~warmup_stable_sim_ns')
    if isinstance(warmup, str) and warmup.isdecimal():
        warmup = int(warmup)
    if type(warmup) is not int:
        raise ValueError('warmup_stable_sim_ns必须为整数纳秒或十进制字符串')
    timeline = SourceTimeline(run_id, warmup_stable_sim_ns=warmup,
                              **{key: rospy.get_param('~' + key) for key in (
        'startup_timeout_wall_s', 'pending_limit',
        'pending_timeout_wall_s', 'source_timeout_wall_s')})
    sysid, compid = rospy.get_param('~sysid'), rospy.get_param('~compid')
    tolerance = rospy.get_param('~quaternion_norm_tolerance')
    clock_pub = rospy.Publisher('/clock', Clock, queue_size=100)
    state_pub = rospy.Publisher('/uav/sim/state', AircraftState, queue_size=100)
    diag_pub = rospy.Publisher('/uav/diagnostics', DiagnosticArray, queue_size=20)
    lock = threading.RLock()
    audit = PublicationAudit(rospy.get_param('~audit_path', ''))
    closing = False

    def record(topic, msg):
        try:
            audit.record(topic, msg)
        except Exception:
            rospy.signal_shutdown('publication audit failed')
            raise

    def diagnostic(reason, level=DiagnosticStatus.WARN):
        item = DiagnosticStatus(level=level, name='simulation/state_clock',
                                hardware_id=run_id, message=reason)
        item.values = [KeyValue(key='phase', value=timeline.phase),
                       KeyValue(key='python', value=sys.executable)]
        item.values += [KeyValue(key=k, value=str(v)) for k, v in sorted(timeline.counters.items())]
        diag_pub.publish(DiagnosticArray(status=[item]))

    def publish(events):
        for event in events:
            if event['type'] == 'clock':
                ns = event['timestamp']
                msg = Clock(clock=rospy.Time(ns // 1000000000, ns % 1000000000))
                clock_pub.publish(msg)
                record('/clock', msg)
            elif event['type'] == 'state':
                msg = to_ros_state(event['state'])
                state_pub.publish(msg)
                record('/uav/sim/state', msg)
            else:
                diagnostic(event['reason'], DiagnosticStatus.ERROR if timeline.phase == 'FAULT' else DiagnosticStatus.WARN)

    def receive(msg):
        with lock:
            if closing:
                return
            try:
                sample = decode_source_packet(convert_to_bytes(msg), msg.framing_status,
                                              sysid, compid, tolerance)
                if sample is not None:
                    publish(timeline.consume(sample, time.monotonic()))
            except ValueError as exc:
                diagnostic(str(exc))

    subscriber = rospy.Subscriber(rospy.get_param('~input_topic', '/mavlink/from'),
                                  Mavlink, receive, queue_size=1000)

    def shutdown():
        nonlocal closing
        with lock:
            closing = True
            subscriber.unregister()
            audit.close(phase=timeline.phase, counters=dict(timeline.counters))

    rospy.on_shutdown(shutdown)
    last_diagnostic = 0.
    while not rospy.is_shutdown():
        with lock:
            if closing:
                break
            if clock_pub.get_num_connections() >= 2 and state_pub.get_num_connections() >= 2:
                audit.ready()
            now = time.monotonic()
            publish(timeline.poll_timeout(now))
            if now - last_diagnostic >= 1:
                diagnostic('timeline:' + timeline.phase,
                           DiagnosticStatus.ERROR if timeline.phase == 'FAULT' else
                           DiagnosticStatus.OK if timeline.phase == 'ACTIVE' else DiagnosticStatus.WARN)
                last_diagnostic = now
        time.sleep(.02)
    subscriber.unregister()


if __name__ == '__main__':
    main()
