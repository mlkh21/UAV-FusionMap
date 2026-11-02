"""M2-SW-03 H-K: event time, rolling evidence preservation and bounded state."""
import math
import unittest

from m2_fixture import load_spec
from m2_motion_fixture import motion_observation
from ufm_mapping.rolling_probability_map import RollingProbabilityMap


class RollingM2Test(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()
        self.run_id = 'm2-rolling'

    def new_map(self, **changes):
        return RollingProbabilityMap(dict(self.spec, **changes), self.run_id, 'sim:' + self.run_id)

    def row(self, sequence, **kwargs):
        return motion_observation(self.spec, self.run_id, sequence, **kwargs)

    def query(self, local_map, stamp, point=(8.25, .25, .25), max_age_ns=100_000_000):
        return local_map.query(map_id=self.spec['map_id'], frame_id='odom', run_id=self.run_id,
            clock_id='sim:' + self.run_id, query_timestamp=stamp, point=point, max_age_ns=max_age_ns)

    def test_positive_negative_and_half_cell_shifts_preserve_evidence(self):
        for body, expected, index in (((.24, 0., 0.), [-16., -8., -4.], [48, 16, 8]),
                ((.26, 0., 0.), [-15.5, -8., -4.], [47, 16, 8]),
                ((-.26, 0., 0.), [-16.5, -8., -4.], [49, 16, 8]),
                ((.25, -.25, 0.), [-15.5, -8., -4.], [47, 16, 8])):
            local_map = self.new_map()
            local_map.update(self.row(0))
            local_map.update(self.row(1, kind='empty', body=body))
            result = self.query(local_map, 20_000_000)
            with self.subTest(body=body):
                self.assertEqual(local_map.snapshot()['origin'], expected)
                self.assertEqual(result['index'], index)
                self.assertEqual(result['last_observed_timestamp'], 10_000_000)
                self.assertAlmostEqual(result['probability'], .75)

    def test_turn_and_shift_accumulate_same_world_cell(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        local_map.update(self.row(1, body=(.5, 0., 0.), yaw=math.pi / 2,
                                  origin=(-15., -8., -4.)))
        result = self.query(local_map, 20_000_000)
        self.assertEqual(result['index'], [47, 16, 8])
        self.assertAlmostEqual(result['probability'], .9)
        self.assertEqual(local_map.snapshot()['origin'], [-15.5, -8., -4.])

    def test_large_move_evicts_log_odds_and_new_regions_stay_unknown(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        local_map.update(self.row(1))
        local_map.update(self.row(2, kind='empty', body=(40., 0., 0.), origin=(24., -8., -4.)))
        self.assertEqual(local_map.snapshot()['origin'], [24., -8., -4.])
        self.assertEqual(local_map.snapshot()['cells'], [])
        self.assertEqual(self.query(local_map, 30_000_000, point=(40.25, .25, .25))['status'], 'unknown')
        local_map.update(self.row(3, kind='empty'))
        self.assertFalse(self.query(local_map, 40_000_000)['observed'])
        local_map.update(self.row(4))
        self.assertAlmostEqual(self.query(local_map, 50_000_000)['probability'], .75)

    def test_empty_window_change_does_not_refresh_or_answer_past_geometry(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        local_map.update(self.row(1, kind='empty', body=(.5, 0., 0.), stamp=200_000_000))
        snapshot = local_map.snapshot()
        self.assertEqual(snapshot['revision'], 2)
        self.assertEqual(snapshot['header']['timestamp'], 10_000_000)
        stale = self.query(local_map, 200_000_000)
        self.assertEqual(stale['status'], 'stale')
        past = self.query(local_map, 100_000_000)
        self.assertEqual(past['status'], 'unavailable')
        self.assertIsNone(past['probability'])
        self.assertFalse(past['observed'])
        self.assertEqual(snapshot, local_map.snapshot())

    def test_no_evidence_first_move_is_still_unavailable(self):
        local_map = self.new_map()
        local_map.update(self.row(0, kind='empty', body=(.5, 0., 0.)))
        self.assertEqual(local_map.snapshot()['header']['status'], 'unavailable')
        self.assertEqual(local_map.snapshot()['header']['timestamp'], 0)
        self.assertEqual(self.query(local_map, 10_000_000)['status'], 'unavailable')

    def test_unavailable_transform_does_not_move_window_but_consumes_time(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        before = local_map.snapshot()
        gap = self.row(2, kind='unavailable', body=(40., 0., 0.), origin=(24., -8., -4.))
        gap['context']['T_mapping_body_status'] = 'unavailable'
        gap['context']['T_mapping_body'] = [0.] * 16
        self.assertFalse(local_map.update(gap))
        self.assertEqual(before, local_map.snapshot())
        with self.assertRaises(ValueError):
            local_map.update(self.row(1))
        local_map.update(self.row(3))
        self.assertAlmostEqual(self.query(local_map, 40_000_000)['probability'], .9)

    def test_bad_geometry_and_last_voxel_leave_all_state_unchanged(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        before = local_map.snapshot()
        for key, value in (('T_mapping_body', [-1., 0, 0, 0, 0, 1., 0, 0, 0, 0, 1., 0, 0, 0, 0, 1.]),
                           ('T_mapping_body', [float('nan')] * 16)):
            bad = self.row(3, body=(.5, 0., 0.))
            bad['context'][key] = value
            with self.assertRaises(ValueError):
                local_map.update(bad)
            self.assertEqual(before, local_map.snapshot())
        bad = self.row(3, body=(.5, 0., 0.), origin=(-15.5, -8., -4.))
        bad['voxels'].append(dict(bad['voxels'][0], index=[999, 0, 0]))
        with self.assertRaises(ValueError):
            local_map.update(bad)
        bad = self.row(3, body=(.5, 0., 0.))
        bad['origin'][0] += .1
        with self.assertRaises(ValueError):
            local_map.update(bad)
        self.assertEqual(before, local_map.snapshot())
        self.assertTrue(local_map.update(self.row(1, body=(.5, 0., 0.))))

    def test_ttl_boundary_after_shift_and_neutral_does_not_restart(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        local_map.update(self.row(1))
        local_map.update(self.row(2, kind='neutral', body=(.5, 0., 0.), stamp=120_000_000))
        self.assertEqual(self.query(local_map, 120_000_000)['status'], 'occupied')
        self.assertEqual(self.query(local_map, 120_000_001, max_age_ns=999_000_000)['status'], 'stale')
        local_map.update(self.row(3, body=(.5, 0., 0.), stamp=130_000_000))
        self.assertAlmostEqual(self.query(local_map, 130_000_000)['probability'], .75)
        self.assertEqual(self.query(local_map, 130_000_001, max_age_ns=0)['status'], 'stale')

    def test_bounded_identity_old_time_conflict_and_long_sequence(self):
        local_map = self.new_map(identity_history_limit=3, max_active_cells=2)
        old = self.row(0)
        for sequence in range(40):
            point = (8.25 + sequence % 3, .25, .25)
            local_map.update(self.row(sequence, points=(point,)))
            self.assertLessEqual(local_map.retained_identity_count, 3)
            self.assertLessEqual(len(local_map.snapshot()['cells']), 2)
            self.assertLessEqual(len(local_map._log_odds), 2)
        before = local_map.snapshot()
        with self.assertRaises(ValueError):
            local_map.update(old)
        recent = self.row(39, points=((8.25, .25, .25),))
        self.assertFalse(local_map.update(recent))
        recent['voxels'][0]['probability'] = .25
        with self.assertRaises(ValueError):
            local_map.update(recent)
        self.assertEqual(before, local_map.snapshot())

    def test_nonuniform_resolution_and_three_axis_half_cell_boundaries(self):
        spec = dict(self.spec, resolution=[1., .5, 2.], shape=[4, 4, 4],
                    origin=[-2., -1., -4.], cell_index=[3, 2, 2])
        local_map = RollingProbabilityMap(spec, self.run_id, 'sim:' + self.run_id)
        point = (1.5, .25, 1.)
        first = motion_observation(spec, self.run_id, 0, points=(point,))
        local_map.update(first)
        local_map.update(motion_observation(spec, self.run_id, 1, kind='empty',
                                           body=(.5, -.25, 1.)))
        result = self.query(local_map, 20_000_000, point=point)
        self.assertEqual(local_map.snapshot()['origin'], [-1., -1., -2.])
        self.assertEqual(result['index'], [2, 2, 1])
        self.assertAlmostEqual(result['probability'], .75)
        self.assertEqual(result['last_observed_timestamp'], 10_000_000)

    def test_observation_outside_new_window_does_not_create_evidence(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        local_map.update(self.row(1, body=(40., 0., 0.)))
        self.assertEqual(local_map.snapshot()['cells'], [])
        self.assertEqual(local_map._log_odds, {})
        self.assertEqual(local_map.snapshot()['header']['timestamp'], 10_000_000)
        self.assertEqual(self.query(local_map, 20_000_000, point=(40.25, .25, .25))['status'], 'unknown')

    def test_tied_capacity_eviction_is_deterministic(self):
        left, right = self.new_map(max_active_cells=2), self.new_map(max_active_cells=2)
        row = self.row(0, points=((8.25, .25, .25), (9.25, .25, .25), (10.25, .25, .25)))
        left.update(row)
        row['voxels'].reverse()
        right.update(row)
        self.assertEqual(left.snapshot(), right.snapshot())
        self.assertEqual([cell['index'][0] for cell in left.snapshot()['cells']], [48, 50])

    def test_foreign_run_or_clock_does_not_reset_and_new_instance_is_empty(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        before = local_map.snapshot()
        for key, value in (('run_id', 'new'), ('clock_id', 'foreign')):
            row = self.row(1)
            row['header'][key] = value
            if key == 'clock_id':
                row['context']['clock_id'] = value
            with self.assertRaises(ValueError):
                local_map.update(row)
            self.assertEqual(before, local_map.snapshot())
        fresh = RollingProbabilityMap(self.spec, 'new', 'sim:new')
        self.assertEqual(fresh.snapshot()['revision'], 0)
        self.assertEqual(fresh.snapshot()['cells'], [])


if __name__ == '__main__':
    unittest.main()
