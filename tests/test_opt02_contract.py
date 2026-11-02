"""OPT-02消费边界反例；使用实际ROS编解码和节点回调，不启动master。"""
import copy
import importlib.util
import unittest
import xmlrpc.client
from types import SimpleNamespace
from unittest.mock import patch

import test_perception_node as harness
from test_perf01a_contract import valid_bundle
from test_map_query_node import Publisher
from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.placeholder import placeholder_infer
from ufm_ros_contract.perf01a_codec import to_ros_bundle, to_ros_occupancy, from_ros_occupancy
from runtime_config import load_map_config, normalize_map_config, ros_map_config


class InputBoundaryTest(harness.PerceptionNodeTest):
    def test_bad_nested_bundle_preserves_old_map_and_valid_frame_recovers(self):
        self.node.main()
        cases = [('radar', 'timestamp', 1), ('radar', 'frame_id', 'base_link'),
                 ('infrared', 'clock_id', 'foreign'), ('state', 'run_id', 'foreign'),
                 ('state', 'timestamp', 151_000_000),
                 ('state', 'timestamp', 139_999_999)]
        for component, field, value in cases:
            local_map = SparseLocalMap()
            local_map.update(placeholder_infer(valid_bundle()))
            before = local_map.snapshot()
            bundle = valid_bundle(radar_timestamp=150_000_000)
            bundle['header']['sample_id'] += ':bad'
            message = to_ros_bundle(bundle)
            setattr(getattr(message, component).header, field, value)
            with self.subTest(component=component, field=field, value=value):
                self.callbacks['/uav/sensors/bundle'](message)
                result = from_ros_occupancy(self.publishers['/uav/perception/occupancy'].rows[-1])
                self.assertEqual(result['header']['status'], 'unavailable')
                self.assertFalse(local_map.update(result))
                self.assertEqual(before, local_map.snapshot())
                recovery = valid_bundle(radar_timestamp=200_000_000)
                recovery['header']['sample_id'] += ':recover'
                self.callbacks['/uav/sensors/bundle'](to_ros_bundle(recovery))
                result = from_ros_occupancy(self.publishers['/uav/perception/occupancy'].rows[-1])
                self.assertTrue(local_map.update(result))
                self.assertEqual(local_map.snapshot()['revision'], 2)

    def test_declared_ages_and_calibration_must_match(self):
        self.node.main()
        for key, value in [('radar_ir_delta_ns', 1), ('pose_age_ns', 1),
                           ('calibration_id', 'foreign')]:
            message = to_ros_bundle(valid_bundle())
            setattr(message, key, value)
            self.callbacks['/uav/sensors/bundle'](message)
            result = from_ros_occupancy(self.publishers['/uav/perception/occupancy'].rows[-1])
            self.assertEqual(result['header']['status'], 'unavailable')
        message = to_ros_bundle(valid_bundle())
        message.infrared.calibration_id = 'foreign'
        self.callbacks['/uav/sensors/bundle'](message)
        self.assertEqual(self.publishers['/uav/perception/occupancy'].rows[-1].header.status, 2)

    def test_untrusted_context_is_dropped_then_valid_recovers(self):
        self.node.main()
        for key, value in [('reference_timestamp', 0), ('clock_id', 'foreign'),
                           ('source_frame_id', 'base_link'), ('mapping_frame_id', 'map'),
                           ('T_mapping_source', [-1., 0, 0, 0, 0, 1., 0, 0,
                                                  0, 0, 1., 0, 0, 0, 0, 1.])]:
            message = to_ros_bundle(valid_bundle())
            setattr(message.context, key, value)
            self.callbacks['/uav/sensors/bundle'](message)
        self.assertEqual(self.publishers['/uav/perception/occupancy'].rows, [])
        self.callbacks['/uav/sensors/bundle'](to_ros_bundle(valid_bundle()))
        self.assertEqual(len(self.publishers['/uav/perception/occupancy'].rows), 1)

    def test_exact_age_boundaries_and_configured_limits(self):
        self.params.update({'~max_radar_ir_delta_ns': 6_000_000,
                            '~max_pose_age_ns': 12_000_000})
        self.node.main()
        for delta, age in [(5_000_000, 10_000_000), (-5_000_000, 10_000_000),
                           (6_000_000, 12_000_000)]:
            message = to_ros_bundle(valid_bundle())
            message.infrared.header.timestamp += delta
            message.infrared.exposure_start += delta
            message.infrared.exposure_end += delta
            message.state.header.timestamp -= age
            message.radar_ir_delta_ns, message.pose_age_ns = abs(delta), age
            self.callbacks['/uav/sensors/bundle'](message)
            self.assertEqual(self.publishers['/uav/perception/occupancy'].rows[-1].header.status, 0)

    def test_delayed_mandatory_consumer_waits_without_observers(self):
        self.params.update({'/perf01a_require_observers': False,
                            '/ufm_diagnostics_enabled': False})
        def wait(_):
            self.assertNotIn('~ready', self.params)
            self.assertEqual(self.publishers['/uav/perception/occupancy'].rows, [])
        with patch.object(Publisher, 'get_num_connections', side_effect=[0, 0, 1]), \
                patch.object(self.node.time, 'monotonic', return_value=0.), \
                patch.object(self.node.time, 'sleep', side_effect=wait), \
                patch.object(self.node.rospy, 'is_shutdown', return_value=False):
            self.node.main()
        self.assertEqual(self.params['~ready'], 'perf-run')

    def test_nested_identity_and_time_cannot_create_map_evidence(self):
        self.node.main()
        for field in ('run_id', 'clock_id', 'frame_id', 'timestamp'):
            message = to_ros_bundle(valid_bundle())
            if field == 'timestamp':
                message.infrared.header.timestamp += 1_000_000_000
                message.infrared.exposure_start += 1_000_000_000
                message.infrared.exposure_end += 1_000_000_000
            else:
                setattr(message.radar.header, field, 'foreign')
            with self.subTest(field=field):
                self.callbacks['/uav/sensors/bundle'](message)
                rows = self.publishers['/uav/perception/occupancy'].rows
                if rows:
                    result = from_ros_occupancy(rows[-1])
                    self.assertEqual(result['header']['status'], 'unavailable')
                    self.assertFalse(SparseLocalMap().update(result))

    def test_missing_mandatory_consumer_never_reports_ready(self):
        self.params.update({'/perf01a_require_observers': False,
                            '/ufm_diagnostics_enabled': False})
        with patch.object(Publisher, 'get_num_connections', return_value=0), \
                patch.object(self.node.time, 'monotonic', side_effect=[0., 16.]), \
                patch.object(self.node.rospy, 'is_shutdown', return_value=False):
            with self.assertRaises(RuntimeError):
                self.node.main()
        self.assertNotIn('~ready', self.params)

    def test_three_second_config_snapshot_is_xmlrpc_safe(self):
        self.params['~staleness_limit_ns'] = 3_000_000_000
        self.node.main()
        snapshot = self.params['~resolved_map_config']
        xmlrpc.client.dumps((snapshot,))
        self.assertEqual(int(snapshot['staleness_limit_ns']), 3_000_000_000)


