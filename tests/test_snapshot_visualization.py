"""Public view geometry, unknown/failure semantics and recorded domain isolation."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from ufm_application.visualization import SnapshotView, load_recording, validate_snapshot
from ufm_mapping.local_map import SparseLocalMap
from test_local_map_query import observation


class SnapshotVisualizationTest(unittest.TestCase):
    def setUp(self):
        local = SparseLocalMap(free_threshold=.3, occupied_threshold=.7)
        local.update(observation())
        self.snapshot = local.snapshot()
        self.stamp = self.snapshot['header']['timestamp']
        self.clock = self.snapshot['header']['clock_id']
        self.view = SnapshotView(100, .3, .7)

    def test_geometry_uses_origin_resolution_and_index_without_frame_guess(self):
        frame = self.view.frame(self.snapshot, self.stamp, self.clock)
        first = self.snapshot['cells'][0]
        self.assertEqual(frame['cells'][0]['center'], [self.snapshot['origin'][a] +
            (first['index'][a] + .5) * self.snapshot['resolution'][a] for a in range(3)])
        self.assertEqual(frame['header']['frame_id'], 'odom')
        self.assertEqual(frame['unlisted_space'], 'unknown')
        self.assertEqual(frame['counts']['free'], 0)

    def test_stale_exact_boundary_and_disconnected_never_free(self):
        for delta, connected, state in ((100, True, 'occupied'), (101, True, 'stale'),
                                       (0, False, 'unavailable')):
            frame = self.view.frame(self.snapshot, self.stamp + delta, self.clock, connected)
            self.assertEqual(frame['cells'][0]['state'], state)
        self.assertEqual(self.snapshot['cells'][0]['last_observed_timestamp'], self.stamp)

    def test_clock_mismatch_reset_missing_and_bad_status_are_unavailable(self):
        for stamp, clock in ((None, self.clock), (self.stamp, 'foreign'), (self.stamp - 1, self.clock)):
            self.assertEqual(self.view.frame(self.snapshot, stamp, clock)['cells'][0]['state'], 'unavailable')
        self.snapshot['header']['status'] = 'unavailable'
        self.assertFalse(self.view.frame(self.snapshot, self.stamp, self.clock)['available'])

    def test_free_requires_observed_fresh_explicit_thresholds(self):
        self.snapshot['cells'][0]['probability'] = .1
        self.assertEqual(self.view.frame(self.snapshot, self.stamp, self.clock)['cells'][0]['state'], 'free')
        self.snapshot['cells'][0]['observed'] = False
        self.assertEqual(self.view.frame(self.snapshot, self.stamp, self.clock)['cells'][0]['state'], 'unknown')
        self.assertEqual(SnapshotView(100).frame(self.snapshot, self.stamp, self.clock)['cells'][0]['state'], 'unknown')

    def test_bad_geometry_or_duplicate_cells_and_oversize_are_rejected(self):
        for changes in (dict(resolution=[0, .5, .5]), dict(coverage=[0] * 6),
                        dict(cells=self.snapshot['cells'] * 2), dict(shape=[True, 32, 16])):
            with self.assertRaises(ValueError):
                validate_snapshot(dict(self.snapshot, **changes))
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, cell_limit=0)

    def test_recording_rejects_domain_mix_nonincreasing_and_empty(self):
        for change in ('run_id', 'clock_id', 'frame_id'):
            later = copy.deepcopy(self.snapshot)
            later['revision'] += 1
            later['header'][change] = 'foreign'
            with self.assertRaises(ValueError):load_recording(dict(snapshots=[self.snapshot, later]))
        for rows in ([], [self.snapshot, self.snapshot]):
            with self.assertRaises(ValueError):load_recording(dict(snapshots=rows))
        self.assertEqual(load_recording(dict(snapshots=[self.snapshot])), [self.snapshot])

    def test_malformed_quality_and_probability_are_rejected_in_recordings(self):
        for changes in (dict(probability=float('nan')), dict(confidence=True),
                        dict(uncertainty=dict(status='unavailable', kind='', unit='', source='', value=[]))):
            snapshot = copy.deepcopy(self.snapshot)
            snapshot['cells'][0].update(changes)
            with self.assertRaises(ValueError):load_recording(dict(snapshots=[snapshot]))


if __name__ == '__main__':
    unittest.main()
