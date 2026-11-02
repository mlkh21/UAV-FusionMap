"""Public flight v2 offline acceptance, identity and independent boundary expectations."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sim_flight_v2_fixture import ROOT, ack, expected, frame, replace, response
from ufm_flight_contract import contract as c
from ufm_flight_contract.endpoints import ENDPOINTS, validate_endpoints
from ufm_flight_contract.profile import load_profile, validate_profile
from ufm_scene_contract import contract as v1


class FlightV2ContractTest(unittest.TestCase):
    def test_literal_time_and_full_capture_table(self):
        for step, stamp, capture in expected()['time_cases']:
            value = frame(step)
            c.validate_frame(value)
            c.validate_response(response(step), request=dict(frame=value))
            self.assertEqual(value['state']['header']['timestamp'], stamp)
            self.assertEqual(c.capture_step(step), capture)
        steps = [i for i in range(10001) if c.capture_step(i)]
        self.assertEqual(steps, expected()['capture_steps'])
        self.assertEqual(len(steps), 100)
        self.assertEqual([steps[0] * c.STEP_NS, steps[-1] * c.STEP_NS], [30100000000, 40000000000])

    def test_invalid_step_types_and_limits_in_capture_predicate(self):
        for step in (-1, 10001, True, 25., None, 2**64):
            with self.subTest(step=step), self.assertRaises(ValueError):
                c.capture_step(step)

    def test_frozen_frame_rejections(self):
        for path, bad in expected()['reject_frame']:
            with self.subTest(path=path, bad=bad), self.assertRaises(ValueError):
                c.validate_frame(replace(frame(), path, bad))

    def test_ground_anchor_height_and_distance_boundaries(self):
        for step, position, accepted in expected()['position_cases']:
            value = replace(frame(step), 'state.position', position)
            if accepted:
                c.validate_frame(value)
            else:
                with self.assertRaises(ValueError): c.validate_frame(value)
        # The ENU anchor is a registered CG origin, not a claim about actual AGL.
        c.validate_frame(replace(frame(1), 'state.position', [1., -2., .4]))

    def test_time_not_reset_shifted_or_cropped(self):
        for step, stamp in ((7525, 100000000), (7500, 0), (10000, 10000000000), (1, -1),
                            (7525, 30100000001), (7525, 30100000000.)):
            with self.assertRaises(ValueError):
                c.validate_frame(replace(frame(step), 'state.header.timestamp', stamp))

    def test_nonfinite_vectors_and_quaternions_at_all_positions(self):
        for path, size in (('state.position', 3), ('state.orientation_xyzw', 4),
                           ('state.linear_velocity', 3), ('angular_velocity_flu', 3)):
            for index in range(size):
                for bad in (float('nan'), float('inf'), -float('inf'), True, 10**1000):
                    row = frame(1)
                    node = row
                    for key in path.split('.'):
                        node = node[key]
                    node[index] = bad
                    with self.subTest(path=path, index=index), self.assertRaises(ValueError):
                        c.validate_frame(row)

    def test_unknown_or_training_fields_rejected_at_every_nesting(self):
        for key in ('lidar', 'target', 'observed_mask', 'training_supervision'):
            for path in ('', 'state', 'state.header', 'state.quality', 'state.quality.uncertainty'):
                value, node = frame(), None
                node = value
                for part in path.split('.') if path else []:
                    node = node[part]
                node[key] = []
                with self.assertRaises(ValueError): c.validate_frame(value)
            for value, validator in ((dict(frame=frame(), **{key: []}), c.validate_request),
                                     (dict(ack(), **{key: []}), c.validate_ack),
                                     (dict(response(), **{key: []}), c.validate_response)):
                with self.assertRaises(ValueError): validator(value)

    def test_identity_utf8_bytes_nul_and_full_sample_id_bound(self):
        for text in ('', ' ', '\0', '\ud800', 'x' * 129, '\u4e2d' * 43):
            row = frame()
            row['state']['header']['run_id'] = text
            row['state']['header']['clock_id'] = 'sim:' + text
            row['state']['header']['sample_id'] = 'scene.frame:' + text + ':0'
            with self.assertRaises(ValueError): c.validate_frame(row)
        for length, valid in ((110, True), (111, False)):
            row = frame(10000)
            row['state']['header'].update(run_id='x' * length, clock_id='sim:' + 'x' * length,
                sample_id='scene.frame:' + 'x' * length + ':10000')
            if valid:
                c.validate_frame(row)
            else:
                with self.assertRaises(ValueError): c.validate_frame(row)

    def test_ack_only_in_capture_window_even_on_failure(self):
        for index in (0, 25, 250, 7500, 7501, 7524, 7526, 9999, 10001):
            for published in (True, False):
                with self.assertRaises(ValueError): c.validate_ack(ack(index, published=published))
        for index in expected()['capture_steps']:
            for sensor in (1, 2):
                c.validate_ack(ack(index, sensor), frame=frame(index))
                c.validate_ack(ack(index, sensor, False), frame=frame(index))

    def test_ack_identity_kind_boolean_time_and_reason_rejections(self):
        for key, bad in (('protocol_version', 1), ('protocol_version', True), ('clock_id', 'sim:foreign'),
                         ('sensor_kind', True), ('sensor_kind', 0), ('sensor_kind', 3),
                         ('published', 1), ('measurement_timestamp', 0), ('measurement_timestamp', 30100000001),
                         ('measurement_timestamp', 30100000000.), ('reason', 'fake_success')):
            with self.assertRaises(ValueError): c.validate_ack(dict(ack(), **{key: bad}))
        for reason in ('', 'BadReason', 'bad reason', 'x' * 257):
            with self.assertRaises(ValueError): c.validate_ack(dict(ack(published=False), reason=reason))
        with self.assertRaises(ValueError): c.validate_ack(ack(), frame=frame(7550))
        wanted = replace(frame(7525), 'state.header.run_id', 'foreign')
        wanted = replace(wanted, 'state.header.clock_id', 'sim:foreign')
        wanted = replace(wanted, 'state.header.sample_id', 'scene.frame:foreign:7525')
        with self.assertRaises(ValueError): c.validate_ack(ack(), frame=wanted)

    def test_preparation_is_absence_of_capture_and_failure_keeps_partial_receipts(self):
        for index in (0, 25, 2500, 7500, 7524):
            value = response(index)
            self.assertIsNone(value['radar_timestamp'])
            self.assertIsNone(value['infrared_timestamp'])
            c.validate_response(value)
            with self.assertRaises(ValueError):
                c.validate_response(dict(value, radar_timestamp=index * 4000000))
        c.validate_response(response(7525, False, True))
        c.validate_response(dict(response(7525, False), radar_timestamp=None, infrared_timestamp=None))
        for key, bad in (('accepted', 1), ('reason', 'fake_success'), ('radar_timestamp', 0),
                         ('infrared_timestamp', None), ('infrared_timestamp', 30200000000)):
            with self.assertRaises(ValueError): c.validate_response(dict(response(7525), **{key: bad}))

    def test_versionless_unapplied_response_is_rejected_without_fabricating_application(self):
        value = dict(accepted=False, reason='scene_rejected', applied_frame=None,
                     radar_timestamp=None, infrared_timestamp=None)
        v1.validate_response(value)
        for bindings in ({}, dict(request=dict(frame=frame()))):
            with self.assertRaisesRegex(ValueError, 'requires_versioned_applied_frame'):
                c.validate_response(value, **bindings)

    def test_applied_request_binding_and_quaternion_sign(self):
        value, wanted = response(7525), dict(frame=frame(7525))
        c.validate_response(value, request=wanted)
        sign = replace(value, 'applied_frame.state.orientation_xyzw', [0., 0., 0., -1.])
        c.validate_response(sign, request=wanted)
        for path, bad in (('applied_frame.state.position', [1., 0., .5]),
                          ('applied_frame.state.linear_velocity', [1., 0., 0.]),
                          ('applied_frame.angular_velocity_flu', [0., 0., 1.]),
                          ('applied_frame.state.orientation_xyzw', [0., 0., 1., 0.])):
            with self.assertRaises(ValueError): c.validate_response(replace(value, path, bad), request=wanted)
        with self.assertRaises(ValueError): c.validate_response(value, request=dict(frame=frame(7550)))

    def test_both_directions_reject_cross_version_semantics(self):
        from sim_motion_fixture import ack as old_ack, frame as old_frame, response as old_response
        for new_check, old_check, new_value, old_value in (
                (c.validate_frame, v1.validate_frame, frame(), old_frame()),
                (c.validate_request, v1.validate_request, dict(frame=frame()), dict(frame=old_frame())),
                (c.validate_ack, v1.validate_ack, ack(), old_ack()),
                (c.validate_response, v1.validate_response, response(), old_response())):
            with self.assertRaises(ValueError): new_check(old_value)
            with self.assertRaises(ValueError): old_check(new_value)

    def test_profile_is_exact_observation_only_metadata(self):
        profile = load_profile(ROOT / 'configs/sim_flight_scene_fixture.json')
        validate_profile(profile)
        for path, bad in (('commands_enabled', True), ('observation_only', False), ('protocol_version', 1),
                          ('duration_steps', 10001), ('duration_steps', 10000.), ('step_ns', 4000001),
                          ('capture_start_after_step', 0), ('capture_period_steps', 1),
                          ('scene_anchor_m', [0., 0., 8.]), ('pairing_ns.pose_age', 10000000),
                          ('limits.wire_bytes', 4097), ('limits.receipts_per_stream', 4096),
                          ('deadlines_ns.session', 240000000001), ('target', [])):
            with self.assertRaises(ValueError): validate_profile(replace(profile, path, bad))
        with self.assertRaises(ValueError):
            validate_profile(json.loads((ROOT / 'configs/sim_scene_motion_fixture.json').read_text()))
        from ufm_scene_contract.profile import validate_profile as old_profile
        with self.assertRaises(ValueError): old_profile(profile)

    def test_profile_json_duplicate_encoding_depth_nodes_and_byte_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff',
                        b'[' * 10 + b'0' + b']' * 10, b'[' * 1100 + b'0' + b']' * 1100,
                        b'[' + b'0,' * 8192 + b'0]', b' ' * (256 * 1024 + 1)):
                path.write_bytes(raw)
                with self.assertRaises(ValueError): load_profile(path)

    def test_endpoint_contract_is_frozen_and_disjoint_without_registration(self):
        validate_endpoints(expected()['endpoints'])
        self.assertEqual({k: list(v) for k, v in ENDPOINTS.items()}, expected()['endpoints'])
        with self.assertRaises(TypeError): ENDPOINTS['step'] = ('other', 'other')
        for key in ENDPOINTS:
            for index in (0, 1):
                values = copy.deepcopy(expected()['endpoints'])
                values[key][index] = values[key][index].replace('/flight', '') if index == 0 else 'std_msgs/String'
                with self.assertRaises(ValueError): validate_endpoints(values)

    def test_imports_have_no_ros_runtime_or_generated_message_side_effects(self):
        code = ('import sys; import ufm_flight_contract.contract, ufm_flight_contract.profile, '
                'ufm_flight_contract.endpoints, ufm_flight_contract.codec; '
                'assert not any(k in sys.modules for k in '
                '("rospy", "uav_fusionmap_msgs.msg", "uav_fusionmap_sim_scene_msgs.msg"))')
        result = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