class GeometryAndQualityTest(unittest.TestCase):
    def test_invalid_rotations_for_source_and_body_fixed_and_rolling(self):
        for entries in ({0: -1.}, {0: 2.}, {1: .25}, {0: 0.}, {3: float('nan')}):
            for key in ('T_mapping_source', 'T_mapping_body'):
                bundle = valid_bundle()
                for index, value in entries.items():
                    bundle['context'][key][index] = value
                with self.subTest(entries=entries, key=key), self.assertRaises(ValueError):
                    placeholder_infer(bundle)

    def test_reflection_is_not_a_rotation(self):
        bundle = valid_bundle()
        bundle['context']['T_mapping_source'][0] = -1.
        with self.assertRaises(ValueError):
            placeholder_infer(bundle)
        for rolling in (False, True):
            local_map = SparseLocalMap(rolling_enabled=rolling)
            first = placeholder_infer(valid_bundle(), rolling_grid=rolling)
            local_map.update(first)
            before = local_map.snapshot()
            candidate = placeholder_infer(valid_bundle(radar_timestamp=150_000_000),
                                          rolling_grid=rolling)
            candidate['header']['sample_id'] += ':later'
            candidate['context']['T_mapping_body'][0] = -1.
            with self.subTest(rolling=rolling), self.assertRaises(ValueError):
                local_map.update(candidate)
            self.assertEqual(before, local_map.snapshot())

    def test_bad_quality_rejected_by_wire_and_pure_map_atomically(self):
        for quality in ({'confidence': float('nan')},
                        {'uncertainty': dict(status='available', kind='', value=[],
                                             unit='', source='')}):
            observation = placeholder_infer(valid_bundle())
            observation['voxels'][0].update(copy.deepcopy(quality))
            with self.subTest(quality=quality):
                with self.assertRaises(ValueError):
                    to_ros_occupancy(observation)
                local_map = SparseLocalMap()
                before = local_map.snapshot()
                with self.assertRaises(ValueError):
                    local_map.update(observation)
                self.assertEqual(before, local_map.snapshot())

    def test_quality_numeric_and_structural_boundaries(self):
        variance = dict(status='available', kind='occupancy_variance', value=[.125],
                        unit='dimensionless', source='fixture')
        bad = [{'confidence': value} for value in (True, float('nan'), float('inf'), -.1, 1.1)]
        bad += [{'uncertainty': dict(variance, **change)} for change in (
            {'value': []}, {'value': [float('nan')]}, {'value': [-.1]},
            {'value': [.1, .2]}, {'kind': ''}, {'unit': ''}, {'source': ''},
            {'status': 'unavailable', 'value': []})]
        for quality in bad:
            observation = placeholder_infer(valid_bundle())
            observation['voxels'][0].update(quality)
            with self.subTest(quality=quality):
                with self.assertRaises(ValueError):
                    to_ros_occupancy(observation)
                with self.assertRaises(ValueError):
                    SparseLocalMap().update(observation)
        for confidence in (None, 0., .25, 1.):
            observation = placeholder_infer(valid_bundle())
            observation['voxels'][0].update(confidence=confidence, uncertainty=variance)
            result = from_ros_occupancy(to_ros_occupancy(observation))
            self.assertEqual(result['voxels'][0]['confidence'], confidence)
            self.assertEqual(result['voxels'][0]['uncertainty'], variance)
            result['voxels'][0]['confidence'] = float('nan')
            message = to_ros_occupancy(observation)
            message.voxels[0].confidence_available = True
            message.voxels[0].confidence = float('nan')
            with self.assertRaises(ValueError):
                from_ros_occupancy(message)


