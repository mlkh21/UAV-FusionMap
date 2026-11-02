"""M3-SW-03: probability ranges and missing-quality state follow rolling cells."""
import copy
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from m3_fixture import interval_quality, load_spec
from m3_motion_fixture import motion_observation
from ufm_mapping.m3_contract import validate_interval_quality
from ufm_mapping.rolling_interval_probability_map import RollingIntervalProbabilityMap
from ufm_mapping.rolling_probability_map import RollingProbabilityMap
from ufm_ros_contract.perf01a_codec import from_ros_snapshot, to_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result


class RollingM3Test(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()
        self.run_id = 'm3-motion'

    def new_map(self, spec=None):
        return RollingIntervalProbabilityMap(spec or self.spec, self.run_id, 'sim:' + self.run_id)

    def row(self, index, **kwargs):
        return motion_observation(self.spec, self.run_id, index, **kwargs)

    def query(self, candidate, stamp, **changes):
        request = dict(map_id='m3-fixture', frame_id='odom', run_id=self.run_id,
            clock_id='sim:' + self.run_id, query_timestamp=stamp, point=[8.25, .25, .25],
            max_age_ns=999_000_000)
        request.update(changes)
        return candidate.query(**request)

    def state(self, candidate):
        return copy.deepcopy((candidate.snapshot(), candidate._log_odds, candidate._seen,
                              candidate._input_timestamp, candidate._geometry_timestamp, candidate.origin))

    def test_positive_negative_and_half_cell_shifts_preserve_range_and_private_state(self):
        for body, origin, index in (((.24, 0., 0.), [-16., -8., -4.], [48, 16, 8]),
                ((.26, 0., 0.), [-15.5, -8., -4.], [47, 16, 8]),
                ((-.26, 0., 0.), [-16.5, -8., -4.], [49, 16, 8]),
                ((.25, -.25, 0.), [-15.5, -8., -4.], [47, 16, 8])):
            candidate = self.new_map()
            candidate.update(self.row(0))
            old_quality = candidate.snapshot()['cells'][0]['uncertainty']
            old_state = next(iter(candidate._log_odds.values()))
            candidate.update(self.row(1, kind='empty', body=body))
            result = self.query(candidate, 20_000_000)
            with self.subTest(body=body):
                self.assertEqual(candidate.snapshot()['origin'], origin)
                self.assertEqual(result['index'], index)
                self.assertEqual(result['uncertainty'], old_quality)
                self.assertEqual(candidate._log_odds, {tuple(index): old_state})
                self.assertEqual(result['last_observed_timestamp'], 10_000_000)

    def test_turn_and_different_observation_origin_match_m2_nominal_and_hand_range(self):
        candidate = self.new_map()
        baseline = RollingProbabilityMap(self.spec['arithmetic'], self.run_id, 'sim:' + self.run_id)
        for row in (self.row(0), self.row(1, body=(.5, 0., 0.), yaw=math.pi/2, origin=(-15., -8., -4.))):
            candidate.update(row)
            baseline.update(row)
        result = self.query(candidate, 20_000_000)
        self.assertEqual(result['probability'], self.query(baseline, 20_000_000)['probability'])
        self.assertEqual(result['index'], [47, 16, 8])
        for actual, expected in zip(result['uncertainty']['value'], [49/58, .9]):
            self.assertAlmostEqual(actual, expected, places=12)

    def test_missing_quality_survives_shifts_known_input_and_ttl_boundary(self):
        candidate = self.new_map()
        candidate.update(self.row(0))
        candidate.update(self.row(1, bounds=None, body=(.5, 0., 0.)))
        candidate.update(self.row(2, body=(-.5, 0., 0.)))
        candidate.update(self.row(3, kind='neutral', body=(.5, 0., 0.), stamp=130_000_000))
        self.assertEqual(self.query(candidate, 130_000_000)['status'], 'occupied')
        self.assertEqual(self.query(candidate, 130_000_000)['uncertainty']['status'], 'unavailable')
        stale = self.query(candidate, 130_000_001)
        self.assertEqual(stale['status'], 'stale')
        self.assertEqual(stale['last_observed_timestamp'], 30_000_000)
        candidate.update(self.row(4, body=(.5, 0., 0.), stamp=140_000_000))
        result = self.query(candidate, 140_000_000)
        self.assertAlmostEqual(result['probability'], .75)
        self.assertEqual(result['uncertainty']['status'], 'available')
        self.assertEqual(self.query(candidate, 140_000_001, max_age_ns=0)['status'], 'stale')

    def test_far_move_removes_known_and_missing_states_and_return_starts_fresh(self):
        candidate = self.new_map()
        row = self.row(0, bounds=None, points=((8.25, .25, .25), (9.25, .25, .25)))
        row['voxels'][1]['uncertainty'] = interval_quality(self.spec, ['7/10', '4/5'])
        candidate.update(row)
        candidate.update(self.row(1))
        candidate.update(self.row(2, kind='empty', body=(40., 0., 0.), origin=(24., -8., -4.)))
        self.assertEqual(candidate.snapshot()['cells'], [])
        self.assertEqual(candidate._log_odds, {})
        self.assertEqual(self.query(candidate, 30_000_000, point=[40.25, .25, .25])['status'], 'unknown')
        candidate.update(self.row(3, kind='empty'))
        self.assertFalse(self.query(candidate, 40_000_000)['observed'])
        candidate.update(self.row(4))
        result = self.query(candidate, 50_000_000)
        self.assertAlmostEqual(result['probability'], .75)
        self.assertEqual(result['uncertainty']['status'], 'available')
        self.assertFalse(self.query(candidate, 50_000_000, point=[9.25, .25, .25])['observed'])

    def test_empty_move_preserves_evidence_time_and_past_geometry_leaks_no_range(self):
        candidate = self.new_map()
        candidate.update(self.row(0))
        old_quality = candidate.snapshot()['cells'][0]['uncertainty']
        candidate.update(self.row(1, kind='empty', body=(.5, 0., 0.), stamp=200_000_000))
        snapshot = candidate.snapshot()
        self.assertEqual((snapshot['revision'], snapshot['header']['timestamp']), (2, 10_000_000))
        result = self.query(candidate, 100_000_000)
        self.assertEqual((result['status'], result['probability'], result['uncertainty']),
                         ('unavailable', None, None))
        self.assertEqual(self.query(candidate, 200_000_000)['uncertainty'], old_quality)
        self.assertEqual(self.query(candidate, 200_000_000)['status'], 'stale')
        self.assertEqual(candidate.snapshot(), snapshot)
        empty = self.new_map()
        empty.update(self.row(0, kind='empty', body=(.5, 0., 0.)))
        self.assertEqual(empty.snapshot()['header']['timestamp'], 0)
        self.assertEqual(self.query(empty, 10_000_000)['status'], 'unavailable')

    def test_nonvalid_frames_do_not_move_or_refresh_and_keep_event_watermark(self):
        for kind in ('unavailable', 'degraded'):
            candidate = self.new_map()
            candidate.update(self.row(0))
            before = candidate.snapshot()
            row = self.row(2, kind=kind, body=(40., 0., 0.), origin=(24., -8., -4.))
            row['context']['T_mapping_body_status'] = 'unavailable'
            row['context']['T_mapping_body'] = [0.] * 16
            self.assertFalse(candidate.update(row))
            self.assertEqual(candidate.snapshot(), before)
            with self.assertRaises(ValueError):
                candidate.update(self.row(1))
            self.assertTrue(candidate.update(self.row(3, body=(.5, 0., 0.))))
            self.assertEqual(self.query(candidate, 40_000_000)['uncertainty']['status'], 'available')

    def test_invalid_geometry_and_last_range_cannot_partially_move_state(self):
        candidate = self.new_map()
        candidate.update(self.row(0))
        before = self.state(candidate)
        for fault in ('reflection', 'nan', 'lattice', 'range'):
            row = self.row(8, body=(.5, 0., 0.), points=((8.25, .25, .25), (9.25, .25, .25)))
            if fault == 'reflection':
                row['context']['T_mapping_body'][0] = -1.
            elif fault == 'nan':
                row['context']['T_mapping_body'][3] = float('nan')
            elif fault == 'lattice':
                row['origin'][0] += .1
            else:
                row['voxels'][-1]['uncertainty']['unit'] = 'm2'
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                candidate.update(row)
            self.assertEqual(self.state(candidate), before)
        self.assertTrue(candidate.update(self.row(1, body=(.5, 0., 0.))))

    def test_second_cell_construction_error_after_staged_shift_is_atomic(self):
        candidate = self.new_map()
        candidate.update(self.row(0))
        before = self.state(candidate)
        row = self.row(8, body=(.5, 0., 0.), points=((8.25, .25, .25), (9.25, .25, .25)))
        original, calls = candidate._updated_cell, []

        def fail_second(*args):
            calls.append(1)
            if len(calls) == 2:
                raise ValueError('injected construction failure after staged window shift')
            return original(*args)

        with patch.object(candidate, '_updated_cell', side_effect=fail_second), self.assertRaises(ValueError):
            candidate.update(row)
        self.assertEqual(self.state(candidate), before)
        self.assertTrue(candidate.update(self.row(1, body=(.5, 0., 0.))))

    def test_nonuniform_resolution_and_three_axis_half_cell_motion(self):
        spec = copy.deepcopy(self.spec)
        spec['arithmetic'].update(resolution=[1., .5, 2.], shape=[4, 4, 4],
                                  origin=[-2., -1., -4.], cell_index=[3, 2, 2])
        candidate = self.new_map(spec)
        point = (1.5, .25, 1.)
        candidate.update(motion_observation(spec, self.run_id, 0, points=(point,)))
        candidate.update(motion_observation(spec, self.run_id, 1, kind='empty',
                                           body=(.5, -.25, 1.), points=(point,)))
        result = self.query(candidate, 20_000_000, point=point)
        self.assertEqual(candidate.snapshot()['origin'], [-1., -1., -2.])
        self.assertEqual(result['index'], [2, 2, 1])
        self.assertEqual(result['last_observed_timestamp'], 10_000_000)
        self.assertEqual(result['uncertainty']['status'], 'available')

    def test_eighty_step_mixed_quality_sequence_has_bounded_coherent_state(self):
        spec = copy.deepcopy(self.spec)
        spec['arithmetic'].update(max_active_cells=2, identity_history_limit=3)
        candidate = self.new_map(spec)
        history = []
        for index in range(80):
            row = motion_observation(spec, self.run_id, index, body=(.5 * (index % 2), 0., 0.),
                points=((8.25, .25, .25), (9.25, .25, .25), (10.25, .25, .25)))
            if index % 4 == 0:
                row['voxels'][1]['uncertainty'] = interval_quality(spec, None)
            history.append(row)
            candidate.update(row)
            self.assertEqual(set(candidate._cells), set(candidate._log_odds))
            self.assertEqual(len(candidate._log_odds), 2)
            self.assertLessEqual(candidate.retained_identity_count, 3)
            stamp = row['header']['timestamp']
            self.assertEqual(self.query(candidate, stamp)['uncertainty']['status'], 'available')
            self.assertEqual(self.query(candidate, stamp, point=[9.25, .25, .25])['uncertainty']['status'], 'unavailable')
            self.assertFalse(self.query(candidate, stamp, point=[10.25, .25, .25])['observed'])
        before = self.state(candidate)
        self.assertFalse(candidate.update(copy.deepcopy(history[-1])))
        with self.assertRaises(ValueError):
            candidate.update(history[0])
        conflict = copy.deepcopy(history[-1])
        conflict['voxels'][0]['uncertainty']['value'][0] = .6
        with self.assertRaises(ValueError):
            candidate.update(conflict)
        self.assertEqual(self.state(candidate), before)

    def test_equal_age_capacity_ties_have_deterministic_ranges(self):
        spec = copy.deepcopy(self.spec)
        spec['arithmetic']['max_active_cells'] = 2
        left, right = self.new_map(spec), self.new_map(spec)
        row = motion_observation(spec, self.run_id, 0, body=(.5, 0., 0.),
            points=((8.25, .25, .25), (9.25, .25, .25), (10.25, .25, .25)))
        left.update(row)
        row['voxels'].reverse()
        right.update(row)
        self.assertEqual(self.state(left)[:2], self.state(right)[:2])

    def test_foreign_run_clock_and_new_instance_do_not_inherit_ranges(self):
        candidate = self.new_map()
        candidate.update(self.row(0, body=(.5, 0., 0.)))
        before = self.state(candidate)
        for key in ('run_id', 'clock_id'):
            row = self.row(1)
            row['header'][key] = 'foreign'
            if key == 'clock_id':
                row['context']['clock_id'] = 'foreign'
            with self.assertRaises(ValueError):
                candidate.update(row)
            self.assertEqual(self.state(candidate), before)
        fresh = RollingIntervalProbabilityMap(self.spec, 'new', 'sim:new')
        self.assertEqual((fresh.snapshot()['revision'], fresh.snapshot()['cells'], fresh._log_odds), (0, [], {}))

    def test_point_ranges_wire_serialization_and_public_copy_isolation(self):
        candidate = self.new_map()
        for index in range(4):
            candidate.update(self.row(index, bounds=['3/4', '3/4'], body=(.5 * index, 0., 0.)))
        result = self.query(candidate, 40_000_000)
        self.assertEqual(result['uncertainty']['value'], [result['probability']] * 2)
        for message, decode in ((to_ros_query_result(result), from_ros_query_result),
                                (to_ros_snapshot(candidate.snapshot()), from_ros_snapshot)):
            buffer = io.BytesIO()
            message.serialize(buffer)
            decoded = decode(type(message)().deserialize(buffer.getvalue()))
            cells = decoded['cells'] if 'cells' in decoded else [decoded]
            for cell in cells:
                validate_interval_quality(cell['probability'], cell['uncertainty'], self.spec, output=True, wire=True)
        before = candidate.snapshot()
        result['uncertainty']['value'][0] = .1
        self.assertEqual(candidate.snapshot(), before)

    def test_default_startup_does_not_import_rolling_interval_candidate(self):
        code = "from ufm_mapping.factory import create_map; import sys; create_map(); assert 'ufm_mapping.rolling_interval_probability_map' not in sys.modules; from ufm_mapping.rolling_interval_probability_map import RollingIntervalProbabilityMap; assert not any(k.split('.')[0] in ('torch','numpy','diffusion_consistency_radar') for k in sys.modules)"
        subprocess.run([sys.executable, '-B', '-c', code], check=True, timeout=10)

    def test_saved_motion_replay_rejects_changed_range_or_origin_without_oracle(self):
        from m3_rolling_run import main
        reference = dict(probability=.75, interval=[.7, .8], quality_available=True, observed=True,
                         last_observed_timestamp=10_000_000, status='occupied')
        steps = []
        for i, (row, origin) in enumerate(((self.row(0), [-16., -8., -4.]),
                (self.row(1, kind='empty', body=(.5, 0., 0.)), [-15.5, -8., -4.]))):
            steps.append(dict(observation=row, expected=dict(origin=origin, revision=i + 1,
                map_timestamp=10_000_000, cell_count=1, changed=True), queries=[dict(
                point=[8.25, .25, .25], timestamp=(i + 1) * 10_000_000,
                expected=dict(reference, revision=i + 1))]))
        source = dict(spec=self.spec, cases=[dict(name='saved', spec=self.spec, steps=steps, probes=[])])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'fixtures.json'
            for tamper in (None, 'range', 'origin'):
                modified = copy.deepcopy(source)
                if tamper == 'range':
                    modified['cases'][0]['steps'][0]['queries'][0]['expected']['interval'][0] = .6
                elif tamper == 'origin':
                    modified['cases'][0]['steps'][1]['expected']['origin'][0] = -16.
                path.write_text(json.dumps(modified))
                output = io.StringIO()
                with patch.dict(sys.modules, {'m3_oracle': None, 'm3_rolling_scenarios': None}), redirect_stdout(output):
                    result = main(['--input', str(path), '--output-root', folder])
                report = json.loads(output.getvalue())
                self.assertEqual((result, report['passed']), (0 if tamper is None else 1, tamper is None))


if __name__ == '__main__':
    unittest.main()
