"""M2-SW-01 contract, wire compatibility and independently fixed rational expectations."""
import copy
import unittest

from m2_fixture import SCENARIOS, load_spec, observation
from m2_oracle import expected_sequence
from ufm_mapping.m2_contract import validate_fixture_observation, validate_spec
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, to_ros_occupancy


class M2FixtureTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()

    def test_explicit_parameters_and_default_off(self):
        self.assertTrue(self.spec['fixture_only'])
        self.assertFalse(self.spec['enabled_by_default'])
        self.assertEqual(self.spec['prior_probability'], .5)
        self.assertEqual(self.spec['occupied_probability'], .75)
        self.assertEqual(self.spec['free_probability'], .25)
        self.assertEqual(self.spec['evidence_ttl_ns'], 100_000_000)

    def test_invalid_or_undeclared_configuration_is_rejected(self):
        for key, value in (('fixture_only', False), ('enabled_by_default', True),
                ('prior_probability', .6), ('occupied_probability', float('nan')),
                ('free_probability', 1.), ('sample_period_ns', True), ('evidence_ttl_ns', 1.5),
                ('shape', [True, 32, 16]), ('cell_index', [64, 0, 0]), ('extra', 'unknown')):
            spec = dict(self.spec, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_spec(spec)

    def test_every_fixture_round_trips_existing_ros_message(self):
        for scenario, kinds in SCENARIOS.items():
            identities = set()
            for index, kind in enumerate(kinds):
                value = observation(self.spec, 'm2:' + scenario, index, kind)
                validate_fixture_observation(value, self.spec)
                self.assertEqual(value, from_ros_occupancy(to_ros_occupancy(value)))
                self.assertNotIn(value['header']['sample_id'], identities)
                identities.add(value['header']['sample_id'])
                self.assertTrue(set(value).isdisjoint({'lidar', 'target', 'observed_mask'}))

    def test_source_and_domain_cannot_relabel_placeholder_or_model_as_evidence(self):
        for key, value in (('source_type', 'model'), ('source_type', 'measured'),
                           ('source_type', 'simulation'), ('frame_id', 'map')):
            row = observation(self.spec, 'm2', 0, 'occupied')
            row['header'][key] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_fixture_observation(row, self.spec)
        row = observation(self.spec, 'm2', 0, 'occupied')
        row['observed_domain_source'] = 'fixture_radar_point'
        with self.assertRaises(ValueError):
            validate_fixture_observation(row, self.spec)
        row = observation(self.spec, 'm2', 0, 'occupied')
        row['lidar'] = []
        with self.assertRaises(ValueError):
            validate_fixture_observation(row, self.spec)

    def test_fixed_fixture_context_does_not_assume_missing_transform(self):
        for key, value in (('clock_id', 'foreign'), ('reference_timestamp', 0),
                ('calibration_id', 'real-device'), ('T_mapping_body_status', 'unavailable'),
                ('T_mapping_source', [0.] * 16)):
            row = observation(self.spec, 'm2', 0, 'occupied')
            row['context'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_fixture_observation(row, self.spec)

    def test_invalid_probability_index_quality_and_nonvalid_evidence_are_rejected(self):
        for changes in (dict(probability=0.), dict(probability=1.), dict(probability=True),
                dict(probability=float('inf')), dict(observed=1), dict(index=[48.5, 16, 8]),
                dict(index=[64, 0, 0]), dict(confidence=float('nan'))):
            row = observation(self.spec, 'm2', 0, 'occupied')
            row['voxels'][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_fixture_observation(row, self.spec)
        row = observation(self.spec, 'm2', 0, 'occupied')
        row['voxels'].append(copy.deepcopy(row['voxels'][0]))
        with self.assertRaises(ValueError):
            validate_fixture_observation(row, self.spec)
        row['voxels'] = row['voxels'][:1]
        row['header'].update(status='unavailable', reason='fixture failure')
        with self.assertRaises(ValueError):
            validate_fixture_observation(row, self.spec)

    def test_free_is_explicit_and_missing_or_unobserved_is_neutral(self):
        free = observation(self.spec, 'm2', 0, 'free')['voxels'][0]
        self.assertEqual((free['probability'], free['observed']), (.25, True))
        unknown = observation(self.spec, 'm2', 1, 'unobserved')
        self.assertEqual((unknown['voxels'][0]['probability'], unknown['voxels'][0]['observed']), (.5, False))
        for kind in ('empty', 'no_return', 'unavailable', 'degraded'):
            self.assertEqual(observation(self.spec, 'm2', 2, kind)['voxels'], [])
        unknown['voxels'][0]['probability'] = .25
        with self.assertRaises(ValueError):
            validate_fixture_observation(unknown, self.spec)

    def test_oracle_matches_fixed_hand_calculated_sequences(self):
        cases = {
            'positive_twice': ['3/4', '9/10'],
            'negative_twice': ['1/4', '1/10'],
            'positive_saturation_then_reverse': ['3/4', '9/10', '9/10', '3/4'],
            'negative_saturation_then_reverse': ['1/4', '1/10', '1/10', '1/4'],
            'reverse_to_free': ['3/4', '9/10', '3/4', '1/2', '1/4'],
            'cancel_to_unknown': ['3/4', '1/2'],
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                actual = expected_sequence(SCENARIOS[name], self.spec)
                self.assertEqual([row['probability_fraction'] for row in actual], expected)

    def test_oracle_no_evidence_never_refreshes_last_evidence_time(self):
        for name in ('neutral_without_history', 'no_evidence_without_history'):
            for row in expected_sequence(SCENARIOS[name], self.spec):
                self.assertIsNone(row['probability'])
                self.assertIsNone(row['last_observed_timestamp'])
                self.assertFalse(row['observed'])
        actual = expected_sequence(SCENARIOS['no_evidence_preserves_history'], self.spec)
        self.assertTrue(all(row['probability_fraction'] == '3/4' for row in actual))
        self.assertEqual({row['last_observed_timestamp'] for row in actual},
                         {self.spec['sample_period_ns']})

    def test_oracle_scope_does_not_fabricate_future_ttl_results(self):
        kinds = ['occupied'] + ['neutral'] * 11 + ['free']
        with self.assertRaisesRegex(ValueError, 'excludes TTL'):
            expected_sequence(kinds, self.spec)


if __name__ == '__main__':
    unittest.main()
