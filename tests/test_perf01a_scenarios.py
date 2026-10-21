"""大图序列化与故障窗口拒绝/恢复回归；旧地图不能被失效输入刷新。"""
import copy
import io
from pathlib import Path
import unittest

import yaml
from ufm_sensors.perf01a_scenarios import scenario_inputs
from ufm_sensors.perf01a_fixture import build_sensor_bundle
from ufm_simulation.perf01a_fixture import make_fixture_state
from ufm_sensors.state_adapter import adapt_state
from ufm_perception.placeholder import placeholder_infer
from ufm_mapping.local_map import SparseLocalMap
from ufm_ros_contract.perf01a_codec import to_ros_bundle, from_ros_bundle
from perf01a_validation import expected_sequences, validate_receipts


def state(sequence):
    return adapt_state(make_fixture_state('r', sequence, sequence * 50_000_000), {
        'odom_origin_policy': 'px4_estimator_local_origin',
        'body_origin_policy': 'source_body_virtual_flu'})


class ScenariosTest(unittest.TestCase):
    def setUp(self):
        with (Path(__file__).resolve().parents[1] / 'configs/perf01a_scenarios.yaml').open() as handle:
            self.profiles = yaml.safe_load(handle)['scenarios']

    def test_fault_window_preserves_map_and_recovers(self):
        for name, reason in (('sync_timeout', 'radar_ir_timeout'), ('ir_missing', 'infrared_unavailable'),
                             ('pose_stale', 'pose_age_exceeded')):
            with self.subTest(name=name):
                local = SparseLocalMap()
                profile = self.profiles[name]
                rejects = []
                for i in range(40):
                    source = state(i)
                    before_source = copy.deepcopy(source)
                    radar, ir, states = scenario_inputs('r', i, source, profile)
                    before_map = local.snapshot()
                    bundle, rejected = build_sensor_bundle(radar, ir, states)
                    if 10 <= i < 20:
                        self.assertIsNone(bundle)
                        self.assertEqual(rejected, reason)
                        self.assertEqual(local.snapshot(), before_map)
                        rejects.append(i)
                        if i >= 12:
                            self.assertTrue(local.stale_cells(i * 50_000_000))
                    else:
                        self.assertEqual(rejected, '')
                        self.assertTrue(local.update(placeholder_infer(bundle)))
                    self.assertEqual(source, before_source)
                self.assertEqual(rejects, list(range(10, 20)))
                self.assertEqual(local.snapshot()['revision'], 30)
                self.assertEqual(local.snapshot()['header']['timestamp'], 1_950_000_000)

    def test_five_ms_boundary_is_accepted_without_retimestamping(self):
        radar, infrared, states = scenario_inputs('r', 12, state(12), self.profiles['sync_boundary'])
        bundle, reason = build_sensor_bundle(radar, infrared, states)
        self.assertEqual(reason, '')
        self.assertEqual(bundle['radar_ir_delta_ns'], 5_000_000)
        self.assertEqual(bundle['infrared']['header']['timestamp'], 595_000_000)
        self.assertEqual(bundle['header']['timestamp'], 600_000_000)

    def test_parameterized_fixture_reaches_placeholder_and_map(self):
        radar, infrared, states = scenario_inputs('r', 1, state(1),
                                                   self.profiles['parameterized'])
        self.assertEqual(len(radar['points']), 1)
        self.assertEqual(radar['scan_start'], radar['scan_end'])
        self.assertEqual((infrared['width'], infrared['height']), (4, 3))
        self.assertNotEqual(infrared['image'], [.4] * 12)
        bundle, reason = build_sensor_bundle(radar, infrared, states)
        self.assertEqual(reason, '')
        observation = placeholder_infer(bundle)
        local = SparseLocalMap()
        self.assertTrue(local.update(observation))
        self.assertEqual(local.snapshot()['revision'], 1)
        self.assertEqual(local.snapshot()['header']['timestamp'], 50_000_000)

    def test_full_image_survives_real_ros_serialization(self):
        radar, infrared, states = scenario_inputs('r', 0, state(0), self.profiles['full_ir'])
        bundle, reason = build_sensor_bundle(radar, infrared, states)
        self.assertEqual(reason, '')
        message = to_ros_bundle(bundle)
        stream = io.BytesIO()
        message.serialize(stream)
        restored = from_ros_bundle(type(message)().deserialize(stream.getvalue()))
        self.assertEqual(restored['infrared']['width'], 640)
        self.assertEqual(restored['infrared']['height'], 512)
        self.assertEqual(restored['infrared']['image'], [0.5] * 327680)

    def test_image_copy_preserves_input_and_bundle_ownership(self):
        radar, infrared, states = scenario_inputs('r', 0, state(0), self.profiles['full_ir'])
        bundle, reason = build_sensor_bundle(radar, infrared, states)
        self.assertEqual(reason, '')
        infrared['image'][0] = 9.
        infrared['camera_info']['width'] = 1
        self.assertEqual(bundle['infrared']['image'][0], .5)
        self.assertEqual(bundle['infrared']['camera_info']['width'], 640)
        bundle['infrared']['image'][1] = 7.
        self.assertEqual(infrared['image'][1], .5)

    def test_registered_counts_do_not_hide_unexpected_missing_samples(self):
        self.assertEqual(len(expected_sequences(40, self.profiles['sync_timeout'])['map']), 30)
        self.assertEqual(len(expected_sequences(40, self.profiles['ir_missing'])['infrared']), 30)
        records = {key: [] for key in ('state', 'radar', 'infrared', 'bundle', 'occupancy', 'map')}
        errors = validate_receipts(records, 40, self.profiles['sync_timeout'], 'r', 50_000_000)
        self.assertIn('map: count or identity mismatch', errors)
