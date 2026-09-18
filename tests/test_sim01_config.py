"""回归实际发生的ROS1参数服务器大整数装载失败。"""
from pathlib import Path
import unittest
import xmlrpc.client

import yaml


class ConfigTransportTest(unittest.TestCase):
    def test_config_can_cross_xmlrpc_without_losing_nanoseconds(self):
        root=Path(__file__).resolve().parents[1]
        config=yaml.safe_load((root/'configs/sim01_state.yaml').read_text())
        payload=xmlrpc.client.dumps((config,))
        restored=xmlrpc.client.loads(payload)[0][0]
        self.assertEqual(int(restored['warmup_stable_sim_ns']),10000000000)
        self.assertEqual(restored['pending_limit'],100)
        self.assertEqual(restored['pending_timeout_wall_s'],.5)


if __name__=='__main__':
    unittest.main()
