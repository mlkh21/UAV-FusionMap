"""Known-scene statistics and independent geometric acceptance checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
for directory in ('tests', 'simulation', 'sensors'):
    sys.path.insert(0, str(ROOT / directory))

from sens_train_01_scene_suite import (
    _positive_length_voxel_cells,
    build_case,
    audit_case,
    run_suite,
)
from ufm_simulation.perf01a_fixture import make_scan_motion_state


def matrix():
    return yaml.safe_load((ROOT / 'configs/sens_train_01_scene_matrix.yaml').read_text())


def voxel_coverage_matrix():
    return yaml.safe_load((ROOT / 'configs/sens_train_01_voxel_coverage_matrix.yaml').read_text())


class TrainingSceneSuiteTest(unittest.TestCase):
    def test_motion_state_retains_ned_frd_and_explicit_fixture_source(self):
        state = make_scan_motion_state('motion-state', 2, 1_100_000_000,
                                       1_000_000_000, 35., 20.)
        self.assertEqual(state['header']['frame_id'], 'world_ned')
        self.assertEqual(state['header']['source_type'], 'simulation')
        self.assertEqual(state['body_frame_id'], 'body_frd')
        self.assertAlmostEqual(state['position'][0], 3.5)
        self.assertNotEqual(state['orientation_xyzw'], [0., 0., 0., 1.])
        with self.assertRaises(ValueError):
            make_scan_motion_state('bad', 0, 1, 1, float('nan'), 0.)

    def test_all_declared_cases_pass_geometry_and_coverage_checks(self):
        plan = matrix()
        for case in plan['cases']:
            with self.subTest(case=case['case_id']):
                config, states, rows = build_case(case, plan, ROOT)
                result = audit_case(case, plan, config, states, rows)
                self.assertEqual(result['sample_count'], 3)
                self.assertEqual(result['ray_slot_count'], 15)
                self.assertTrue(result['complete_voxel_coverage_checked'])
                counts = result['label_counts']
                self.assertEqual(sum(counts.values()), 3 * 1280)
                if case['geometry'] == 'empty' or case.get('lidar_range_m') == 2.:
                    self.assertEqual(result['echo_count'], 0)
                    self.assertEqual(result['observed_fraction'], 0.)
                    self.assertIsNone(result['compensation_error_m']['max'])
                else:
                    self.assertGreater(result['echo_count'], 0)
                    self.assertLessEqual(result['compensation_error_m']['max'], plan['numerical_tolerance_m'])

    def test_rotation_exercises_interpolation_and_preserves_unknown(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'translation_yaw')
        config, states, rows = build_case(case, plan, ROOT)
        result = audit_case(case, plan, config, states, rows)
        self.assertGreater(result['interpolated_echo_count'], 0)
        self.assertGreater(result['no_echo_slot_count'], 0)
        self.assertGreater(result['label_counts']['unknown'], result['label_counts']['occupied'])

    def test_geometric_corruption_is_rejected_even_with_valid_record_structure(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'translation_yaw')
        config, states, rows = build_case(case, plan, ROOT)
        for kind in ('raw', 'compensated', 'pose_id', 'missing_echo'):
            damaged = copy.deepcopy(rows)
            point = damaged[0]['lidar']['points'][0]
            if kind == 'raw':
                point['raw_xyz'][0] += .1
            elif kind == 'compensated':
                point['x'] += .1
            elif kind == 'pose_id':
                point['pose_sample_ids'] = ['invented']
            else:
                damaged[0]['lidar']['points'].pop()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                audit_case(case, plan, config, states, damaged)

    def test_extra_free_space_in_no_echo_case_is_rejected(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['geometry'] == 'empty')
        config, states, rows = build_case(case, plan, ROOT)
        rows[0]['supervision']['target'][0] = 'free'
        rows[0]['supervision']['observed_mask'][0] = True
        with self.assertRaises(ValueError):
            audit_case(case, plan, config, states, rows)

    def test_missing_free_label_before_real_echo_is_rejected(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'static_single')
        config, states, rows = build_case(case, plan, ROOT)
        self.assertGreater(len(rows[0]['lidar']['points']), 0)
        free_indices = [index for index, label in enumerate(rows[0]['supervision']['target'])
                        if label == 'free']
        self.assertTrue(free_indices)
        flat = free_indices[len(free_indices) // 2]
        rows[0]['supervision']['target'][flat] = 'unknown'
        rows[0]['supervision']['observed_mask'][flat] = False
        with self.assertRaises(ValueError):
            audit_case(case, plan, config, states, rows)

    def test_free_label_outside_all_echo_segments_is_rejected(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'static_single')
        config, states, rows = build_case(case, plan, ROOT)
        self.assertGreater(len(rows[0]['lidar']['points']), 0)
        self.assertEqual(rows[0]['supervision']['target'][0], 'unknown')
        rows[0]['supervision']['target'][0] = 'free'
        rows[0]['supervision']['observed_mask'][0] = True
        with self.assertRaises(ValueError):
            audit_case(case, plan, config, states, rows)

    def test_free_label_inside_segment_bounds_but_off_ray_is_rejected(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'translation_yaw')
        config, states, rows = build_case(case, plan, ROOT)
        grid = rows[0]['supervision']
        # x=[1,1.5), y=[.5,1), z=[0,.5): inside the diagonal echo's
        # bounding box, but outside its ray and all other echo rays.
        shape = grid['grid_shape']
        index = (2 * shape[1] + 5) * shape[2] + 4
        self.assertEqual(grid['target'][index], 'unknown')
        diagonal = next(point for point in rows[0]['lidar']['points'] if point['ray_index'] == 2)
        self.assertGreater(diagonal['x'], 1.5)
        self.assertGreater(diagonal['y'], 1.)
        rows[0]['supervision']['target'][index] = 'free'
        rows[0]['supervision']['observed_mask'][index] = True
        with self.assertRaises(ValueError):
            audit_case(case, plan, config, states, rows)

    def test_short_voxel_chords_require_complete_positive_length_coverage(self):
        plan = voxel_coverage_matrix()
        for case in plan['cases']:
            with self.subTest(case=case['case_id']):
                config, states, rows = build_case(case, plan, ROOT)
                result = audit_case(case, plan, config, states, rows)
                self.assertTrue(result['complete_voxel_coverage_checked'])
                self.assertEqual(result['sample_count'], 3)

    def test_complete_voxel_oracle_rejects_a_removed_positive_length_cell(self):
        plan = voxel_coverage_matrix()
        case = plan['cases'][0]
        config, states, rows = build_case(case, plan, ROOT)
        grid = rows[0]['supervision']
        point = rows[0]['lidar']['points'][0]
        end = [point[axis] for axis in ('x', 'y', 'z')]
        traversed = _positive_length_voxel_cells([0., 0., 0.], end, grid)
        index = next(index for index in sorted(traversed)
                     if grid['target'][index] == 'free')
        grid['target'][index] = 'unknown'
        grid['observed_mask'][index] = False
        with self.assertRaisesRegex(ValueError, 'complete positive-length voxel coverage'):
            audit_case(case, plan, config, states, rows)

    def test_radar_and_ir_values_must_match_the_named_scene(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'translation_yaw')
        config, states, rows = build_case(case, plan, ROOT)
        for kind in ('radar', 'infrared'):
            damaged = copy.deepcopy(rows)
            if kind == 'radar':
                damaged[0]['radar']['points'][0]['x'] += .1
            else:
                damaged[0]['infrared']['image'][0] = .9
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                audit_case(case, plan, config, states, damaged)

    def test_file_readback_is_independent_and_previous_output_is_never_overwritten(self):
        plan = matrix()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'new-run'
            report = run_suite(ROOT / 'configs/sens_train_01_scene_matrix.yaml', output, ROOT)
            self.assertTrue(report['passed'])
            self.assertEqual(report['sample_count'], 36)
            self.assertEqual(report['case_count'], 12)
            old = (output / 'report.json').read_bytes()
            with self.assertRaises(FileExistsError):
                run_suite(ROOT / 'configs/sens_train_01_scene_matrix.yaml', output, ROOT)
            self.assertEqual((output / 'report.json').read_bytes(), old)
            case = plan['cases'][0]
            folder = output / case['case_id']
            config = yaml.safe_load((folder / 'config.yaml').read_text())
            states = [json.loads(line) for line in (folder / 'states.jsonl').read_text().splitlines()]
            rows = [json.loads(line) for line in (folder / 'training-records.jsonl').read_text().splitlines()]
            self.assertEqual(audit_case(case, plan, config, states, rows,
                                       run_id=report['cases'][0]['run_id']), report['cases'][0])

    def test_distinct_output_runs_do_not_reuse_record_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            reports = [run_suite(ROOT / 'configs/sens_train_01_scene_matrix.yaml',
                                  Path(directory) / name, ROOT) for name in ('run-a', 'run-b')]
            self.assertTrue(all(report['passed'] for report in reports))
            self.assertEqual(reports[0]['label_counts'], reports[1]['label_counts'])
            self.assertNotEqual(reports[0]['cases'][0]['run_id'], reports[1]['cases'][0]['run_id'])


if __name__ == '__main__':
    unittest.main()
