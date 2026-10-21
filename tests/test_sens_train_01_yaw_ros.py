"""Yaw/interpolation acceptance through the training ROS receipt verifier."""
import copy
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
for directory in ('sensors', 'simulation', 'ros_ws'):
    sys.path.insert(0, str(ROOT / directory))

from ufm_simulation.perf01a_fixture import make_scan_motion_state, make_training_fixture_state
from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.training_stream import TrainingScanBuffer
from sens_train_01_run import validate_training_run


def yaw_fixture(cfg=None):
    cfg = cfg or yaml.safe_load((ROOT / 'configs/sens_train_01_yaw_fixture.yaml').read_text())
    buffer = TrainingScanBuffer('yaw-ros', cfg, range(100_000_000, 2_000_000_001, 100_000_000))
    receipts = dict(state=[], clock=[], radar=[], infrared=[], training=[])
    rows = []
    for sequence, stamp in enumerate(range(0, 2_100_000_001, 100_000_000)):
        source = make_scan_motion_state('yaw-ros', sequence, stamp, **cfg['fixture_motion'])
        receipts['state'].append(source)
        receipts['clock'].append(stamp)
        rows.extend(buffer.advance_clock(stamp))
        rows.extend(buffer.push_state(adapt_state(source, {
            'odom_origin_policy': 'px4_estimator_local_origin',
            'body_origin_policy': 'source_body_virtual_flu',
        })))
    buffer.finish()
    from ufm_ros_contract.perf01a_codec import (
        to_ros_radar, from_ros_radar, to_ros_infrared, from_ros_infrared,
    )
    receipts['radar'] = [from_ros_radar(to_ros_radar(row['radar'])) for row in rows]
    receipts['infrared'] = [from_ros_infrared(to_ros_infrared(row['infrared'])) for row in rows]
    receipts['training'] = copy.deepcopy(rows)
    return cfg, rows, receipts


class TrainingYawRosAuditTest(unittest.TestCase):
    def test_yaw_and_interpolated_echoes_pass_receipt_geometry_audit(self):
        cfg, rows, receipts = yaw_fixture()
        self.assertNotEqual(receipts['state'][-1]['orientation_xyzw'][2], 0.)
        report = validate_training_run(rows, receipts, cfg, 'yaw-ros')
        self.assertEqual(report['record_count'], 20)
        self.assertEqual(report['source_state_count'], 22)
        self.assertEqual(report['yaw_oracle']['sample_count'], 20)
        self.assertEqual(report['yaw_oracle']['interpolated_echo_count'], 20)
        self.assertEqual(report['yaw_oracle']['no_echo_slot_count'], 20)
        self.assertLess(report['yaw_oracle']['compensation_error_m']['max'], 1e-6)

    def test_source_profile_preserves_legacy_states_and_rejects_inference(self):
        from ufm_simulation.perf01a_fixture import make_motion_state
        for name in ('fixture', 'multiray_fixture', 'motion_fixture'):
            cfg = yaml.safe_load((ROOT / ('configs/sens_train_01_' + name + '.yaml')).read_text())
            self.assertEqual(make_training_fixture_state('profile', 1, 100_000_000, cfg),
                             make_motion_state('profile', 1, 100_000_000, .1))
        cfg, _, receipts = yaw_fixture()
        for sequence, source in enumerate(receipts['state']):
            self.assertEqual(make_training_fixture_state('yaw-ros', sequence,
                                                        source['header']['timestamp'], cfg), source)
        cfg['mode'] = 'inference'
        with self.assertRaises(ValueError):
            make_training_fixture_state('profile', 1, 100_000_000, cfg)

    def test_interpolated_echo_and_no_echo_slot_keep_distinct_time_evidence(self):
        _, rows, _ = yaw_fixture()
        for row in rows:
            lidar = row['lidar']
            interpolated = next(point for point in lidar['points'] if point['ray_index'] == 1)
            self.assertEqual(interpolated['point_time_ns'], lidar['scan_start'] + 50_000_000)
            self.assertEqual(len(interpolated['pose_sample_ids']), 2)
            self.assertEqual(lidar['ray_time_offsets_ns'][3], 150_000_000)
            self.assertNotIn(3, [point['ray_index'] for point in lidar['points']])

    def test_wrong_source_rotation_body_velocity_and_clock_or_missing_tail_fail(self):
        cfg, rows, receipts = yaw_fixture()
        for field in ('orientation_xyzw', 'linear_velocity', 'position', 'clock', 'tail'):
            damaged = copy.deepcopy(receipts)
            if field == 'clock':
                damaged['clock'][1] += 1
            elif field == 'tail':
                damaged['state'].pop()
            else:
                damaged['state'][1][field][0 if field != 'orientation_xyzw' else 2] += .01
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_training_run(rows, damaged, cfg, 'yaw-ros')

    def test_self_consistent_wrong_geometry_pose_labels_and_inputs_fail(self):
        cfg, rows, receipts = yaw_fixture()
        for field in ('raw', 'compensated', 'pose_ids', 'unknown', 'occupied', 'image', 'radar'):
            damaged_rows, damaged = copy.deepcopy(rows), copy.deepcopy(receipts)
            row = damaged_rows[0]
            if field == 'raw':
                row['lidar']['points'][1]['raw_xyz'][0] += .01
            elif field == 'compensated':
                row['lidar']['points'][1]['x'] += .01
            elif field == 'pose_ids':
                row['lidar']['points'][1]['pose_sample_ids'].pop()
            elif field == 'unknown':
                cell = (4 * 10 + 2) * 8 + 4
                row['supervision']['target'][cell] = 'free'
                row['supervision']['observed_mask'][cell] = True
            elif field == 'occupied':
                cell = row['supervision']['target'].index('occupied')
                row['supervision']['target'][cell] = 'free'
            elif field == 'image':
                row['infrared']['image'][0] = .9
                damaged['infrared'][0]['image'][0] = .9
            else:
                row['radar']['points'][0]['x'] += .01
                damaged['radar'][0]['points'][0]['x'] += .01
            damaged['training'] = copy.deepcopy(damaged_rows)
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_training_run(damaged_rows, damaged, cfg, 'yaw-ros')

    def test_zero_yaw_cannot_close_yaw_acceptance(self):
        cfg = yaml.safe_load((ROOT / 'configs/sens_train_01_yaw_fixture.yaml').read_text())
        cfg['fixture_motion']['yaw_rate_deg_s'] = 0.
        cfg, rows, receipts = yaw_fixture(cfg)
        with self.assertRaisesRegex(ValueError, 'nonzero rotation'):
            validate_training_run(rows, receipts, cfg, 'yaw-ros')


if __name__ == '__main__':
    unittest.main()
