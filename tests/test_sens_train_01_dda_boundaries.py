"""Finite-grid boundary contract for the training-only ray coverage traversal."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
for directory in ('sensors', 'tests'):
    sys.path.insert(0, str(ROOT / directory))

from sens_train_01_scene_suite import _positive_length_voxel_cells
from ufm_sensors.training_supervision import _segment_voxel_indices


def _flatten(indices, shape):
    return {(x * shape[1] + y) * shape[2] + z for x, y, z in indices}


class TrainingVoxelBoundaryTest(unittest.TestCase):
    def test_fixed_segments_match_independent_aabb_oracle_and_expected_cells(self):
        origin = [0., 0., 0.]
        resolution = [1., 1., 1.]
        shape = [4, 4, 4]
        cases = (
            ('axis_positive', [.25, 1.5, 1.5], [3.75, 1.5, 1.5],
             [(x, 1, 1) for x in range(4)]),
            ('axis_negative', [3.75, 1.5, 1.5], [.25, 1.5, 1.5],
             [(x, 1, 1) for x in range(4)]),
            ('corner_positive', [.25, .25, .25], [3.75, 3.75, 3.75],
             [(x, x, x) for x in range(4)]),
            ('corner_negative', [3.75, 3.75, 3.75], [.25, .25, .25],
             [(x, x, x) for x in range(4)]),
            ('edge_positive', [.25, .25, 1.5], [3.75, 3.75, 1.5],
             [(x, x, 1) for x in range(4)]),
            ('face_parallel', [1., .25, 1.5], [1., 3.75, 1.5],
             [(1, y, 1) for y in range(4)]),
            ('edge_parallel', [.25, 1., 2.], [3.75, 1., 2.],
             [(x, 1, 2) for x in range(4)]),
            ('clipped_both_ends', [-2., 1.5, 1.5], [6., 1.5, 1.5],
             [(x, 1, 1) for x in range(4)]),
            ('clipped_reverse', [6., 1.5, 1.5], [-2., 1.5, 1.5],
             [(x, 1, 1) for x in range(4)]),
            ('starts_on_upper_face_inward', [4., 1.5, 1.5], [2.5, 1.5, 1.5],
             [(x, 1, 1) for x in (2, 3)]),
            ('ends_on_upper_face', [.25, 1.5, 1.5], [4., 1.5, 1.5],
             [(x, 1, 1) for x in range(4)]),
            ('endpoint_at_entry', [-1., 1.5, 1.5], [0., 1.5, 1.5], []),
            ('endpoint_at_exit', [4., 1.5, 1.5], [5., 1.5, 1.5], []),
            ('corner_tangent', [-1., 0., 1.], [1., 0., -1.], []),
            ('parallel_outside', [-.25, 1.5, 1.5], [-.25, 3., 1.5], []),
            ('zero_length_inside', [1.5, 1.5, 1.5], [1.5, 1.5, 1.5], []),
        )
        grid = dict(grid_origin_m=origin, grid_resolution_m=resolution, grid_shape=shape)
        for name, start, end, expected_indices in cases:
            with self.subTest(name=name):
                actual = set(_segment_voxel_indices(start, end, origin, resolution, shape))
                self.assertEqual(actual, _flatten(expected_indices, shape))
                self.assertEqual(actual, _positive_length_voxel_cells(start, end, grid))

    def test_nonuniform_grid_clipping_and_axis_order(self):
        origin = [-1., -2., -3.]
        resolution = [.5, 1., 2.]
        shape = [4, 3, 2]
        grid = dict(grid_origin_m=origin, grid_resolution_m=resolution, grid_shape=shape)
        cases = (
            ([-2., -.5, -2.], [2., -.5, -2.], [(x, 1, 0) for x in range(4)]),
            ([2., -.5, -2.], [-2., -.5, -2.], [(x, 1, 0) for x in range(4)]),
            ([-.75, -1.5, -2.], [.75, 1.5, 2.], None),
        )
        for start, end, expected_indices in cases:
            with self.subTest(start=start, end=end):
                actual = set(_segment_voxel_indices(start, end, origin, resolution, shape))
                if expected_indices is not None:
                    self.assertEqual(actual, _flatten(expected_indices, shape))
                self.assertEqual(actual, _positive_length_voxel_cells(start, end, grid))
                self.assertTrue(actual)
                self.assertTrue(all(0 <= cell < 24 for cell in actual))


if __name__ == '__main__':
    unittest.main()
