"""Existing mapping node query/update contracts without starting ROS."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import rospy
from test_map_query_ros import request
from test_local_map_query import observation
from ufm_ros_contract.perf01a_codec import to_ros_occupancy
from ufm_ros_contract.query_codec import from_ros_query_result

ROOT = Path(__file__).resolve().parents[1]


class Publisher:
    def __init__(self):
        self.rows = []

    def get_num_connections(self):
        return 1

    def publish(self, message):
        self.rows.append(message)


class MappingNodeTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.params = {'~run_id': 'perf-run', '~free_threshold': 0.3,
                       '~occupied_threshold': 0.7}
        self.publishers, self.callbacks, self.services = {}, {}, {}
        self.events = []
        path = ROOT / 'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'
        spec = importlib.util.spec_from_file_location('query_mapping_test', path)
        self.node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.node)

        def publisher(topic, *args, **kwargs):
            result = Publisher()
            self.publishers[topic] = result
            return result

        def subscribe(topic, message_type, callback, **kwargs):
            self.callbacks[topic] = callback

        def service(name, service_type, callback):
            self.services[name] = callback

        for key, value in dict(init_node=lambda *a: None, spin=lambda: None,
                               get_param=lambda name, default=None: self.params.get(name, default),
                               set_param=lambda name, value: self.params.__setitem__(name, value),
                               Publisher=publisher, Subscriber=subscribe, Service=service).items():
            self.stack.enter_context(patch.object(self.node.rospy, key, value))
        self.stack.enter_context(patch.object(self.node, 'publish_perf_event',
            lambda *a, **kw: self.events.append(kw)))

    def start(self, enabled=True):
        if enabled:
            self.params['~enable_query'] = True
        self.node.main()

    def test_query_is_default_off_and_updates_keep_snapshot_path(self):
        self.start(enabled=False)
        self.assertEqual(self.services, {})
        self.callbacks['/uav/perception/occupancy'](to_ros_occupancy(observation()))
        self.assertEqual(len(self.publishers['/uav/map/snapshot'].rows), 1)

    def test_query_uses_updated_map_and_does_not_change_revision(self):
        self.start()
        callback = self.services['/uav/map/query']
        self.assertEqual(from_ros_query_result(callback(request()).result)['status'], 'unavailable')
        message = to_ros_occupancy(observation())
        self.callbacks['/uav/perception/occupancy'](message)
        self.assertEqual(from_ros_query_result(callback(request()).result)['status'], 'occupied')
        self.callbacks['/uav/perception/occupancy'](message)
        result = from_ros_query_result(callback(request(stamp=151)).result)
        self.assertEqual(result['status'], 'stale')
        self.assertEqual(result['revision'], 1)
        self.assertEqual(len(self.publishers['/uav/map/snapshot'].rows), 1)

    def test_invalid_request_is_service_error_and_node_remains_usable(self):
        self.start()
        callback = self.services['/uav/map/query']
        with self.assertRaises(rospy.ServiceException):
            callback(request(max_age_ns=-1))
        self.assertEqual(from_ros_query_result(callback(request()).result)['status'], 'unavailable')

    def test_wrong_run_cannot_seed_configured_node_map(self):
        self.start()
        foreign = observation(run_id='other')
        self.callbacks['/uav/perception/occupancy'](to_ros_occupancy(foreign))
        self.assertEqual(self.publishers['/uav/map/snapshot'].rows, [])
        result = from_ros_query_result(self.services['/uav/map/query'](request()).result)
        self.assertEqual(result['reason'], 'map_unavailable')


if __name__ == '__main__':
    unittest.main()