class ConfigSnapshotTest(unittest.TestCase):
    def test_exact_nanoseconds_and_old_integer_snapshots(self):
        settings = load_map_config()
        for duration in (100_000_000, 3_000_000_000, 2**31-1, 2**31, 2**63-1):
            original = dict(settings, staleness_limit_ns=duration)
            encoded = ros_map_config(original)
            self.assertEqual(normalize_map_config(encoded), original)
            self.assertEqual(normalize_map_config(original), original)
            xmlrpc.client.dumps((encoded,))
        for value in (True, -1, 3.5, '3.0', 'NaN', 2**63, str(2**63)):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ros_map_config(dict(settings, staleness_limit_ns=value))


class SourceHandshakeTest(unittest.TestCase):
    def load(self, package, script):
        path = harness.ROOT / 'ros_ws/src' / package / 'scripts' / script
        spec = importlib.util.spec_from_file_location('opt02_' + script[:-3], path)
        node = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(node)
        return node

    def test_source_waits_for_same_run_business_ready_then_starts_at_zero(self):
        node = self.load('uav_fusionmap_simulation', 'perf01a_source_node.py')
        params = {'~run_id': 'r', '~duration_s': .1,
                  '/perf01a_sensor/ready': 'r', '/perf01a_mapping/ready': 'r',
                  '/perf01a_perception/ready': 'old-run'}
        publishers, waits = {}, []
        def publisher(topic, *a, **kw):
            publishers[topic] = Publisher()
            return publishers[topic]
        def wait(_):
            if '/perf01a_perception/ready' in params and params['/perf01a_perception/ready'] != 'r':
                self.assertEqual(publishers['/clock'].rows, [])
                self.assertEqual(publishers['/uav/sim/state'].rows, [])
                waits.append(True)
                if len(waits) == 2:
                    params['/perf01a_perception/ready'] = 'r'
        with patch.multiple(node.rospy, init_node=lambda *a, **kw: None, spin=lambda: None,
                get_param=lambda key, default=None: params.get(key, default),
                set_param=lambda key, value: params.__setitem__(key, value),
                Publisher=publisher, is_shutdown=lambda: False), \
                patch.object(node.time, 'monotonic', return_value=0.), \
                patch.object(node.time, 'sleep', side_effect=wait):
            node.main()
        self.assertEqual(len(waits), 2)
        states = publishers['/uav/sim/state'].rows
        self.assertEqual([msg.header.timestamp for msg in states], [0, 50_000_000])
        self.assertTrue(states[0].header.sample_id.endswith(':0'))

    def test_sensor_waits_for_inbound_clock_connection(self):
        node = self.load('uav_fusionmap_sensors', 'perf01a_sensor_node.py')
        params = {'~run_id': 'r', '/perf01a_require_observers': False,
                  '/ufm_diagnostics_enabled': False}
        connected = [False]
        def subscriber(topic, *a, **kw):
            return SimpleNamespace(get_num_connections=lambda: int(
                topic != '/clock' or connected[0]))
        def wait(_):
            self.assertNotIn('~ready', params)
            connected[0] = True
        with patch.multiple(node.rospy,
                get_param=lambda key, default=None: params.get(key, default),
                set_param=lambda key, value: params.__setitem__(key, value),
                Publisher=lambda *a, **kw: Publisher(), Subscriber=subscriber,
                is_shutdown=lambda: False), \
                patch.object(node.time, 'monotonic', return_value=0.), \
                patch.object(node.time, 'sleep', side_effect=wait):
            node.SensorFixture()
        self.assertEqual(params['~ready'], 'r')


if __name__ == '__main__':
    unittest.main()
