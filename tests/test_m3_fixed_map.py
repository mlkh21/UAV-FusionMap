"""Fixed synthetic interval accumulation, atomic rejection and saved-expectation checks."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from m3_fixture import interval_quality, load_spec, observation, scenarios
from ufm_mapping.fixed_interval_probability_map import FixedIntervalProbabilityMap
from ufm_mapping.fixed_probability_map import FixedProbabilityMap
from ufm_mapping.m3_contract import validate_interval_quality, wire_probability
from ufm_ros_contract.perf01a_codec import from_ros_snapshot, to_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result


def wire(message):
    buffer = io.BytesIO()
    message.serialize(buffer)
    return type(message)().deserialize(buffer.getvalue())


class FixedM3Test(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()
        self.run_id = 'm3-fixed'

    def new_map(self, spec=None):
        return FixedIntervalProbabilityMap(spec or self.spec, self.run_id, 'sim:' + self.run_id)

    def row(self, index, kind='occupied', bounds='default', stamp=None):
        event = copy.deepcopy(scenarios(self.spec)['bounded_positive_then_free'][0])
        event.update(kind=kind, timestamp=(index + 1) * 10_000_000)
        if kind == 'free':
            event.update(probability='1/4', bounds=['1/5', '3/10'])
        elif kind in ('neutral', 'unobserved'):
            event.update(probability='1/2', bounds=['1/2', '1/2'] if kind == 'neutral' else None)
        elif kind in ('empty', 'unavailable', 'degraded'):
            event.update(probability=None, bounds=None)
        if bounds != 'default':
            event['bounds'] = bounds
        if stamp is not None:
            event['timestamp'] = stamp
        return observation(self.spec, self.run_id, index, event)

    def query(self, candidate, stamp, **changes):
        request = dict(map_id='m3-fixture', frame_id='odom', run_id=self.run_id,
            clock_id='sim:' + self.run_id, query_timestamp=stamp, point=[8.25, .25, .25],
            max_age_ns=999_000_000)
        request.update(changes)
        return candidate.query(**request)

    def state(self, candidate):
        return copy.deepcopy((candidate.snapshot(), candidate._log_odds, candidate._seen,
                              candidate._input_timestamp, candidate.origin))

    def test_mean_matches_m2_and_interval_matches_hand_calculation(self):
        candidate = self.new_map()
        baseline = FixedProbabilityMap(self.spec['arithmetic'], self.run_id, 'sim:' + self.run_id)
        for index, (kind, mean, interval) in enumerate((('occupied', .75, [.7, .8]),
                ('occupied', .9, [49/58, .9]), ('free', .75, [49/85, 27/34]))):
            row = self.row(index, kind)
            self.assertEqual(candidate.update(row), baseline.update(row))
            result = self.query(candidate, row['header']['timestamp'])
            self.assertEqual(result['probability'], self.query(baseline, row['header']['timestamp'])['probability'])
            self.assertAlmostEqual(result['probability'], mean, places=12)
            self.assertEqual(result['revision'], index + 1)
            self.assertEqual(result['uncertainty']['status'], 'available')
            for actual, expected in zip(result['uncertainty']['value'], interval):
                self.assertAlmostEqual(actual, expected, places=12)
            self.assertEqual(result['uncertainty']['source'], self.spec['interval_profile']['output_source'])
            self.assertIsNone(result['confidence'])

    def test_point_intervals_remain_points_through_both_clips(self):
        for kind, bound in (('occupied', '3/4'), ('free', '1/4')):
            candidate = self.new_map()
            for index in range(8):
                candidate.update(self.row(index, kind, bounds=[bound, bound]))
                result = self.query(candidate, (index + 1) * 10_000_000)
                self.assertEqual(result['uncertainty']['value'], [result['probability']] * 2)
                validate_interval_quality(result['probability'], result['uncertainty'], self.spec, output=True)

    def test_missing_contributor_latches_until_new_ttl_cycle(self):
        candidate = self.new_map()
        for index, bounds in enumerate(('default', None, 'default')):
            candidate.update(self.row(index, bounds=bounds))
            quality = self.query(candidate, (index + 1) * 10_000_000)['uncertainty']
            self.assertEqual(quality['status'], 'available' if index == 0 else 'unavailable')
            if index:
                self.assertIsNone(quality['value'])
                self.assertEqual(quality['source'], self.spec['interval_profile']['unavailable_source'])
        candidate.update(self.row(3, stamp=140_000_000))
        result = self.query(candidate, 140_000_000)
        self.assertAlmostEqual(result['probability'], .75)
        self.assertEqual(result['uncertainty']['status'], 'available')
        self.assertEqual(result['last_observed_timestamp'], 140_000_000)

    def test_cells_do_not_borrow_ranges_and_missing_history_is_not_restored(self):
        candidate = self.new_map()
        row = self.row(0, bounds=None)
        other = copy.deepcopy(row['voxels'][0])
        other.update(index=[50, 16, 8], uncertainty=interval_quality(self.spec, ['3/4', '3/4']))
        row['voxels'].append(other)
        candidate.update(row)
        candidate.update(self.row(1))
        self.assertEqual(self.query(candidate, 20_000_000)['uncertainty']['status'], 'unavailable')
        result = self.query(candidate, 20_000_000, point=[9.25, .25, .25])
        self.assertAlmostEqual(result['probability'], .75, places=12)
        self.assertEqual(result['uncertainty']['value'], [result['probability']] * 2)
        self.assertEqual(result['last_observed_timestamp'], 10_000_000)

    def test_no_evidence_and_reads_do_not_refresh_quality_revision_or_time(self):
        candidate = self.new_map()
        candidate.update(self.row(0))
        before = candidate.snapshot()
        for index, kind in enumerate(('neutral', 'unobserved', 'empty', 'unavailable', 'degraded'), 1):
            self.assertFalse(candidate.update(self.row(index, kind)))
            self.assertEqual(candidate.snapshot(), before)
        self.assertEqual(self.query(candidate, 110_000_000)['status'], 'occupied')
        stale = self.query(candidate, 110_000_001)
        self.assertEqual(stale['status'], 'stale')
        self.assertEqual(stale['last_observed_timestamp'], 10_000_000)
        self.assertEqual(stale['uncertainty'], before['cells'][0]['uncertainty'])
        self.assertEqual(candidate.snapshot(), before)
        empty = self.new_map()
        empty.update(self.row(0, 'empty'))
        self.assertEqual(self.query(empty, 10_000_000)['status'], 'unavailable')
        self.assertEqual(self.query(candidate, 60_000_000, point=[2.25, .25, .25])['status'], 'unknown')

    def test_bad_last_range_and_late_construction_failure_are_atomic(self):
        candidate = self.new_map()
        candidate.update(self.row(0))
        before = self.state(candidate)
        row = self.row(8)
        other = copy.deepcopy(row['voxels'][0])
        other['index'][0] += 1
        other['uncertainty']['unit'] = 'm2'
        row['voxels'].append(other)
        with self.assertRaises(ValueError):
            candidate.update(row)
        self.assertEqual(self.state(candidate), before)
        row['voxels'][1]['uncertainty']['unit'] = 'dimensionless'
        original = candidate._updated_cell
        calls = []

        def fail_second(*args):
            calls.append(1)
            if len(calls) == 2:
                raise ValueError('injected second-cell construction failure')
            return original(*args)

        with patch.object(candidate, '_updated_cell', side_effect=fail_second), self.assertRaises(ValueError):
            candidate.update(row)
        self.assertEqual(self.state(candidate), before)
        self.assertTrue(candidate.update(self.row(1)))
        self.assertEqual(self.query(candidate, 20_000_000)['revision'], 2)

    def test_duplicate_conflict_and_late_messages_cannot_change_range(self):
        candidate = self.new_map()
        first = self.row(0)
        candidate.update(first)
        before = self.state(candidate)
        self.assertFalse(candidate.update(copy.deepcopy(first)))
        self.assertEqual(self.state(candidate), before)
        for change in ('range', 'same_time'):
            row = copy.deepcopy(first)
            if change == 'range':
                row['voxels'][0]['uncertainty']['value'][0] = .6
            else:
                row['header']['sample_id'] += ':other'
            with self.assertRaises(ValueError):
                candidate.update(row)
            self.assertEqual(self.state(candidate), before)
        candidate.update(self.row(2, 'unavailable'))
        with self.assertRaises(ValueError):
            candidate.update(self.row(1))

    def test_source_profile_run_and_geometry_errors_do_not_fallback(self):
        candidate = self.new_map()
        before = self.state(candidate)
        for group, key, value in (('header', 'source_type', 'model'), ('header', 'run_id', 'other'),
                ('header', 'clock_id', 'other'), ('context', 'calibration_id', 'real-device'),
                (None, 'observed_domain_source', 'fixture_radar_point'),
                (None, 'origin', [-15.5, -8., -4.])):
            row = self.row(0)
            (row if group is None else row[group])[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                candidate.update(row)
            self.assertEqual(self.state(candidate), before)
        row = self.row(0)
        row['voxels'][0]['uncertainty']['source'] = self.spec['interval_profile']['output_source']
        with self.assertRaises(ValueError):
            candidate.update(row)
        self.assertEqual(self.state(candidate), before)

    def test_capacity_evicts_nominal_and_range_together_and_new_instance_is_empty(self):
        spec = copy.deepcopy(self.spec)
        spec['arithmetic'].update(max_active_cells=1, identity_history_limit=2)
        candidate = self.new_map(spec)
        candidate.update(self.row(0))
        second = self.row(1)
        second['voxels'][0]['index'] = [50, 16, 8]
        candidate.update(second)
        self.assertEqual(len(candidate.snapshot()['cells']), 1)
        self.assertEqual(len(candidate._log_odds), 1)
        self.assertFalse(self.query(candidate, 20_000_000)['observed'])
        candidate.update(self.row(2))
        self.assertAlmostEqual(self.query(candidate, 30_000_000)['probability'], .75)
        self.assertEqual(candidate.retained_identity_count, 2)
        fresh = FixedIntervalProbabilityMap(self.spec, 'fresh', 'sim:fresh')
        self.assertEqual((fresh.snapshot()['revision'], fresh.snapshot()['cells']), (0, []))

    def test_public_snapshot_query_wire_rounding_and_copies_do_not_leak_internal_state(self):
        candidate = self.new_map()
        candidate.update(self.row(0, bounds=['3/4', '3/4']))
        candidate.update(self.row(1, bounds=['3/4', '3/4']))
        result = self.query(candidate, 20_000_000)
        decoded = from_ros_query_result(wire(to_ros_query_result(result)))
        validate_interval_quality(decoded['probability'], decoded['uncertainty'], self.spec,
                                  output=True, wire=True)
        self.assertEqual(decoded['probability'], wire_probability(result['probability']))
        snapshot = from_ros_snapshot(wire(to_ros_snapshot(candidate.snapshot())))
        self.assertEqual(snapshot['cells'][0]['uncertainty'], result['uncertainty'])
        self.assertEqual(set(snapshot['cells'][0]), {'index', 'probability', 'observed',
            'last_observed_timestamp', 'confidence', 'uncertainty'})
        result['uncertainty']['value'][0] = .1
        self.assertNotEqual(self.query(candidate, 20_000_000)['uncertainty']['value'][0], .1)

    def test_candidate_remains_explicit_and_requires_valid_configuration_and_identity(self):
        for identity in (('', 'sim:r'), ('r', '')):
            with self.assertRaises(ValueError):
                FixedIntervalProbabilityMap(self.spec, *identity)
        bad = copy.deepcopy(self.spec)
        bad['enabled_by_default'] = True
        with self.assertRaises(ValueError):
            self.new_map(bad)
        code = "from ufm_mapping.factory import create_map; import sys; create_map(); assert 'ufm_mapping.fixed_interval_probability_map' not in sys.modules; from ufm_mapping.fixed_interval_probability_map import FixedIntervalProbabilityMap; assert not any(k.split('.')[0] in ('torch','numpy','diffusion_consistency_radar') for k in sys.modules)"
        subprocess.run([sys.executable, '-B', '-c', code], check=True, timeout=10)

    def test_saved_expectation_runner_refuses_tampering_and_never_imports_oracle(self):
        import m3_fixed_run
        row = self.row(0)
        reference = dict(probability=.75, interval=[.7, .8], quality_available=True, observed=True,
                         last_observed_timestamp=10_000_000, revision=1, status='occupied')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'config.json').write_text(json.dumps(self.spec))
            for tamper in (None, 'range', 'shape'):
                expected = copy.deepcopy(reference)
                if tamper == 'range':
                    expected['interval'][0] = .6
                elif tamper == 'shape':
                    expected['interval'].append(.9)
                source = root / 'fixtures.json'
                source.write_text(json.dumps([dict(name='saved', observations=[row], expectations=[expected])]))
                output = io.StringIO()
                with patch.dict(sys.modules, {'m3_oracle': None}), redirect_stdout(output):
                    status = m3_fixed_run.main(['--input', str(source), '--output-root', str(root)])
                result = json.loads(output.getvalue())
                self.assertEqual(status, 0 if tamper is None else 1)
                self.assertEqual(result['passed'], tamper is None)
                report = json.loads((Path(result['run']) / 'report.json').read_text())
                self.assertTrue(report['map_accumulation_executed'])


if __name__ == '__main__':
    unittest.main()
