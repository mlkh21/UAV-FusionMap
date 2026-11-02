"""Existing mapping node query/update contracts without starting ROS."""
from contextlib import ExitStack
import importlib.util
from pathlib import Path
from types import SimpleNamespace
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
            return SimpleNamespace(get_num_connections=lambda: 1)

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

    def test_no_observers_start_and_invalid_codec_frame_does_not_kill_callback(self):
        self.params.update({'/perf01a_require_observers': False,
                            '/ufm_diagnostics_enabled': False})
        with patch.object(Publisher, 'get_num_connections', return_value=0), \
                patch.object(self.node.time, 'monotonic', side_effect=[0., 16.]):
            self.start()
        invalid = to_ros_occupancy(observation())
        invalid.context.T_mapping_source_status = 255
        self.callbacks['/uav/perception/occupancy'](invalid)
        self.assertEqual(self.publishers['/uav/map/snapshot'].rows, [])
        self.callbacks['/uav/perception/occupancy'](to_ros_occupancy(observation()))
        self.assertEqual(len(self.publishers['/uav/map/snapshot'].rows), 1)
        self.assertNotIn('/uav/perf/events', self.publishers)

    def test_m2_selection_missing_config_or_unknown_backend_cannot_start(self):
        for backend in ('m2_fixture', 'm3_fixture', 'm4_fixture', 'typo'):
            self.params['~map_backend'] = backend
            with self.assertRaises(ValueError):
                self.start()
        self.assertEqual(self.callbacks, {})

    def test_explicit_m2_accumulates_and_rejects_old_placeholder(self):
        from m2_fixture import CONFIG, load_spec, observation as m2_observation
        self.params.pop('~free_threshold')
        self.params.pop('~occupied_threshold')
        self.params.update({'~map_backend': 'm2_fixture', '~m2_fixture_config': str(CONFIG),
                            '~clock_id': 'sim:perf-run', '~rolling_enabled': True})
        self.start()
        self.callbacks['/uav/perception/occupancy'](to_ros_occupancy(observation()))
        self.assertEqual(self.publishers['/uav/map/snapshot'].rows, [])
        for index in range(2):
            self.callbacks['/uav/perception/occupancy'](to_ros_occupancy(
                m2_observation(load_spec(), 'perf-run', index, 'occupied')))
        self.assertEqual(len(self.publishers['/uav/map/snapshot'].rows), 2)
        result = from_ros_query_result(self.services['/uav/map/query'](request(
            map_id='m2-fixture', stamp=20_000_000, max_age_ns=100_000_000)).result)
        self.assertEqual(result['status'], 'occupied')
        self.assertAlmostEqual(result['probability'], .9, places=6)

    def test_m2_config_without_backend_cannot_silently_start_latest(self):
        self.params['~m2_fixture_config'] = '/unused/m2-config.yaml'
        with self.assertRaisesRegex(ValueError, 'explicit m2_fixture backend'):
            self.start()
        self.assertEqual(self.callbacks, {})

    def test_m3_config_without_selection_or_mixed_with_m2_cannot_start(self):
        self.params['~m3_fixture_config'] = '/unused/m3-config.yaml'
        with self.assertRaisesRegex(ValueError, 'explicit m3_fixture backend'):
            self.start()
        self.params['~map_backend'] = 'm2_fixture'
        with self.assertRaisesRegex(ValueError, 'cannot be mixed'):
            self.start()
        self.assertEqual(self.callbacks, {})

    def test_m4_config_cannot_be_implicit_or_mixed_with_other_fixture(self):
        self.params['~m4_fixture_config']='/unused/m4.yaml'
        with self.assertRaisesRegex(ValueError,'explicit m4_fixture backend'):self.start()
        for backend in ('m2_fixture','m3_fixture'):
            self.params['~map_backend']=backend
            with self.assertRaisesRegex(ValueError,'cannot be mixed'):self.start()
        self.assertEqual(self.callbacks,{})

    def test_explicit_m4_map_query_and_aging_use_scene_geometry(self):
        import json
        import tempfile
        import yaml
        from rosgraph_msgs.msg import Clock
        from m4_fixture import bound_spec,load_spec,observation as m4_observation,step
        self.params.pop('~free_threshold')
        self.params.pop('~occupied_threshold')
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'m4.yaml'
            spec=bound_spec(load_spec(),'perf-run')
            config.write_text(yaml.safe_dump(spec))
            self.params.update({'~map_backend':'m4_fixture','~m4_fixture_config':str(config),
                '~clock_id':'sim:perf-run','~rolling_enabled':True,'/perf01a_map_audit_directory':folder})
            shutdown=[]
            with patch.object(self.node.rospy,'on_shutdown',side_effect=shutdown.append):self.start()
            receive=self.callbacks['/uav/perception/occupancy']
            receive(to_ros_occupancy(m4_observation(spec,step(0,10_000_000,[],[],0,None))))
            result=from_ros_query_result(self.services['/uav/map/query'](request(
                map_id='m4-scene-fixture',frame_id='map',point=[40.25,.25,.25],stamp=10_000_000)).result)
            self.assertEqual(result['status'],'occupied')
            self.assertEqual(result['index'],[80,32,8])
            self.callbacks['/clock'](Clock(clock=rospy.Time(0,120_000_000)))
            shutdown[0]()
            report=json.loads((Path(folder)/'map-aging.json').read_text())
            self.assertEqual(report['rows'][-1]['stale'],[[80,32,8]])

    def test_explicit_m3_rejects_bad_quality_atomically_and_recovers(self):
        import copy
        from m3_fixture import CONFIG, load_spec
        from m3_motion_fixture import motion_observation
        self.params.pop('~free_threshold')
        self.params.pop('~occupied_threshold')
        self.params.update({'~map_backend': 'm3_fixture', '~m3_fixture_config': str(CONFIG),
                            '~clock_id': 'sim:perf-run', '~rolling_enabled': True})
        self.start()
        receive = self.callbacks['/uav/perception/occupancy']
        first = motion_observation(load_spec(), 'perf-run', 0)
        bad = motion_observation(load_spec(), 'perf-run', 1)
        bad['voxels'].append(copy.deepcopy(bad['voxels'][0]))
        bad['voxels'][-1]['index'] = [40, 16, 8]
        bad['voxels'][-1]['uncertainty']['unit'] = 'm2'
        receive(to_ros_occupancy(first))
        receive(to_ros_occupancy(bad))
        self.assertEqual(len(self.publishers['/uav/map/snapshot'].rows), 1)
        self.assertEqual(self.events[-1]['status'], 'unavailable')
        receive(to_ros_occupancy(motion_observation(load_spec(), 'perf-run', 2)))
        result = from_ros_query_result(self.services['/uav/map/query'](request(
            map_id='m3-fixture', stamp=30_000_000, max_age_ns=100_000_000)).result)
        self.assertEqual(result['revision'], 2)
        self.assertEqual(result['uncertainty']['status'], 'available')
        self.assertEqual(result['uncertainty']['source'], load_spec()['interval_profile']['output_source'])
        self.assertAlmostEqual(result['probability'], .9, places=6)


if __name__ == '__main__':
    unittest.main()
