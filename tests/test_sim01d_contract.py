"""SIM-01D配置和验收边界的轻量契约测试，不启动长测。"""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros_ws'))
from sim01d_record import BOUNDARY_NS, SPAN_NS, SOURCE_LIMIT_NS, load_settings
import sim01d_record
import check_sim01d_continuity


class Sim01DContractTest(unittest.TestCase):
    def test_frozen_boundary_config(self):
        root = Path(__file__).resolve().parents[1]
        path, values = load_settings(root)
        self.assertEqual(path.name, 'sim01d_continuity.yaml')
        self.assertEqual(int(values['boundary_ns']), BOUNDARY_NS)
        self.assertEqual(int(values['min_valid_span_ns']), SPAN_NS)
        self.assertEqual(int(values['source_limit_ns']), SOURCE_LIMIT_NS)

    def test_boundary_is_inside_recording_window_with_margin(self):
        self.assertLess(BOUNDARY_NS, SPAN_NS)
        self.assertLess(SPAN_NS, SOURCE_LIMIT_NS)

    def test_old_bridge_is_rejected_before_dependency_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'sim01d-bridge'
            old_bridge = Path(directory) / 'init01-bridge'
            candidate.touch()
            old_bridge.touch()
            with patch.object(sim01d_record, 'SIM01D_BRIDGE_BINARY', candidate), \
                    patch.object(sim01d_record.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, '仅接受项目独立候选'):
                    sim01d_record.bridge_preflight(old_bridge)
                run.assert_not_called()

    def test_sim01d_bridge_retains_executable_and_dependency_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / 'sim01d-bridge'
            candidate.touch()
            with patch.object(sim01d_record, 'SIM01D_BRIDGE_BINARY', candidate), \
                    patch.object(sim01d_record.os, 'access', return_value=True), \
                    patch.object(sim01d_record.subprocess, 'run') as run:
                run.return_value.returncode = 0
                run.return_value.stdout = 'libc.so.6 => /lib/libc.so.6'
                result = sim01d_record.bridge_preflight(candidate)
                self.assertEqual(result['path'], str(candidate))
                run.return_value.stdout = 'libjsbsim.so => not found'
                with self.assertRaisesRegex(RuntimeError, '未解析动态库'):
                    sim01d_record.bridge_preflight(candidate)

    def test_checker_default_is_read_only_and_preserves_failure_exit(self):
        result = {'passed': False, 'errors': ['boundary: missing']}
        with patch.object(check_sim01d_continuity, 'validate_sim01d', return_value=result), \
                patch.object(Path, 'open', side_effect=AssertionError('unexpected file access')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(check_sim01d_continuity.main(['existing-run']), 1)
        self.assertEqual(json.loads(output.getvalue()), result)

    def test_checker_explicit_output_never_overwrites_existing_file(self):
        result = {'passed': True, 'errors': []}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'result.json'
            with patch.object(check_sim01d_continuity, 'validate_sim01d', return_value=result), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check_sim01d_continuity.main(['existing-run', '--output', str(output)]), 0)
                original = output.read_bytes()
                self.assertEqual(json.loads(original), result)
                with self.assertRaises(SystemExit) as failure:
                    check_sim01d_continuity.main(['existing-run', '--output', str(output)])
                self.assertEqual(failure.exception.code, 2)
                self.assertEqual(output.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
