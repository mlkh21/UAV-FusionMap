"""M5-SW-03 time, saturation, failure recovery and saved-input checks."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from m5_fixture import load_spec, query_request
from m5_time_scenarios import scenarios, capacity_spec
from m5_time_validation import execute_case, resource_probe, make_layer, inject_install, FAULTS


class TerrainTimeResourceTest(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec()
        self.cases = scenarios(self.spec)

    def test_full_64_event_multiversion_sequence_preserves_heights_quality_and_time(self):
        result = execute_case(self.cases[0])
        self.assertEqual(len(result['receipts']),64)
        self.assertEqual(result['final_snapshot']['terrain_revision'],8)
        self.assertEqual(len(result['final_snapshot']['version_ids']),8)
        self.assertEqual(result['final_snapshot']['installed_timestamp'],380)

    def test_delayed_activation_registration_expiry_and_terminal_reset(self):
        result = execute_case(self.cases[1])
        self.assertTrue(result['final_snapshot']['locked'])
        self.assertEqual(result['final_snapshot']['terrain_revision'],2)
        self.assertEqual(result['receipts'][2]['outcome'],'rejected')

    def test_disable_overrides_stale_values_and_duplicate_retries(self):
        result = execute_case(self.cases[2])
        self.assertFalse(result['final_snapshot']['enabled'])
        self.assertEqual(result['receipts'][-1]['result']['height'],None)

    def test_new_run_starts_empty_and_foreign_domain_does_not_poison_it(self):
        result = execute_case(self.cases[3])
        self.assertEqual(result['final_snapshot']['version_ids'],[self.spec['identity']['dataset_version']])
        self.assertEqual(result['receipts'][-1]['result']['height'],13.)

    def test_saved_expectation_mismatch_is_a_failure_not_a_rebuilt_oracle(self):
        case = self.cases[0]
        case['expected'][1]['result']['height'] = 999.
        with self.assertRaisesRegex(AssertionError,'height'):
            execute_case(case)

    def test_fault_site_failure_restores_trace_and_same_version_can_retry(self):
        spec = capacity_spec(self.spec)
        for fault in FAULTS:
            with self.subTest(fault=fault[0]):
                layer = make_layer(spec)
                layer.observe_clock(100)
                before = layer.snapshot()
                previous = sys.gettrace()
                inject_install(layer,spec,100,fault)
                self.assertIs(sys.gettrace(),previous)
                self.assertEqual(layer.snapshot(),before)
                self.assertTrue(layer.install(spec,100))
                self.assertFalse(layer.install(spec,100))

    def test_last_sample_numeric_failure_retains_old_version_then_retry_replaces_whole_tile(self):
        spec = capacity_spec(self.spec)
        spec['registration']['T_map_terrain'][11] = 1e308
        spec['registration']['height_quality']['value'] = [1e308,1e308]
        layer = make_layer(spec)
        layer.observe_clock(100)
        layer.install(spec,100)
        replacement = copy.deepcopy(spec)
        replacement['identity']['dataset_version'] = 'late-numeric-failure'
        replacement['grid']['heights'][-1] = 1e308
        layer.observe_clock(101)
        before = layer.snapshot()
        with self.assertRaisesRegex(ValueError,'overflow'):
            layer.install(replacement,101)
        self.assertEqual(layer.snapshot(),before)
        replacement['grid']['heights'][-1] = -1e308
        self.assertTrue(layer.install(replacement,101))
        self.assertEqual(layer.snapshot()['samples'][-1]['height'],0.)
        self.assertEqual(layer.query(query_request(spec,101,(117.,173.)))['status'],'valid')

    def test_full_identity_payload_budget_faults_and_return_copies_are_counted(self):
        report = resource_probe(capacity_spec(self.spec))
        self.assertEqual(report['retained']['identities'],64)
        self.assertEqual(report['retained']['identity_bytes'],1024000)
        self.assertEqual(len(report['fault_sites']),5)
        self.assertEqual(len(report['rejections']),5)
        self.assertEqual(report['census']['peaks']['states'],2)
        self.assertGreaterEqual(report['census']['peaks']['grid_samples'],64)
        self.assertGreaterEqual(report['census']['peaks']['sample_payloads'],32)
        self.assertGreaterEqual(report['census']['peaks']['canonical_bytes'],1024000)
        self.assertEqual(report['census']['peaks']['encoder_current_part_bytes'],196610)
        self.assertTrue(report['terminal_reset_disable_unavailable'])

    def test_overlong_text_is_rejected_before_json_encoder_and_old_state_survives(self):
        from ufm_mapping.m5_contract import validate_spec
        spec = capacity_spec(self.spec)
        layer = make_layer(spec)
        layer.observe_clock(100)
        layer.install(spec,100)
        before = layer.snapshot()
        for field in ('dataset_version','source_ref'):
            too_large = copy.deepcopy(spec)
            too_large['identity'][field] = 'x'*16385
            with self.subTest(field=field), \
                 patch('ufm_mapping.terrain_fixture.json.JSONEncoder',side_effect=AssertionError('must reject before encoding')):
                with self.assertRaisesRegex(ValueError,'byte limit'):
                    layer.install(too_large,100)
                with self.assertRaisesRegex(ValueError,'byte limit'):
                    validate_spec(too_large)
            self.assertEqual(layer.snapshot(),before)

    def test_saved_inputs_execute_without_rebuilding_and_leave_occupancy_unchanged(self):
        from m5_time_run import execute, save
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save(root/'inputs.json',dict(cases=self.cases,resource_spec=capacity_spec(self.spec)))
            content = (root/'inputs.json').read_bytes()
            # Resource stress has its own full test; this check isolates the saved-input path.
            with patch('m5_time_scenarios.scenarios',side_effect=AssertionError('must not rebuild')), \
                 patch('m5_time_validation.resource_probe',return_value={}):
                result = execute(root)
            self.assertTrue(result['occupancy_snapshot_unchanged'])
            self.assertEqual((root/'inputs.json').read_bytes(),content)
            self.assertEqual(len(result['cases']),4)


if __name__ == '__main__':
    unittest.main()
