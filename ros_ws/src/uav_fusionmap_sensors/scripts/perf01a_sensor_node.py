#!/usr/bin/env python
"""PERF-01-A fake Radar/IR、同步和SensorBundle薄ROS包装。"""
import sys
import threading
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState, InfraredFrame, RadarFrame, SensorBundle

from ufm_ros_contract import from_ros_state, to_ros_state
from ufm_ros_contract.perf01a_codec import to_ros_bundle, to_ros_infrared, to_ros_radar
from ufm_sensors.perf01a_fixture import build_sensor_bundle
from ufm_sensors.clock_gate import StateClockGate
from ufm_sensors.state_adapter import adapt_state
from ufm_ros_contract.perf01a_ros import PerfTrace, publish_perf_event, perf_publisher
from ufm_ros_contract.perf01a_wire import WireAudit
from ufm_sensors.perf01a_scenarios import scenario_inputs


class SensorFixture:
    def __init__(self):
        self.run_id = rospy.get_param("~run_id")
        self.max_delta_ns = int(rospy.get_param("~max_radar_ir_delta_ns", 5_000_000))
        self.max_pose_age_ns = int(rospy.get_param("~max_pose_age_ns", 10_000_000))
        self.frequency_hz = float(rospy.get_param("~fixture_frequency_hz", 20.0))
        self.profile = rospy.get_param('~scenario_profile', {'ir_resolution': [2, 2], 'fault': 'none'})
        self.segmented = rospy.get_param('/perf01a_segmented_timing', False)
        self.audit = WireAudit.for_node('sensor')
        self.audit.install(InfraredFrame, 'serialize')
        self.audit.install(SensorBundle, 'serialize')
        observer_mode = rospy.get_param('/perf01a_observer_mode', 'full')
        radar_pub = rospy.Publisher("/uav/sensors/radar", RadarFrame, queue_size=100)
        ir_pub = rospy.Publisher("/uav/sensors/infrared", InfraredFrame, queue_size=100)
        bundle_pub = rospy.Publisher("/uav/sensors/bundle", SensorBundle, queue_size=100)
        state_pub = rospy.Publisher("/uav/sensors/state", AircraftState, queue_size=100)
        event_pub = perf_publisher(rospy)
        self.radar_pub, self.ir_pub, self.bundle_pub, self.state_pub, self.event_pub = (
            radar_pub, ir_pub, bundle_pub, state_pub, event_pub)
        self.lock = threading.RLock()
        self.gate = StateClockGate(self.run_id)
        self.sequence = 0
        state_sub = rospy.Subscriber("/uav/sim/state", AircraftState, self.receive_state, queue_size=100)
        clock_sub = rospy.Subscriber("/clock", Clock, self.receive_clock, queue_size=100)
        deadline = time.monotonic() + 15.0
        require_observers = rospy.get_param('/perf01a_require_observers', True)
        expected_bundle = 1 if not require_observers or observer_mode == 'metadata' else 2
        expected_ir = 0 if not require_observers or observer_mode == 'metadata' else 1
        while not ((not require_observers or event_pub is None or event_pub.get_num_connections()) and
                   bundle_pub.get_num_connections() >= expected_bundle and
                   ir_pub.get_num_connections() >= expected_ir and
                   state_sub.get_num_connections() and clock_sub.get_num_connections()):
            if time.monotonic() > deadline or rospy.is_shutdown():
                raise RuntimeError('sensor subscribers not ready')
            time.sleep(.02)
        rospy.set_param('~ready', self.run_id)

    def receive_state(self, msg):
        try:
            with self.lock:
                state = adapt_state(from_ros_state(msg), {
                    "odom_origin_policy": "px4_estimator_local_origin",
                    "body_origin_policy": "source_body_virtual_flu"})
                self.publish_ready(self.gate.consume_state(state, time.monotonic()))
        except Exception as exc:
            rospy.logerr("PERF-01-A state adaptation failed: %s", exc)

    def receive_clock(self, msg):
        with self.lock:
            try:
                self.publish_ready(self.gate.consume_clock(msg.clock.to_nsec(), time.monotonic()))
            except ValueError as exc:
                rospy.logerr('PERF-01-A clock gate failed: %s', exc)

    def publish_ready(self, states):
        for state in states:
            self.state_pub.publish(to_ros_state(state))
            self.tick(state)

    def tick(self, state):
        try:
            sequence = self.sequence
            self.sequence += 1
            start_ns = time.monotonic_ns()
            timestamp_ns = state["header"]["timestamp"]
            trace = PerfTrace(self.segmented)
            radar, infrared, states = trace.call('fixture_generation', scenario_inputs,
                self.run_id, sequence, state, self.profile, measure=trace.call)
            bundle_id = 'sensors.bundle:' + radar['header']['sample_id']
            publish_perf_event(self.event_pub, self.run_id, bundle_id, 'radar_receive',
                               timestamp_ns, monotonic_ns=start_ns)
            if infrared is not None:
                ir_msg = trace.call('infrared_encode', to_ros_infrared, infrared)
                trace.call('infrared_publish', self.ir_pub.publish, ir_msg)
                self.audit.record('publish:InfraredFrame', ir_msg, connections=self.ir_pub.get_num_connections())
                publish_perf_event(self.event_pub, self.run_id, bundle_id, 'infrared_receive',
                                   infrared['header']['timestamp'])
            else:
                publish_perf_event(self.event_pub, self.run_id, bundle_id, 'infrared_receive',
                                   timestamp_ns, status='unavailable', reason='infrared_unavailable')
            bundle, reason = trace.call('pairing', build_sensor_bundle, radar, infrared, states,
                                                 self.max_delta_ns, self.max_pose_age_ns)
            radar_msg = trace.call('radar_encode', to_ros_radar, radar)
            trace.call('radar_publish', self.radar_pub.publish, radar_msg)
            if bundle is None:
                publish_perf_event(self.event_pub, self.run_id, bundle_id, "sensor_bundle_ready",
                                   timestamp_ns, status='unavailable' if infrared is None else 'timeout', reason=reason)
                trace.flush(self.event_pub, self.run_id, bundle_id, timestamp_ns)
                return
            publish_perf_event(self.event_pub, self.run_id, bundle_id, "sensor_bundle_ready",
                               timestamp_ns, time.monotonic_ns() - start_ns)
            bundle_msg = trace.call('bundle_encode', to_ros_bundle, bundle)
            trace.call('bundle_publish', self.bundle_pub.publish, bundle_msg)
            self.audit.record('publish:SensorBundle', bundle_msg, connections=self.bundle_pub.get_num_connections())
            trace.flush(self.event_pub, self.run_id, bundle_id, timestamp_ns)
        except Exception as exc:
            rospy.logerr("PERF-01-A sensor tick failed: %s", exc)


def main():
    if not sys.executable.endswith("/Radar-Diffusion/bin/python"):
        raise RuntimeError("PERF-01-A必须使用Radar-Diffusion Python")
    rospy.init_node("perf01a_sensor")
    SensorFixture()
    rospy.spin()


if __name__ == "__main__":
    main()
