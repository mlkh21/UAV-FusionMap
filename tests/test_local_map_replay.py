"""Replay acceptance uses exact identities and public map outputs only."""
import copy
import unittest

from test_local_map_rolling import observed
from ufm_mapping.replay import equivalent, replay_observations


class ReplayTest(unittest.TestCase):
    def settings(self):
        return dict(rolling_enabled=True, free_threshold=.3, occupied_threshold=.7)

    def test_preserves_order_and_does_not_refuse_duplicate_as_new_evidence(self):
        first = observed(100)
        gap = observed(120, visible=False)
        gap['header'].update(status='unavailable', reason='fixture_gap')
        rows = [first, copy.deepcopy(first), gap, observed(110), observed(130)]
        result = replay_observations(rows, 'rolling', self.settings())
        self.assertEqual([row['outcome'] for row in result['steps']],
                         ['fused', 'not_fused', 'not_fused', 'rejected', 'fused'])
        self.assertEqual([row['revision'] for row in result['steps']], [1, 1, 1, 1, 2])
        self.assertEqual(result['steps'][2]['timestamp'], 100)
        self.assertEqual(result, replay_observations(rows, 'rolling', self.settings()))

    def test_roll_turn_eviction_and_new_run_have_fresh_map_instances(self):
        rows = [observed(100), observed(110, body=(.5, 0., 0.), yaw=1.5707963267948966),
                observed(120, body=(40., 0., 0.), visible=False)]
        replay = replay_observations(rows, 'rolling', self.settings())
        self.assertEqual(len(replay['snapshots']), 3)
        self.assertEqual(len(replay['snapshots'][1]['cells']), 1)
        self.assertEqual(replay['final_snapshot']['origin'][0], 24.)
        self.assertEqual(replay['final_snapshot']['cells'], [])
        foreign = copy.deepcopy(rows[0])
        foreign['header']['run_id'] = 'new-run'
        foreign['header']['clock_id'] = 'sim:new-run'
        foreign['context']['clock_id'] = 'sim:new-run'
        mixed = replay_observations([rows[0], foreign], 'rolling', self.settings())
        self.assertEqual(mixed['steps'][1]['outcome'], 'rejected')
        fresh = replay_observations([foreign], 'new-run', self.settings())
        self.assertEqual(fresh['final_snapshot']['revision'], 1)
        self.assertEqual(fresh['final_snapshot']['header']['run_id'], 'new-run')

    def test_query_replays_recorded_revision_and_gap_age_without_refresh(self):
        request = dict(map_id='perf01a-local', frame_id='odom', run_id='rolling',
                       clock_id='sim:rolling', query_timestamp=201, point=[2.25, .25, .25],
                       max_age_ns=100)
        query = dict(request=request, result=dict(revision=1))
        result = replay_observations([observed(100), observed(210, body=(1., 0., 0.))],
                                     'rolling', self.settings(), [query])
        self.assertEqual(result['queries'][0]['result']['status'], 'stale')
        self.assertEqual(result['queries'][0]['result']['last_observed_timestamp'], 100)
        self.assertEqual(result['final_snapshot']['revision'], 2)
        with self.assertRaises(ValueError):
            replay_observations([observed(100)], 'rolling', self.settings(),
                                [dict(request=request, result=dict(revision=5))])

    def test_wire_float_tolerance_does_not_mask_identity_or_timestamp_changes(self):
        self.assertTrue(equivalent(.9, .8999999761581421))
        self.assertFalse(equivalent(100, 101))
        self.assertFalse(equivalent(100, 100.0))
        self.assertFalse(equivalent(dict(run_id='a'), dict(run_id='b')))
        self.assertFalse(equivalent(float('nan'), float('nan')))


if __name__ == '__main__':
    unittest.main()
