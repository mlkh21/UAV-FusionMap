"""PERF-01预算配置必须在正式输入缺失时保持fail-closed。"""
import copy
from pathlib import Path
import unittest

import yaml

from perf01_budget_gate import evaluate_budget


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs/perf01_budget.yaml'


class Perf01BudgetGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(CONFIG.read_text())

    def test_current_config_is_reference_only(self):
        result = evaluate_budget(self.config)
        self.assertFalse(result['ready'])
        self.assertEqual(result['mode'], 'reference_only')
        self.assertEqual(result['errors'], [])
        self.assertIn('formal measurement status is not confirmed', result['blockers'])
        self.assertIn('target airborne platform is not confirmed', result['blockers'])

    def test_thresholds_cannot_drift(self):
        config = copy.deepcopy(self.config)
        config['timing_contract']['max_radar_ir_delta_ms'] = 6.0
        config['timing_contract']['max_p99_latency_ms'] = 21.0
        result = evaluate_budget(config)
        self.assertIn('max_radar_ir_delta_ms must remain 5.0', result['errors'])
        self.assertIn('max_p99_latency_ms must remain 20.0', result['errors'])

    def test_confirmed_inputs_can_reach_formal_ready(self):
        config = copy.deepcopy(self.config)
        config['target_airborne_platform']['status'] = 'confirmed_selected_platform'
        config['reference_sensors']['radar'].update(frequency_hz=20.0, timestamp_error_ms=1.0)
        config['reference_sensors']['infrared'].update(
            status='confirmed_selected_sensor', timestamp_error_ms=1.0)
        config['formal_measurement'].update(
            status='confirmed', target_platform_id='platform-01',
            start_endpoint='radar_capture_timestamp', end_endpoint='occupancy_ready',
            sampling_clock_source='ptp', clock_domain_mapping='ptp-to-monotonic-v1',
            continuous_duration_s=2400.0)
        result = evaluate_budget(config)
        self.assertTrue(result['ready'])
        self.assertEqual(result['mode'], 'formal_ready')
        self.assertEqual(result['blockers'], [])
        self.assertEqual(result['errors'], [])


if __name__ == '__main__':
    unittest.main()
