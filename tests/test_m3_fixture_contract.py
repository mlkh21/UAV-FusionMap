"""M3-SW-01 typed synthetic inputs, wire rounding and independent exact expectations."""
from contextlib import redirect_stdout
import copy
from fractions import Fraction as F
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import yaml
from m3_fixture import interval_quality, load_spec, observation, scenarios
from m3_oracle import expected_sequence
from ufm_mapping.m3_contract import (validate_fixture_observation, validate_interval_quality,
                                     validate_spec, wire_probability)
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, to_ros_occupancy


class M3FixtureTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()
        self.cases = scenarios(self.spec)

    def row(self):
        return observation(self.spec, 'm3-test', 0, self.cases['bounded_positive_then_free'][0])

    def test_configuration_is_explicit_default_off_and_separates_sources(self):
        self.assertTrue(self.spec['fixture_only'])
        self.assertFalse(self.spec['enabled_by_default'])
        self.assertEqual(self.spec['arithmetic']['map_id'], 'm3-fixture')
        profile = self.spec['interval_profile']
        self.assertNotEqual(profile['input_source'], profile['output_source'])
        self.assertEqual(profile['wire_rounding'], 'float32_nearest_even_v1')

    def test_bad_configuration_cannot_enable_or_relabel_the_profile(self):
        for changes in (dict(schema_version='unknown'), dict(fixture_only=False),
                        dict(enabled_by_default=True), dict(extra=1), dict(arithmetic=None)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_spec(dict(self.spec, **changes))
        for field, value in (('kind', 'occupancy_variance'), ('unit', 'm2'),
                ('input_source', self.spec['interval_profile']['output_source']),
                ('wire_rounding', 'epsilon_1e-6')):
            spec = copy.deepcopy(self.spec)
            spec['interval_profile'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_spec(spec)
        for section, key, value in (('arithmetic', 'map_id', 'm2-fixture'),
                ('arithmetic', 'enabled_by_default', True), ('arithmetic', 'evidence_ttl_ns', -1),
                ('arithmetic', 'minimum_probability', 1e-100),
                ('arithmetic', 'maximum_probability', 1. - 2**-53),
                ('evidence_intervals', 'occupied', [.8, .9]),
                ('evidence_intervals', 'free', [float('nan'), .3])):
            spec = copy.deepcopy(self.spec)
            spec[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_spec(spec)
        spec = copy.deepcopy(self.spec)
        spec['arithmetic']['occupied_probability'] = .7
        spec['evidence_intervals']['occupied'] = [.6, .8]
        with self.assertRaisesRegex(ValueError, 'already be float32'):
            validate_spec(spec)

    def test_all_fixture_inputs_survive_actual_ros_serialization(self):
        count = 0
        for name, events in self.cases.items():
            for index, event in enumerate(events):
                row = observation(self.spec, 'm3:' + name, index, event)
                validate_fixture_observation(row, self.spec)
                message, buffer = to_ros_occupancy(row), io.BytesIO()
                message.serialize(buffer)
                decoded = from_ros_occupancy(type(message)().deserialize(buffer.getvalue()))
                validate_fixture_observation(decoded, self.spec)
                self.assertEqual(row, decoded)
                self.assertTrue(set(row).isdisjoint({'lidar', 'target', 'observed_mask'}))
                count += 1
        self.assertEqual((len(self.cases), count), (10, 43))

    def test_bad_interval_kind_unit_source_shape_numbers_and_containment_fail(self):
        changes = [dict(kind='occupancy_variance'), dict(unit='m2'), dict(source='unregistered'),
            dict(source=self.spec['interval_profile']['output_source']), dict(status='unknown'),
            dict(value=[]), dict(value=[.7]), dict(value=[.7, .8, .9]), dict(value=[.8, .7]),
            dict(value=[.8, .9]), dict(value=[0., .8]), dict(value=[.7, 1.]),
            dict(value=[True, .8]), dict(value=[.7, float('nan')]),
            dict(value=[.7, float('inf')]), dict(source=1), dict(target=[])]
        for change in changes:
            row = self.row()
            row['voxels'][0]['uncertainty'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_fixture_observation(row, self.spec)

    def test_unavailable_is_distinct_from_zero_width_and_zero_slots(self):
        row = self.row()
        row['voxels'][0]['uncertainty'] = interval_quality(self.spec, None)
        validate_fixture_observation(row, self.spec)
        row['voxels'][0]['uncertainty'] = interval_quality(self.spec, ['3/4', '3/4'])
        validate_fixture_observation(row, self.spec)
        for quality in (dict(row['voxels'][0]['uncertainty'], value=[0., 0.]),
                dict(interval_quality(self.spec, None), value=[]),
                dict(interval_quality(self.spec, None), value=[0., 0.])):
            with self.assertRaises(ValueError):
                validate_interval_quality(.75, quality, self.spec)

    def test_nonpoint_neutral_is_rejected_and_no_evidence_does_not_become_free(self):
        event = self.cases['zero_width_neutral'][0]
        row = observation(self.spec, 'neutral', 0, event)
        validate_fixture_observation(row, self.spec)
        row['voxels'][0]['uncertainty']['value'] = [.4, .6]
        with self.assertRaisesRegex(ValueError, 'neutral'):
            validate_fixture_observation(row, self.spec)
        for event in self.cases['no_evidence_without_history']:
            row = observation(self.spec, 'no-evidence', 0, event)
            self.assertTrue(not row['voxels'] or all(v['probability'] == .5 for v in row['voxels']))

    def test_sources_training_fields_and_pose_quality_are_not_accepted_as_m3_evidence(self):
        for key in ('lidar', 'target', 'observed_mask'):
            row = dict(self.row(), **{key: []})
            with self.assertRaises(ValueError):
                validate_fixture_observation(row, self.spec)
            row = self.row()
            row['voxels'][0][key] = []
            with self.assertRaises(ValueError):
                validate_fixture_observation(row, self.spec)
        for changes in (dict(source_type='model'), dict(source_type='measured'), dict(frame_id='map')):
            row = self.row()
            row['header'].update(changes)
            with self.assertRaises(ValueError):
                validate_fixture_observation(row, self.spec)
        row = self.row()
        row['observed_domain_source'] = 'fixture_radar_point'
        with self.assertRaises(ValueError):
            validate_fixture_observation(row, self.spec)
        row = self.row()
        row['context']['pose_uncertainty'] = dict(status='available', kind='occupancy_variance',
            value=[.125], unit='dimensionless', source='fixture')
        with self.assertRaisesRegex(ValueError, 'pose'):
            validate_fixture_observation(row, self.spec)

    def test_last_bad_voxel_is_rejected_without_mutating_input(self):
        row = self.row()
        other = copy.deepcopy(row['voxels'][0])
        other['index'][0] += 1
        other['uncertainty']['unit'] = 'm2'
        row['voxels'].append(other)
        before = copy.deepcopy(row)
        with self.assertRaises(ValueError):
            validate_fixture_observation(row, self.spec)
        self.assertEqual(before, row)
        row['voxels'][1]['uncertainty']['unit'] = 'dimensionless'
        validate_fixture_observation(row, self.spec)

    def test_input_requires_wire_mean_and_does_not_expand_nonwire_point_interval(self):
        row = self.row()
        row['voxels'][0].update(probability=.7, uncertainty=interval_quality(self.spec, [.7, .7]))
        with self.assertRaisesRegex(ValueError, 'float32'):
            validate_fixture_observation(row, self.spec)
        nominal = wire_probability(.7)
        row['voxels'][0]['probability'] = nominal
        with self.assertRaisesRegex(ValueError, 'excludes'):
            validate_fixture_observation(row, self.spec)
        row['voxels'][0]['uncertainty']['value'] = [nominal, nominal]
        validate_fixture_observation(row, self.spec)
        with self.assertRaises(ValueError):
            validate_interval_quality(nominal, row['voxels'][0]['uncertainty'], self.spec, wire=True)

    def test_wire_probability_rejects_bool_nonfinite_and_rounded_endpoints(self):
        for value in (True, 0., 1., float('nan'), float('inf'), 1e-100, 1. - 2**-53):
            with self.subTest(value=value), self.assertRaises(ValueError):
                wire_probability(value)
        self.assertEqual(wire_probability(2**-149), 2**-149)

    def test_output_wire_budget_handles_point_intervals_and_rejects_adjacent_means(self):
        for point in (.1, .7, .9):
            quality = interval_quality(self.spec, [point, point], output=True)
            validate_interval_quality(point, quality, self.spec, output=True)
            nominal = wire_probability(point)
            with self.assertRaises(ValueError):
                validate_interval_quality(nominal, quality, self.spec, output=True)
            validate_interval_quality(nominal, quality, self.spec, output=True, wire=True)
            bits = struct.unpack('!I', struct.pack('!f', nominal))[0]
            neighbor = struct.unpack('!f', struct.pack('!I', bits + 1))[0]
            with self.assertRaises(ValueError):
                validate_interval_quality(neighbor, quality, self.spec, output=True, wire=True)

    def test_output_rounding_obeys_nearest_even_ties_and_asymmetric_binade_spacing(self):
        even, odd = .5, .5 + 2**-24
        midpoint = .5 + 2**-25
        quality = interval_quality(self.spec, [midpoint, midpoint], output=True)
        validate_interval_quality(even, quality, self.spec, output=True, wire=True)
        with self.assertRaises(ValueError):
            validate_interval_quality(odd, quality, self.spec, output=True, wire=True)
        below = .5 - 2**-26
        quality['value'] = [below, below]
        validate_interval_quality(even, quality, self.spec, output=True, wire=True)
        with self.assertRaises(ValueError):
            validate_interval_quality(.5 - 2**-25, quality, self.spec, output=True, wire=True)

    def test_oracle_matches_hand_calculated_bounded_sequence(self):
        expected = expected_sequence(self.cases['bounded_positive_then_free'], self.spec['arithmetic'])
        self.assertEqual([row['probability_fraction'] for row in expected], ['3/4', '9/10', '3/4'])
        self.assertEqual([row['interval_fractions'] for row in expected],
                         [['7/10', '4/5'], ['49/58', '9/10'], ['49/85', '27/34']])
        self.assertEqual([row['revision'] for row in expected], [1, 2, 3])

    def test_oracle_point_interval_saturation_and_order_are_not_batch_updates(self):
        for name in ('zero_width_binary32', 'positive_saturation_reverse', 'negative_saturation_reverse'):
            result = expected_sequence(self.cases[name], self.spec['arithmetic'])
            for row in result:
                lower, upper = map(F, row['interval_fractions'])
                self.assertLessEqual(lower, F(row['probability_fraction']))
                self.assertLessEqual(F(row['probability_fraction']), upper)
                self.assertTrue(F('1/10') <= lower <= upper <= F('9/10'))
                if name == 'zero_width_binary32':
                    self.assertEqual(lower, upper)
        positive = expected_sequence(self.cases['positive_saturation_reverse'], self.spec['arithmetic'])
        self.assertEqual([row['probability_fraction'] for row in positive],
                         ['3/4', '9/10', '9/10', '3/4', '1/2', '1/4'])
        self.assertNotEqual(positive[-1]['probability_fraction'], '1/2')  # batch cancellation is wrong

    def test_oracle_missing_quality_latches_until_ttl_restart(self):
        locked = expected_sequence(self.cases['missing_lock'], self.spec['arithmetic'])
        self.assertEqual([row['quality_available'] for row in locked], [True, False, False])
        self.assertEqual([row['probability_fraction'] for row in locked], ['3/4', '1/2', '3/4'])
        recovered = expected_sequence(self.cases['missing_then_ttl_restart'], self.spec['arithmetic'])
        self.assertEqual([row['quality_available'] for row in recovered], [False] * 4 + [True])
        self.assertEqual([row['status'] for row in recovered],
                         ['occupied', 'unknown', 'unknown', 'stale', 'occupied'])
        self.assertEqual(recovered[-1]['interval_fractions'], ['7/10', '4/5'])
        self.assertEqual(recovered[-1]['probability_fraction'], '3/4')

    def test_oracle_no_evidence_and_ttl_reads_do_not_refresh_quality_or_time(self):
        for name in ('no_evidence_without_history', 'zero_width_neutral'):
            for row in expected_sequence(self.cases[name], self.spec['arithmetic']):
                self.assertEqual((row['probability'], row['interval'], row['revision']), (None, None, 0))
                self.assertEqual(row['status'], 'unavailable')
        kept = expected_sequence(self.cases['no_evidence_preserves_quality'], self.spec['arithmetic'])
        self.assertTrue(all(row == kept[0] for row in kept))
        boundary = expected_sequence(self.cases['ttl_boundary'], self.spec['arithmetic'])
        self.assertEqual([row['status'] for row in boundary], ['occupied', 'occupied', 'stale', 'free'])
        self.assertEqual([row['last_observed_timestamp'] for row in boundary],
                         [10_000_000] * 3 + [120_000_000])

    def test_oracle_refuses_bad_events_without_reordering_or_filling_bounds(self):
        for change in (dict(kind='unknown'), dict(probability='0'), dict(bounds=['4/5', '7/10']),
                       dict(bounds=['4/5', '9/10']), dict(bounds=['7/10']), dict(timestamp=-1)):
            rows = copy.deepcopy(self.cases['bounded_positive_then_free'])
            rows[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                expected_sequence(rows, self.spec['arithmetic'])
        for stamp in (10_000_000, 0):
            rows = copy.deepcopy(self.cases['bounded_positive_then_free'])
            rows[1]['timestamp'] = stamp
            with self.assertRaises(ValueError):
                expected_sequence(rows, self.spec['arithmetic'])

    def test_contract_has_no_research_imports_and_default_map_does_not_load_m3(self):
        code = "from ufm_mapping.factory import create_map; import sys; create_map(); assert 'ufm_mapping.m3_contract' not in sys.modules; from ufm_mapping import m3_contract; assert not any(k.split('.')[0] in ('torch', 'numpy', 'diffusion_consistency_radar') for k in sys.modules)"
        subprocess.run([sys.executable, '-B', '-c', code], check=True, timeout=10)

    def test_runner_freezes_inputs_and_refuses_bad_config_without_accumulation(self):
        from m3_fixture_run import main
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'config.yaml'
            for valid in (True, False):
                spec = copy.deepcopy(self.spec)
                spec['enabled_by_default'] = not valid
                config.write_text(yaml.safe_dump(spec))
                output = io.StringIO()
                with redirect_stdout(output):
                    result = main(['--config', str(config), '--output-root', folder])
                receipt = json.loads(output.getvalue())
                report = json.loads((Path(receipt['run']) / 'report.json').read_text())
                self.assertEqual((result, report['passed']), (0 if valid else 1, valid))
                self.assertFalse(report['map_accumulation_executed'])
                if valid:
                    self.assertEqual((report['scenario_count'], report['observation_count']), (10, 43))
                else:
                    self.assertFalse((Path(receipt['run']) / 'fixtures.json').exists())


if __name__ == '__main__':
    unittest.main()
