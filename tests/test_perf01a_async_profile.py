"""ROS参数服务器的可选fixture配置边界。"""
import sys
import unittest
import xmlrpc.client
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros_ws'))

from perf01a_async_run import ros_param_profile


class AsyncProfileTest(unittest.TestCase):
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
