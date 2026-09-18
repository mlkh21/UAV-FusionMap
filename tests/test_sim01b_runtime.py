"""真实诊断消息驱动记录器：WARN里的丢帧计数也必须及时终止。"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros_ws'))
from sim01b_runtime import Recorder, DIAGNOSTIC_TOPIC, load_settings


class FrozenConfigTest(unittest.TestCase):
    def test_confirmed_defaults_are_accepted(self):
        root = Path(__file__).resolve().parents[1]
        _, values = load_settings(root)
        self.assertEqual(int(values['min_valid_span_ns']), 300000000000)

    def test_unwired_custom_quality_thresholds_are_rejected(self):
        root = Path(__file__).resolve().parents[1]
        for key, value in (('min_valid_span_ns', '301000000000'), ('min_clock_hz', 41.),
                           ('min_state_hz', 11.), ('max_gap_ns', '400000000')):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'custom.yaml'
                path.write_text(yaml.safe_dump({key: value}))
                with self.assertRaises(ValueError):
                    load_settings(root, path)


class RuntimeDiagnosticTest(unittest.TestCase):
    def test_warn_drop_counters_fail_before_end_of_live(self):
        for key in ('pending_timeout', 'pending_overflow', 'sample_identity_conflict', 'duplicate_state'):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                with patch('rospy.Subscriber'):
                    recorder = Recorder(Path(directory), 'live.bag', 100)
                try:
                    msg = DiagnosticArray(status=[DiagnosticStatus(
                        level=DiagnosticStatus.WARN, name='simulation/state_clock', message=key,
                        values=[KeyValue(key=key, value='1')])])
                    recorder._receive(msg, DIAGNOSTIC_TOPIC)
                    with self.assertRaises(RuntimeError):
                        recorder.raise_errors()
                finally:
                    recorder.close()

    def test_preparing_warning_without_drop_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('rospy.Subscriber'):
                recorder = Recorder(Path(directory), 'live.bag', 100)
            try:
                recorder._receive(DiagnosticArray(status=[DiagnosticStatus(
                    level=DiagnosticStatus.WARN, name='simulation/state_clock', message='timeline:PREPARING',
                    values=[KeyValue(key='pending_timeout', value='0')])]), DIAGNOSTIC_TOPIC)
                recorder.raise_errors()
            finally:
                closed = recorder.close()
            self.assertTrue(closed['passed'])


if __name__ == '__main__':
    unittest.main()
