"""Motion protocol semantics and bounded source/profile inputs, without simulators."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sim_motion_fixture import ROOT, ack, expected, frame, response, source_sample, verify_analytic
from ufm_scene_contract.contract import (validate_ack, validate_frame, validate_request, validate_response)
from ufm_scene_contract.profile import load_json, validate_profile, validate_source_sample


class MotionContractTest(unittest.TestCase):
    def setUp(self):
        self.profile = load_json(ROOT / 'configs/sim_scene_motion_fixture.json')

    def test_saved_analytic_units_frames_and_lever_arms(self):
        verify_analytic(expected())
        self.assertEqual(len(expected()['coordinate_cases']), 6)

    def test_fixed_profile_cannot_mix_modes_units_or_synchronization_budgets(self):
        validate_profile(self.profile)
        for key, bad in [('fixture_only', 1), ('mode', 'px4_estimated'), ('step_ns', 4e6),
                         ('initial_forward_speed_mps', 35.), ('registration_id', 'assumed_identity')]:
            row = copy.deepcopy(self.profile)
            row[key] = bad
            with self.assertRaises(ValueError): validate_profile(row)
        row = copy.deepcopy(self.profile)
        row['pairing_ns']['radar_ir'] += 1
        with self.assertRaises(ValueError): validate_profile(row)

    def test_json_duplicate_nonfinite_depth_text_and_file_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}',
                        '[' * 18 + '0' + ']' * 18, json.dumps('x' * 2049), ' ' * (1024 * 1024 + 1)):
                path.write_text(raw)
                with self.assertRaises(ValueError): load_json(path)

    def test_raw_fdm_time_is_checked_without_rounding_bad_times_to_grid(self):
        for i in (0, 1, 25, 250):
            validate_source_sample(source_sample(i), self.profile)
        row = source_sample(0)
        row['sim_time_s'] = 2**-30
        validate_source_sample(row, self.profile)
        row['sim_time_s'] = 2**-29
        with self.assertRaises(ValueError): validate_source_sample(row, self.profile)
        row = source_sample(1)
        row['step_index'] = True
        with self.assertRaises(ValueError): validate_source_sample(row, self.profile)

    def test_fdm_rotation_must_be_finite_proper_orthonormal_and_profile_bounded(self):
        for bad in ([1., 0., 0., 0., 1., 0., 0., 0., -1.], [2.] * 9, [float('nan')] * 9):
            row = source_sample()
            row['R_ecef_frd'] = bad
            with self.assertRaises(ValueError): validate_source_sample(row, self.profile)
        row = source_sample(251)
        with self.assertRaises(ValueError): validate_source_sample(row, self.profile)

    def test_zero_negative_height_and_large_integer_timestamp_are_not_missing(self):
        for height in (0., -2.):
            validate_frame(frame(height=height))
        for probe in expected()['time_cases']:
            row = frame(probe['step_index'])
            validate_frame(row)
            self.assertEqual(row['state']['header']['timestamp'], probe['timestamp'])

    def test_frame_time_identity_enum_and_geometry_are_strict(self):
        probes = [('protocol_version', True), ('step_index', -1), ('step_index', 25.),
                  ('registration_id', 'foreign'), ('angular_velocity_flu', [True, 0, 0])]
        for key, bad in probes:
            row = frame()
            row[key] = bad
            with self.assertRaises(ValueError): validate_frame(row)
        for key, bad in [('timestamp', 100_000_001), ('clock_id', 'sim:other'), ('sample_id', 'old'),
                         ('source_type', 'measured'), ('status', 'unavailable'), ('frame_id', 'odom')]:
            row = frame()
            row['state']['header'][key] = bad
            with self.assertRaises(ValueError): validate_frame(row)
        for key, bad in [('state_source', 'estimated'), ('body_frame_id', 'body_frd'),
                         ('orientation_xyzw', [0, 0, 0, 2]), ('position', [0, float('inf'), 0])]:
            row = frame()
            row['state'][key] = bad
            with self.assertRaises(ValueError): validate_frame(row)

    def test_quality_cannot_be_fabricated_or_supervision_hidden_at_any_layer(self):
        row = frame()
        row['state']['quality']['confidence'] = 1.
        with self.assertRaises(ValueError): validate_frame(row)
        row = frame()
        row['state']['quality']['uncertainty']['value'] = [0.]
        with self.assertRaises(ValueError): validate_frame(row)
        for key in ('lidar', 'target', 'observed_mask', 'training_supervision'):
            for path in ((), ('state',), ('state', 'header'), ('state', 'quality'),
                         ('state', 'quality', 'uncertainty')):
                row, node = frame(), None
                node = row
                for field in path: node = node[field]
                node[key] = []
                with self.assertRaises(ValueError): validate_frame(row)

    def test_text_byte_and_encoding_limits_apply_before_ros(self):
        for run in ('x' * 125, '\ud800', '中' * 42, 'bad\0identity', ' '):
            row = ack()
            row.update(run_id=run, clock_id='sim:' + run)
            with self.assertRaises(ValueError): validate_ack(row)
        row = ack()
        row.update(run_id='中' * 40, clock_id='sim:' + '中' * 40)
        validate_ack(row)

    def test_ack_requires_capture_tick_published_boolean_time_and_binding(self):
        for sensor in (1, 2): validate_ack(ack(sensor=sensor), frame())
        for key, bad in [('protocol_version', 2), ('sensor_kind', 0), ('sensor_kind', True),
                         ('published', 1), ('measurement_timestamp', 100_000_001), ('reason', 'fallback')]:
            row = ack()
            row[key] = bad
            with self.assertRaises(ValueError): validate_ack(row)
        for i in (0, 1, 24):
            with self.assertRaises(ValueError): validate_ack(ack(index=i))
        row = ack(published=False)
        row['measurement_timestamp'] = 0
        validate_ack(row)
        with self.assertRaises(ValueError): validate_ack(ack(), frame(50))

    def test_response_distinguishes_initial_non_capture_complete_and_partial_failure(self):
        for i in (0, 1, 25): validate_response(response(i), dict(frame=frame(i)))
        validate_response(response(accepted=False, applied=False))
        validate_response(response(accepted=False), dict(frame=frame()))
        for changes in ({'applied_frame': None}, {'infrared_timestamp': None},
                        {'radar_timestamp': 100_000_001}, {'reason': 'error'}, {'accepted': 1}):
            row = response()
            row.update(changes)
            with self.assertRaises(ValueError): validate_response(row)
        row = response(1)
        row['radar_timestamp'] = 0
        with self.assertRaises(ValueError): validate_response(row)

    def test_response_binding_rejects_wrong_run_step_pose_twist_and_orientation(self):
        request = dict(frame=frame())
        for row in (response(50), response(height=9.)):
            with self.assertRaises(ValueError): validate_response(row, request)
        row = response()
        row['applied_frame']['angular_velocity_flu'][0] = .1
        with self.assertRaises(ValueError): validate_response(row, request)
        row = response()
        row['applied_frame']['state']['orientation_xyzw'] = [0., 0., 0., -1.]
        validate_response(row, request)
        row['applied_frame']['state']['position'][0] += 1e-10
        validate_response(row, request)
        row['applied_frame']['state']['position'][0] += 1e-7
        with self.assertRaises(ValueError): validate_response(row, request)

    def test_contract_import_has_no_ros_or_dynamics_runtime_dependency(self):
        result = subprocess.run([sys.executable, '-B', '-c',
            'import sys; from ufm_scene_contract.contract import validate_frame; '
            'assert not any(k in sys.modules for k in ("rospy","uav_fusionmap_sim_scene_msgs.msg","ufm_perception.engine"))'],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10.)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_verification_runner_refuses_to_overwrite_existing_partial_evidence(self):
        from sim_motion_run import verify
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            artifact = run / 'actual-00.bin'
            artifact.write_bytes(b'previous evidence')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                verify(run, False)
            self.assertEqual(artifact.read_bytes(), b'previous evidence')


if __name__ == '__main__':
    unittest.main()
