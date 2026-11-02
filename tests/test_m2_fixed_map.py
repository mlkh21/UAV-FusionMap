"""Fixed M2 candidate versus the previous work package's independent odds oracle."""
import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from m2_fixture import SCENARIOS, load_spec, observation
from m2_oracle import expected_sequence
from ufm_mapping.fixed_probability_map import FixedProbabilityMap
from ufm_mapping.local_map import SparseLocalMap
from ufm_ros_contract.perf01a_codec import from_ros_snapshot, to_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result


class FixedM2Test(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()
        self.run_id = 'm2-fixed'

    def new_map(self, spec=None):
        return FixedProbabilityMap(spec or self.spec, self.run_id, 'sim:' + self.run_id)

    def row(self, sequence, kind='occupied'):
        return observation(self.spec, self.run_id, sequence, kind)

    def query(self, local_map, stamp, **changes):
        request = dict(map_id=self.spec['map_id'], frame_id='odom', run_id=self.run_id,
            clock_id='sim:' + self.run_id, query_timestamp=stamp, max_age_ns=100_000_000,
            point=[self.spec['origin'][axis] + (self.spec['cell_index'][axis] + .5) *
                   self.spec['resolution'][axis] for axis in range(3)])
        request.update(changes)
        return local_map.query(**request)

    def test_all_nine_scenarios_match_independent_oracle(self):
        for name, kinds in SCENARIOS.items():
            local_map = self.new_map()
            expected = expected_sequence(kinds, self.spec)
            for index, (kind, reference) in enumerate(zip(kinds, expected)):
                row = self.row(index, kind)
                local_map.update(row)
                result = self.query(local_map, row['header']['timestamp'])
                with self.subTest(scenario=name, step=index):
                    self.assertEqual(result['observed'], reference['observed'])
                    self.assertEqual(result['last_observed_timestamp'], reference['last_observed_timestamp'])
                    if reference['probability'] is None:
                        self.assertIsNone(result['probability'])
                    else:
                        self.assertAlmostEqual(result['probability'], reference['probability'], places=12)
                        self.assertIsNone(result['confidence'])
                        self.assertEqual(result['uncertainty']['status'], 'unavailable')

    def test_five_query_states_and_quality_wire_compatibility(self):
        local_map = self.new_map()
        self.assertEqual(self.query(local_map, 0)['status'], 'unavailable')
        local_map.update(self.row(0))
        self.assertEqual(self.query(local_map, 10_000_000)['status'], 'occupied')
        self.assertEqual(self.query(local_map, 10_000_000, point=[0., 0., 0.])['status'], 'unknown')
        self.assertEqual(self.query(local_map, 10_000_000, point=[16., 0., 0.])['reason'], 'outside_coverage')
        self.assertEqual(self.query(local_map, 110_000_001, max_age_ns=999_000_000)['status'], 'stale')
        local_map.update(self.row(1, 'free'))
        conflict = self.query(local_map, 20_000_000)
        self.assertEqual(conflict['status'], 'unknown')
        self.assertTrue(conflict['observed'])
        local_map.update(self.row(2, 'free'))
        free = self.query(local_map, 30_000_000)
        self.assertEqual(free['status'], 'free')
        decoded = from_ros_query_result(to_ros_query_result(free))
        self.assertAlmostEqual(decoded['probability'], free['probability'], places=6)
        snapshot = local_map.snapshot()
        self.assertEqual(snapshot['source_types'], ['fixture'])
        self.assertNotIn('log_odds', snapshot['cells'][0])
        self.assertEqual(from_ros_snapshot(to_ros_snapshot(snapshot))['revision'], snapshot['revision'])

    def test_duplicate_conflict_and_old_time_do_not_accumulate(self):
        local_map = self.new_map()
        row = self.row(0)
        local_map.update(row)
        before = local_map.snapshot()
        self.assertFalse(local_map.update(copy.deepcopy(row)))
        self.assertEqual(before, local_map.snapshot())
        changed = copy.deepcopy(row)
        changed['voxels'][0]['probability'] = .25
        with self.assertRaises(ValueError):
            local_map.update(changed)
        changed = copy.deepcopy(row)
        changed['header']['timestamp'] = 15_000_000
        changed['context']['reference_timestamp'] = 15_000_000
        with self.assertRaises(ValueError):
            local_map.update(changed)
        newer = self.row(1)
        local_map.update(newer)
        same_time = self.row(1)
        same_time['header']['sample_id'] += ':other-id'
        before = local_map.snapshot()
        with self.assertRaises(ValueError):
            local_map.update(same_time)
        self.assertFalse(local_map.update(row))
        self.assertEqual(before, local_map.snapshot())

    def test_invalid_last_voxel_is_atomic_and_next_frame_recovers(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        before = local_map.snapshot()
        for change in (dict(probability=float('nan')), dict(index=[64, 0, 0]),
                       dict(confidence=float('inf'))):
            row = self.row(2)
            second = copy.deepcopy(row['voxels'][0])
            second['index'] = [49, 16, 8]
            second.update(change)
            row['voxels'].append(second)
            with self.subTest(change=change), self.assertRaises(ValueError):
                local_map.update(row)
            self.assertEqual(local_map.snapshot(), before)
        self.assertTrue(local_map.update(self.row(1)))
        self.assertAlmostEqual(self.query(local_map, 20_000_000)['probability'], .9)

    def test_source_run_clock_geometry_and_duplicate_indices_are_rejected(self):
        local_map = self.new_map()
        base = self.row(0)
        changes = [('header', 'source_type', 'model'), ('header', 'run_id', 'foreign'),
            ('header', 'clock_id', 'foreign'), ('context', 'calibration_id', 'other'),
            ('context', 'T_mapping_body', [-1., 0, 0, 0, 0, 1., 0, 0, 0, 0, 1., 0, 0, 0, 0, 1.]),
            (None, 'observed_domain_source', 'fixture_radar_point'),
            (None, 'resolution', [1., 1., 1.])]
        before = local_map.snapshot()
        for group, key, value in changes:
            row = copy.deepcopy(base)
            (row[group] if group else row)[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                local_map.update(row)
            self.assertEqual(local_map.snapshot(), before)
        duplicate = copy.deepcopy(base)
        duplicate['voxels'].append(copy.deepcopy(duplicate['voxels'][0]))
        with self.assertRaises(ValueError):
            local_map.update(duplicate)
        self.assertTrue(local_map.update(base))

    def test_no_evidence_advances_input_watermark_without_refresh(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        before = local_map.snapshot()
        for index, kind in enumerate(('neutral', 'unobserved', 'empty', 'no_return',
                                      'unavailable', 'degraded'), 1):
            self.assertFalse(local_map.update(self.row(index, kind)))
            self.assertEqual(before, local_map.snapshot())
        late = self.row(2)
        late['header']['sample_id'] += ':late'
        with self.assertRaises(ValueError):
            local_map.update(late)
        self.assertTrue(local_map.update(self.row(7)))

    def test_expired_cell_restarts_from_prior_and_reads_do_not_mutate(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        local_map.update(self.row(1))
        before = local_map.snapshot()
        self.assertEqual(self.query(local_map, 120_000_000)['status'], 'occupied')
        self.assertEqual(self.query(local_map, 120_000_001)['status'], 'stale')
        self.assertEqual(before, local_map.snapshot())
        local_map.update(self.row(20))
        self.assertAlmostEqual(self.query(local_map, 210_000_000)['probability'], .75)

    def test_state_limits_and_input_copy_are_explicit(self):
        spec = dict(self.spec, max_active_cells=2, identity_history_limit=2)
        local_map = self.new_map(spec)
        for sequence in range(4):
            row = self.row(sequence)
            row['voxels'][0]['index'][0] += sequence
            self.assertTrue(local_map.update(row))
            row['voxels'][0]['probability'] = .25
        self.assertLessEqual(len(local_map.snapshot()['cells']), 2)
        self.assertTrue(all(abs(cell['probability'] - .75) < 1e-12
                            for cell in local_map.snapshot()['cells']))
        self.assertEqual(local_map.retained_identity_count, 2)
        stale = self.row(0)
        stale['header']['sample_id'] += ':renamed'
        with self.assertRaises(ValueError):
            local_map.update(stale)

    def test_existing_m1_still_uses_latest_probability(self):
        local_map = SparseLocalMap(map_id=self.spec['map_id'])
        local_map.update(self.row(0))
        local_map.update(self.row(1))
        self.assertEqual(local_map.snapshot()['cells'][0]['probability'], .75)

    def test_shorter_client_age_and_identity_errors_preserve_map(self):
        local_map = self.new_map()
        local_map.update(self.row(0))
        before = local_map.snapshot()
        self.assertEqual(self.query(local_map, 10_000_001, max_age_ns=0)['status'], 'stale')
        for changes in (dict(map_id='other'), dict(frame_id='map'), dict(run_id='other'),
                        dict(clock_id='other'), dict(query_timestamp=9_999_999)):
            result = self.query(local_map, 10_000_000, **changes)
            self.assertEqual(result['status'], 'unavailable')
            self.assertIsNone(result['probability'])
        for change in (dict(max_age_ns=True), dict(max_age_ns=2**63),
                       dict(query_timestamp=2**63)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.query(local_map, 10_000_000, **change)
        self.assertEqual(before, local_map.snapshot())

    def test_input_quality_is_not_claimed_as_calibrated_fused_quality(self):
        local_map = self.new_map()
        row = self.row(0)
        row['voxels'][0].update(confidence=.8, uncertainty=dict(status='available',
            kind='occupancy_variance', value=[.125], unit='dimensionless', source='fixture input'))
        local_map.update(row)
        result = self.query(local_map, 10_000_000)
        self.assertIsNone(result['confidence'])
        self.assertEqual(result['uncertainty']['status'], 'unavailable')
        self.assertIsNone(result['uncertainty']['value'])

    def test_runner_refuses_tampered_saved_expectation(self):
        import m2_fixed_run as runner
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'config.json').write_text(json.dumps(self.spec))
            expected = expected_sequence(('occupied',), self.spec)
            expected[0]['probability'] = .8
            source = root / 'fixtures.json'
            source.write_text(json.dumps([dict(name='tampered', steps=['occupied'],
                                               observations=[self.row(0)], expectations=expected)]))
            with patch.object(runner, '__file__', str(root / 'tests/m2_fixed_run.py')), \
                    patch.object(runner.sys, 'argv', ['m2_fixed_run.py', '--input', str(source)]), \
                    redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            report_path = next((root / '.runtime/runs').glob('*/report.json'))
            report = json.loads(report_path.read_text())
            self.assertFalse(report['passed'])
            self.assertTrue(any('saved rational oracle' in error for error in report['errors']))


if __name__ == '__main__':
    unittest.main()
