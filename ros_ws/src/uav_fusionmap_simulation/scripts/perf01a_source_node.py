#!/usr/bin/env python
"""PERF-01-A独立fixture状态/时钟源，不启动PX4、JSBSim或研究模型。"""
import sys
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState

from ufm_ros_contract import to_ros_state
from ufm_simulation.perf01a_fixture import make_fixture_state


def main():
    rospy.init_node("perf01a_source", disable_signals=False)
    run_id = rospy.get_param("~run_id")
    rate_hz = float(rospy.get_param("~state_frequency_hz", 20.0))
    duration_s = float(rospy.get_param("~duration_s", 10.0))
    clock_pub = rospy.Publisher("/clock", Clock, queue_size=100)
    state_pub = rospy.Publisher("/uav/sim/state", AircraftState, queue_size=100)
    period = 1.0 / rate_hz
    sequence = 0
    connect_deadline = time.monotonic() + 15.0
    while not rospy.is_shutdown():
        ready = all(rospy.get_param('/perf01a_' + name + '/ready', '') == run_id
                    for name in ('sensor', 'perception', 'mapping'))
        if ready and state_pub.get_num_connections() and clock_pub.get_num_connections():
            break
        if time.monotonic() >= connect_deadline:
            raise RuntimeError('fixture subscribers not ready')
        time.sleep(0.05)
    expected = max(1, int(round(duration_s * rate_hz)))
    rospy.set_param('~expected_samples', expected)
    while not rospy.is_shutdown() and sequence < expected:
        timestamp_ns = sequence * int(round(period * 1_000_000_000))
        source = make_fixture_state(run_id, sequence, timestamp_ns)
        # 仅供fixture使用；保持SIM-01已验证的simulation -> sensors入口。
        clock_pub.publish(Clock(clock=rospy.Time(timestamp_ns // 1_000_000_000,
                                                 timestamp_ns % 1_000_000_000)))
        state_pub.publish(to_ros_state(source))
        sequence += 1
        time.sleep(period)
    rospy.set_param('~done', run_id)
    rospy.spin()  # 由运行器等待下游排空后统一停止。


if __name__ == "__main__":
    if not sys.executable.endswith("/Radar-Diffusion/bin/python"):
        raise RuntimeError("PERF-01-A必须使用Radar-Diffusion Python")
    main()
