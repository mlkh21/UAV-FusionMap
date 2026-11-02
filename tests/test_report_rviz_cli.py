"""Launch errors must fail before opening a master, display or switching to fixtures."""
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReportRvizCliTest(unittest.TestCase):
    def test_live_requires_explicit_master_clock_and_ttl(self):
        for arguments in (['--mode', 'live'], ['--mode', 'live', '--master-uri', 'http://localhost:1'],
                          ['--mode', 'live', '--master-uri', 'http://localhost:1', '--ttl-ns', '100']):
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'ros_ws/report_rviz_run.py')] + arguments,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertIn('live requires explicit', result.stderr)

    def test_invalid_mode_config_never_falls_back_to_demo(self):
        for arguments in (['--mode', 'replay'], ['--receipt', '/unused/file'],
                          ['--master-uri', 'http://localhost:1'], ['--port', '1'],
                          ['--duration-s', '-1']):
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'ros_ws/report_rviz_run.py')] + arguments,
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)


if __name__ == '__main__':
    unittest.main()
