#!/usr/bin/env python
"""只包装sensors适配和有界接收门控；不读取原始雷达、不创建时钟或TF。"""
import sys
import threading
import time

import rospy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rosgraph_msgs.msg import Clock
import tf2_ros
from uav_fusionmap_msgs.msg import AircraftState, ImuSample
from ufm_ros_contract import from_ros_state, to_ros_state, from_ros_imu, to_ros_imu
from ufm_ros_contract.audit import PublicationAudit
from ufm_sensors.state_adapter import adapt_state, adapt_scene_ground_truth
from ufm_sensors.clock_gate import StateClockGate
from ufm_sensors.odom_mirror import build_odom_mirror
from ufm_sensors.imu_adapter import adapt_imu, ImuClockGate


def main():
    rospy.init_node('state_adapter')
    run_id = rospy.get_param('~run_id')
    input_mode = rospy.get_param('~state_input_mode', 'px4_estimated')
    if input_mode not in ('px4_estimated', 'scene_ground_truth'):
        raise ValueError('unsupported state_input_mode')
    scene_registration = rospy.get_param('~scene_registration', '')
    publish_imu = rospy.get_param('~publish_imu', False)
    if type(publish_imu) is not bool:
        raise ValueError('publish_imu must be bool')
    calibration_id = rospy.get_param('~imu_calibration_id', '') if publish_imu else ''
    if publish_imu and calibration_id != 'sim_pilot_virtual_flu_v1':
        raise ValueError('imu_virtual_calibration_required')
    frames = ({key: rospy.get_param('~' + key) for key in ('odom_origin_policy', 'body_origin_policy')}
              if input_mode == 'px4_estimated' else {})
    if input_mode == 'scene_ground_truth' and (publish_imu or scene_registration != 'gazebo_scene_world_enu_identity_v1'):
        raise ValueError('scene truth requires explicit registration and no PX4 IMU')
    tolerance = rospy.get_param('~quaternion_norm_tolerance')
    gate = StateClockGate(run_id, pending_limit=rospy.get_param('~pending_limit'),
                          pending_timeout_wall_s=rospy.get_param('~pending_timeout_wall_s'),
                          identity_history_limit=rospy.get_param('~identity_history_limit', 1000))
    state_pub = rospy.Publisher('/uav/sensors/state', AircraftState, queue_size=100)
    imu_pub = rospy.Publisher('/uav/sensors/imu', ImuSample, queue_size=100) if publish_imu else None
    imu_gate = ImuClockGate(run_id,
        pending_limit=rospy.get_param('~pending_limit'),
        timeout_wall_s=rospy.get_param('~pending_timeout_wall_s'),
        identity_history_limit=rospy.get_param('~identity_history_limit', 1000)) if publish_imu else None
    publish_odom = bool(rospy.get_param('~publish_odom', False))
    broadcast_tf = bool(rospy.get_param('~broadcast_tf', False))
    odom_pub = rospy.Publisher('/uav/localization/odom', Odometry, queue_size=100) if publish_odom else None
    tf_broadcaster = tf2_ros.TransformBroadcaster() if broadcast_tf else None
    diag_pub = rospy.Publisher('/uav/diagnostics', DiagnosticArray, queue_size=20)
    lock = threading.RLock()
    audit = PublicationAudit(rospy.get_param('~audit_path', ''))
    closing = False

    def diagnostic(reason, level=DiagnosticStatus.WARN):
        item = DiagnosticStatus(level=level, name='sensors/state_adapter',
                                hardware_id=run_id, message=reason)
        item.values = [KeyValue(key='python', value=sys.executable)]
        item.values += [KeyValue(key=k, value=str(v)) for k, v in sorted(gate.counters.items())]
        diag_pub.publish(DiagnosticArray(status=[item]))

    def publish(states):
        for state in states:
            msg = to_ros_state(state)
            state_pub.publish(msg)
            if ((publish_odom or broadcast_tf)
                    and state['header']['status'] != 'unavailable'):
                mirror = build_odom_mirror(state)
                stamp = rospy.Time(state['header']['timestamp'] // 1_000_000_000,
                                   state['header']['timestamp'] % 1_000_000_000)
                if publish_odom:
                    odom = Odometry()
                    odom.header.stamp = stamp
                    odom.header.frame_id = mirror['frame_id']
                    odom.child_frame_id = mirror['child_frame_id']
                    odom.pose.pose.position.x, odom.pose.pose.position.y, odom.pose.pose.position.z = mirror['position']
                    odom.pose.pose.orientation.x, odom.pose.pose.orientation.y = mirror['orientation_xyzw'][:2]
                    odom.pose.pose.orientation.z, odom.pose.pose.orientation.w = mirror['orientation_xyzw'][2:]
                    odom.twist.twist.linear.x, odom.twist.twist.linear.y, odom.twist.twist.linear.z = mirror['linear_velocity']
                    odom.pose.covariance = mirror['pose_covariance']
                    odom.twist.covariance = mirror['twist_covariance']
                    odom_pub.publish(odom)
                if broadcast_tf:
                    transform = TransformStamped()
                    transform.header.stamp = stamp
                    transform.header.frame_id = mirror['frame_id']
                    transform.child_frame_id = mirror['child_frame_id']
                    transform.transform.translation.x, transform.transform.translation.y, transform.transform.translation.z = mirror['position']
                    transform.transform.rotation.x, transform.transform.rotation.y = mirror['orientation_xyzw'][:2]
                    transform.transform.rotation.z, transform.transform.rotation.w = mirror['orientation_xyzw'][2:]
                    tf_broadcaster.sendTransform(transform)
            try:
                audit.record('/uav/sensors/state', msg)
            except Exception:
                rospy.signal_shutdown('publication audit failed')
                raise

    def receive(msg):
        with lock:
            if closing:
                return
            try:
                state = (adapt_state(from_ros_state(msg), frames, tolerance) if input_mode == 'px4_estimated'
                         else adapt_scene_ground_truth(from_ros_state(msg), scene_registration))
                publish(gate.consume_state(state, time.monotonic()))
            except ValueError as exc:
                diagnostic(str(exc))

    def clock(msg):
        with lock:
            if closing:
                return
            try:
                now = time.monotonic()
                publish(gate.consume_clock(msg.clock.to_nsec(), now))
                if imu_gate is not None:
                    publish_imu_samples(imu_gate.consume_clock(msg.clock.to_nsec(), now))
            except ValueError as exc:
                diagnostic(str(exc), DiagnosticStatus.ERROR)

    def publish_imu_samples(samples):
        for sample in samples:
            encoded = to_ros_imu(sample)
            imu_pub.publish(encoded)
            try:
                audit.record('/uav/sensors/imu', encoded)
            except Exception:
                rospy.signal_shutdown('publication audit failed')
                raise

    def receive_imu(msg):
        with lock:
            if closing:
                return
            try:
                sample = adapt_imu(from_ros_imu(msg), run_id, calibration_id)
                publish_imu_samples(imu_gate.consume_imu(sample, time.monotonic()))
            except ValueError as exc:
                diagnostic(str(exc))

    state_sub = rospy.Subscriber('/uav/sim/state', AircraftState, receive, queue_size=100)
    clock_sub = rospy.Subscriber('/clock', Clock, clock, queue_size=100)
    imu_sub = rospy.Subscriber('/uav/sim/imu', ImuSample, receive_imu, queue_size=100) if publish_imu else None

    def shutdown():
        nonlocal closing
        with lock:
            closing = True
            state_sub.unregister()
            clock_sub.unregister()
            if imu_sub is not None:
                imu_sub.unregister()
            audit.close(pending_count=gate.pending_count, locked=gate.locked,
                        counters=dict(gate.counters))

    rospy.on_shutdown(shutdown)
    last_diagnostic = 0.
    while not rospy.is_shutdown():
        with lock:
            if closing:
                break
            if (state_pub.get_num_connections() >= 1 and state_sub.get_num_connections() >= 1
                    and clock_sub.get_num_connections() >= 1):
                audit.ready()
            now = time.monotonic()
            publish(gate.poll_timeout(now))
            if imu_gate is not None:
                imu_gate.poll_timeout(now)
            if now - last_diagnostic >= 1:
                diagnostic('clock_gate_locked' if gate.locked else 'clock_gate',
                           DiagnosticStatus.ERROR if gate.locked else DiagnosticStatus.OK)
                last_diagnostic = now
        time.sleep(.02)
    state_sub.unregister()
    clock_sub.unregister()
    if imu_sub is not None:
        imu_sub.unregister()


if __name__ == '__main__':
    main()
