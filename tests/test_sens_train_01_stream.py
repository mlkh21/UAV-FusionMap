"""Training scan history, clock coverage and file/receipt acceptance gates."""
import copy
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
for directory in ('sensors', 'simulation', 'ros_ws'):
    sys.path.insert(0, str(ROOT / directory))

from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.training_stream import TrainingScanBuffer
from ufm_simulation.perf01a_fixture import make_motion_state
from sens_train_01_run import validate_training_run


def config(name='motion'):
    suffix = 'motion_' if name == 'motion' else ''
    return yaml.safe_load((ROOT / ('configs/sens_train_01_' + suffix + 'fixture.yaml')).read_text())


def state(stamp, run='stream'):
    return adapt_state(make_motion_state(run, stamp, stamp, .1), {
        'odom_origin_policy': 'px4_estimator_local_origin',
        'body_origin_policy': 'source_body_virtual_flu',
    })


class TrainingStreamTest(unittest.TestCase):
    def test_nonzero_scan_waits_for_both_clock_and_scan_end_state(self):
        buffer = TrainingScanBuffer('stream', config(), [100_000_000])
        self.assertEqual(buffer.advance_clock(100_000_000), [])
        self.assertEqual(buffer.push_state(state(0)), [])
        self.assertEqual(buffer.push_state(state(100_000_000)), [])
        self.assertEqual(buffer.push_state(state(200_000_000)), [])
        rows = buffer.advance_clock(200_000_000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['lidar']['scan_start'], 0)
        self.assertEqual(rows[0]['lidar']['scan_end'], 200_000_000)
        self.assertEqual(rows[0]['lidar']['ray_time_offsets_ns'], [0, 100_000_000, 200_000_000])
        self.assertEqual([p['ray_index'] for p in rows[0]['lidar']['points']], [0, 2])
        self.assertAlmostEqual(rows[0]['lidar']['points'][0]['x'], 5.24)
        self.assertEqual(buffer.advance_clock(300_000_000), [])
        buffer.finish()

    def test_clock_can_arrive_before_final_state(self):
        buffer = TrainingScanBuffer('stream', config(), [100_000_000])
        buffer.advance_clock(200_000_000)
        buffer.push_state(state(0))
        buffer.push_state(state(100_000_000))
        self.assertEqual(len(buffer.push_state(state(200_000_000))), 1)
        buffer.finish()

    def test_zero_duration_keeps_original_state_and_clock_gate(self):
        buffer = TrainingScanBuffer('stream', config('single'), [100_000_000])
        self.assertEqual(buffer.push_state(state(100_000_000)), [])
        rows = buffer.advance_clock(100_000_000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['schema_version'], '0.1')
        self.assertEqual(rows[0]['lidar']['scan_start'], rows[0]['lidar']['scan_end'])
        buffer.finish()

    def test_missing_leading_history_and_incomplete_tail_are_rejected(self):
        buffer = TrainingScanBuffer('stream', config(), [100_000_000])
        buffer.advance_clock(200_000_000)
        buffer.push_state(state(100_000_000))
        with self.assertRaises(ValueError):
            buffer.push_state(state(200_000_000))
        incomplete = TrainingScanBuffer('stream', config(), [100_000_000])
        incomplete.advance_clock(100_000_000)
        incomplete.push_state(state(0))
        incomplete.push_state(state(100_000_000))
        with self.assertRaises(ValueError):
            incomplete.finish()

    def test_regression_duplicate_invalid_and_cross_run_states_are_rejected(self):
        for kind in ('duplicate', 'sample_id', 'regression', 'run', 'clock', 'status'):
            with self.subTest(kind=kind):
                buffer = TrainingScanBuffer('stream', config(), [100_000_000])
                buffer.advance_clock(200_000_000)
                buffer.push_state(state(100_000_000))
                damaged = state(200_000_000)
                if kind == 'duplicate':
                    damaged = state(100_000_000)
                elif kind == 'sample_id':
                    damaged['header']['sample_id'] = state(100_000_000)['header']['sample_id']
                elif kind == 'regression':
                    damaged = state(0)
                elif kind in ('run', 'clock'):
                    damaged['header'][kind + '_id'] = 'other'
                else:
                    damaged['header']['status'] = 'unavailable'
                with self.assertRaises(ValueError):
                    buffer.push_state(damaged)
        buffer = TrainingScanBuffer('stream', config(), [100_000_000])
        buffer.advance_clock(200_000_000)
        with self.assertRaises(ValueError):
            buffer.advance_clock(100_000_000)

    def test_pending_clock_and_total_history_have_explicit_bounds(self):
        buffer = TrainingScanBuffer('stream', config(), [100_000_000], max_pending_states=2)
        buffer.push_state(state(0))
        buffer.push_state(state(100_000_000))
        with self.assertRaises(ValueError):
            buffer.push_state(state(200_000_000))
        buffer = TrainingScanBuffer('stream', config(), [100_000_000], max_history_states=2)
        buffer.advance_clock(200_000_000)
        buffer.push_state(state(0))
        buffer.push_state(state(100_000_000))
        with self.assertRaises(ValueError):
            buffer.push_state(state(200_000_000))


