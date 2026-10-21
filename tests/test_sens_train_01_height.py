"""Non-horizontal, training-only observed-mask and FOV checks."""
import copy
from pathlib import Path
import sys
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

from sens_train_01_scene_suite import build_case, audit_case


def matrix():
    return yaml.safe_load((ROOT / 'configs/sens_train_01_height_matrix.yaml').read_text())


class TrainingHeightCoverageTest(unittest.TestCase):
    def test_oblique_rays_hit_high_and_low_obstacles(self):
        plan = matrix()
        for case_id, sign in (('elevated_hit', 1), ('lower_hit', -1)):
            case = next(item for item in plan['cases'] if item['case_id'] == case_id)
            with self.subTest(case=case_id):
                config, states, rows = build_case(case, plan, ROOT)
                result = audit_case(case, plan, config, states, rows)
                self.assertEqual(result['sample_count'], 3)
                self.assertGreater(result['echo_count'], 0)
                self.assertTrue(any(point['raw_xyz'][2] * sign > 0
                                    for row in rows for point in row['lidar']['points']))
                self.assertGreater(result['label_counts']['unknown'], 0)

    def test_valid_ray_missing_high_obstacle_is_unknown(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'vertical_no_echo')
        config, states, rows = build_case(case, plan, ROOT)
        result = audit_case(case, plan, config, states, rows)
        self.assertGreater(len(rows[0]['radar']['points']), 0)
        self.assertEqual(result['echo_count'], 0)
        self.assertEqual(result['observed_fraction'], 0.)
        self.assertTrue(all(not any(row['supervision']['observed_mask']) for row in rows))

    def test_missed_vertical_obstacle_must_not_be_labeled_free(self):
        plan = matrix()
        case = next(item for item in plan['cases'] if item['case_id'] == 'vertical_no_echo')
        config, states, rows = build_case(case, plan, ROOT)
        damaged = copy.deepcopy(rows)
        damaged[0]['supervision']['target'][0] = 'free'
        damaged[0]['supervision']['observed_mask'][0] = True
        with self.assertRaises(ValueError):
            audit_case(case, plan, config, states, damaged)

    def test_ray_outside_declared_vertical_fov_is_rejected(self):
        plan = matrix()
        case = copy.deepcopy(next(item for item in plan['cases']
                                  if item['case_id'] == 'elevated_hit'))
        case['lidar_vertical_fov_deg'] = 6.0
        with self.assertRaisesRegex(ValueError, 'ray outside declared LiDAR FOV'):
            build_case(case, plan, ROOT)


if __name__ == '__main__':
    unittest.main()
