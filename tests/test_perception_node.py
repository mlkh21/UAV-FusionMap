"""感知ROS包装的异常业务输出；不启动master或研究模型。"""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import unittest
import time
from unittest.mock import patch

from test_perf01a_contract import valid_bundle
from test_map_query_node import Publisher
from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.placeholder import placeholder_infer
from ufm_ros_contract.perf01a_codec import to_ros_bundle, from_ros_occupancy


ROOT = Path(__file__).resolve().parents[1]


class PerceptionNodeTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.params = {'~run_id': 'perf-run'}
        self.publishers, self.callbacks = {}, {}
        path = ROOT / 'ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py'
        spec = importlib.util.spec_from_file_location('review_perception_test', path)
        self.node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.node)

        def publisher(topic, *args, **kwargs):
            result = Publisher()
            self.publishers[topic] = result
            return result

        def subscriber(topic, message_type, callback, **kwargs):
            self.callbacks[topic] = callback

        for name, value in dict(init_node=lambda *a: None, spin=lambda: None,
                get_param=lambda key, default=None: self.params.get(key, default),
                set_param=lambda key, value: self.params.__setitem__(key, value),
                Publisher=publisher, Subscriber=subscriber, logerr=lambda *a: None).items():
            self.stack.enter_context(patch.object(self.node.rospy, name, value))

    def test_backend_exception_emits_unavailable_and_preserves_old_map(self):
        self.node.main()
        bundle = valid_bundle()
        local_map = SparseLocalMap()
        local_map.update(placeholder_infer(bundle))
        before = local_map.snapshot()
        bundle = valid_bundle(radar_timestamp=150_000_000)
        bundle['header']['sample_id'] += ':later'
        with patch('ufm_perception.engine.placeholder_infer', side_effect=ValueError('backend failed')):
            self.callbacks['/uav/sensors/bundle'](to_ros_bundle(bundle))
        rows = self.publishers['/uav/perception/occupancy'].rows
        self.assertEqual(len(rows), 1)
        result = from_ros_occupancy(rows[0])
        self.assertEqual(result['header']['status'], 'unavailable')
        self.assertIn('backend failed', result['header']['reason'])
        self.assertEqual(result['header']['timestamp'], bundle['header']['timestamp'])
        self.assertEqual(result['voxels'], [])
        self.assertFalse(local_map.update(result))
        self.assertEqual(local_map.snapshot(), before)

    def test_occupancy_ready_endpoint_precedes_encoding(self):
        self.node.main()
        clock = [100]
        encode = self.node.to_ros_occupancy

        def delayed_encode(value):
            clock[0] += 200
            return encode(value)

        with patch.object(self.node.time, 'monotonic_ns', side_effect=lambda: clock[0]), \
                patch.object(self.node, 'to_ros_occupancy', side_effect=delayed_encode):
            self.callbacks['/uav/sensors/bundle'](to_ros_bundle(valid_bundle()))
        event = self.publishers['/uav/perf/events'].rows[0]
        self.assertEqual(event.stage, 'occupancy_ready')
        self.assertEqual(event.monotonic_ns, 100)
        self.assertLess(event.monotonic_ns, clock[0])

    def test_invalid_wire_input_is_diagnosed_and_next_frame_recovers(self):
        self.node.main()
        message = to_ros_bundle(valid_bundle())
        message.context.T_mapping_source_status = 255
        self.callbacks['/uav/sensors/bundle'](message)
        self.assertEqual(self.publishers['/uav/perception/occupancy'].rows, [])
        self.assertEqual(self.publishers['/uav/perf/events'].rows[-1].status, 'unavailable')
        self.callbacks['/uav/sensors/bundle'](to_ros_bundle(valid_bundle()))
        self.assertEqual(len(self.publishers['/uav/perception/occupancy'].rows), 1)

    def test_no_observer_start_and_shared_nondefault_geometry(self):
        self.params.update({'/perf01a_require_observers': False,
                            '/ufm_diagnostics_enabled': False,
                            '~resolution': [.25, .5, 1.], '~shape': [40, 8, 8],
                            '~origin': [0., -2., -4.]})
        self.node.main()  # occupancy→mapping是必需连接；本例只移除诊断观察器。
        self.callbacks['/uav/sensors/bundle'](to_ros_bundle(valid_bundle()))
        result = from_ros_occupancy(self.publishers['/uav/perception/occupancy'].rows[0])
        self.assertEqual(result['resolution'], [.25, .5, 1.])
        self.assertEqual(result['shape'], [40, 8, 8])
        self.assertEqual(result['origin'], [0., -2., -4.])
        self.assertNotIn('/uav/perf/events', self.publishers)

    def test_optional_worker_publishes_from_wall_clock_without_ros_timer(self):
        self.params.update({'~worker_enabled': True, '~worker_deadline_s': 2.})
        shutdown = []
        self.stack.enter_context(patch.object(self.node.rospy, 'on_shutdown', shutdown.append))
        self.node.main()
        self.addCleanup(lambda: shutdown[0]())
        self.callbacks['/uav/sensors/bundle'](to_ros_bundle(valid_bundle()))
        rows = self.publishers['/uav/perception/occupancy'].rows
        deadline = time.monotonic() + 3
        while not rows and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(len(rows), 1)
        self.assertEqual(from_ros_occupancy(rows[0])['header']['status'], 'valid')

    def test_worker_deadline_and_recovery_through_real_node_callback(self):
        from test_perception_worker import SlowEngine
        self.params.update({'~worker_enabled': True, '~worker_deadline_s': .4})
        shutdown = []
        self.stack.enter_context(patch.object(self.node.rospy, 'on_shutdown', shutdown.append))
        self.node.main(engine_factory=SlowEngine)
        self.addCleanup(lambda: shutdown[0]())
        slow = valid_bundle()
        slow['header']['sample_id'] += ':slow'
        callback = self.callbacks['/uav/sensors/bundle']
        callback(to_ros_bundle(slow))
        rows = self.publishers['/uav/perception/occupancy'].rows
        deadline = time.monotonic() + 3
        while not rows and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(from_ros_occupancy(rows[0])['header']['reason'],
                         'perception_backend_timeout')
        recovery = valid_bundle(radar_timestamp=200_000_000)
        recovery['header']['sample_id'] += ':recovery'
        callback(to_ros_bundle(recovery))
        deadline = time.monotonic() + 3
        while len(rows) < 2 and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(from_ros_occupancy(rows[-1])['header']['status'], 'valid')


if __name__ == '__main__':
    unittest.main()