def run_fixture(name='motion'):
    cfg = config(name)
    half = cfg['lidar']['scan_duration_ns'] // 2
    buffer = TrainingScanBuffer('stream', cfg, range(100_000_000, 2_000_000_001, 100_000_000))
    receipts = {'state': [], 'clock': [], 'radar': [], 'infrared': [], 'training': []}
    rows = []
    for index, stamp in enumerate(range(100_000_000 - half, 2_000_000_001 + half, 100_000_000)):
        source = make_motion_state('stream', index, stamp, .1)
        receipts['state'].append(source)
        receipts['clock'].append(stamp)
        rows.extend(buffer.advance_clock(stamp))
        rows.extend(buffer.push_state(adapt_state(source, {
            'odom_origin_policy': 'px4_estimator_local_origin',
            'body_origin_policy': 'source_body_virtual_flu',
        })))
    from ufm_ros_contract.perf01a_codec import (
        to_ros_radar, from_ros_radar, to_ros_infrared, from_ros_infrared,
    )
    receipts['radar'] = [from_ros_radar(to_ros_radar(row['radar'])) for row in rows]
    receipts['infrared'] = [from_ros_infrared(to_ros_infrared(row['infrared'])) for row in rows]
    receipts['training'] = copy.deepcopy(rows)
    return cfg, rows, receipts


class TrainingRunAuditTest(unittest.TestCase):
    def test_motion_and_zero_duration_file_receipts_are_accepted(self):
        for name in ('motion', 'single'):
            with self.subTest(name=name):
                cfg, rows, receipts = run_fixture(name)
                report = validate_training_run(rows, receipts, cfg, 'stream')
                self.assertEqual(report['record_count'], 20)
                self.assertEqual(report['source_state_count'], 22 if name == 'motion' else 20)
                self.assertEqual(report['motion_oracle_count'], 20 if name == 'motion' else 0)

    def test_missing_reordered_or_cross_run_receipts_fail(self):
        cfg, rows, receipts = run_fixture()
        for kind in ('training', 'radar', 'infrared', 'state', 'clock', 'reordered', 'run'):
            damaged = copy.deepcopy(receipts)
            if kind in ('training', 'radar', 'infrared', 'state', 'clock'):
                damaged[kind].pop()
            elif kind == 'reordered':
                damaged['training'][0], damaged['training'][1] = damaged['training'][1], damaged['training'][0]
            else:
                damaged['radar'][0]['header']['run_id'] = 'other'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_training_run(rows, damaged, cfg, 'stream')

    def test_ros_value_and_sampling_time_mutations_fail(self):
        cfg, rows, receipts = run_fixture()
        for kind in ('radar', 'infrared', 'time', 'pose'):
            damaged = copy.deepcopy(receipts)
            if kind == 'radar':
                damaged['radar'][0]['points'][0]['x'] += .1
            elif kind == 'infrared':
                damaged['infrared'][0]['image'][0] += .1
            elif kind == 'time':
                damaged['clock'][0] += 1
            else:
                damaged['state'][0]['position'][0] += .1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_training_run(rows, damaged, cfg, 'stream')

    def test_self_consistent_but_wrong_geometry_or_unknown_labels_fail(self):
        cfg, rows, receipts = run_fixture()
        for kind in ('raw', 'compensated', 'history_id', 'unknown'):
            damaged_rows = copy.deepcopy(rows)
            row = damaged_rows[0]
            if kind == 'raw':
                row['lidar']['points'][0]['raw_xyz'][0] += .1
            elif kind == 'compensated':
                row['lidar']['points'][0]['x'] += .1
            elif kind == 'history_id':
                row['lidar']['points'][0]['pose_sample_ids'] = ['invented']
            else:
                flat = (4 * 10 + 3) * 8 + 4
                row['supervision']['target'][flat] = 'free'
                row['supervision']['observed_mask'][flat] = True
            damaged_receipts = copy.deepcopy(receipts)
            damaged_receipts['training'] = copy.deepcopy(damaged_rows)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_training_run(damaged_rows, damaged_receipts, cfg, 'stream')


if __name__ == '__main__':
    unittest.main()
