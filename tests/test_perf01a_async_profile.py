"""ROS参数服务器的可选fixture配置边界。"""
import sys
import unittest
import xmlrpc.client
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros_ws'))

import perf01a_async_run
from perf01a_async_run import ros_param_profile
from ufm_sensors.perf01a_async import load_profile


class AsyncProfileTest(unittest.TestCase):
    def test_runner_and_business_share_nested_merge_and_explicit_cli_overrides(self):
        config = yaml.safe_load((ROOT / 'configs/perf01a_async.yaml').read_text())
        config['defaults']['fake_radar']['position_noise_std_m'] = .25
        config['scenarios']['custom'] = {'fake_radar': {'max_range_m': 6.}, 'speed_mps': 35}
        args = SimpleNamespace(scenario='custom', config=None, full_ir=False,
                               speed_mps=None, pairing_policy=None, boundary_obstacles=False)
        with patch('ufm_sensors.perf01a_async.yaml.safe_load', return_value=config):
            business = load_profile('custom')
            actual = perf01a_async_run.resolve_profile(args)
            self.assertEqual(actual, business)
            self.assertEqual(actual['fake_radar']['position_noise_std_m'], .25)
            self.assertEqual(actual['speed_mps'], 35)
            args.speed_mps = 0
            self.assertEqual(perf01a_async_run.resolve_profile(args)['speed_mps'], 0)

    def test_normal_profile_omits_optional_null_without_changing_source(self):
        config = yaml.safe_load((ROOT / 'configs/perf01a_async.yaml').read_text())
        profile = dict(config['defaults'], **config['scenarios']['normal'])
        safe = ros_param_profile(profile)
        self.assertNotIn('fov_deg', safe['fake_radar'])
        self.assertNotIn('max_range_m', safe['fake_radar'])
        self.assertIsNone(profile['fake_radar']['fov_deg'])
        self.assertEqual(safe['fake_infrared']['background_value'],
                         profile['fake_infrared']['background_value'])
        xmlrpc.client.dumps((safe,), allow_none=False)


if __name__ == '__main__':
    unittest.main()
