"""回归状态先于clock到达时，不得用最新槽覆盖未处理状态。"""
import importlib.util
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock

from rosgraph_msgs.msg import Clock
import rospy
from ufm_sensors.clock_gate import StateClockGate
from ufm_simulation.perf01a_fixture import make_fixture_state
from ufm_ros_contract import to_ros_state

path = Path(__file__).resolve().parents[1] / 'ros_ws/src/uav_fusionmap_sensors/scripts/perf01a_sensor_node.py'
spec = importlib.util.spec_from_file_location('sensor_fixture_node', path)
node = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node)


class PendingStateTest(unittest.TestCase):
    def test_two_future_states_are_both_released_in_order(self):
        fixture = node.SensorFixture.__new__(node.SensorFixture)
        fixture.lock = threading.RLock()
        fixture.run_id = 'r'
        fixture.state = None
        fixture.latest_clock_ns = 0
        fixture.gate = StateClockGate('r')
        fixture.state_pub = Mock()
        delivered = []
        def collect(state):
            if state is None:
                state = fixture.state
                if state is None or state['header']['timestamp'] > fixture.latest_clock_ns:
                    return
            delivered.append(state['header']['timestamp'])
        fixture.tick = collect
        fixture.receive_clock(Clock(clock=rospy.Time(0)))
        for i in (1, 2):
            fixture.receive_state(to_ros_state(make_fixture_state('r', i, i * 50_000_000)))
        self.assertEqual(delivered, [])
        fixture.receive_clock(Clock(clock=rospy.Time(0, 100_000_000)))
        self.assertEqual(delivered, [50_000_000, 100_000_000])
