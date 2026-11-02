"""端口预检失败仍需保留报告；不创建socket或ROS进程。"""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import local_map_query_run as runner


class LocalMapSupervisorTest(unittest.TestCase):
    def test_socket_denial_returns_failure_and_preserves_manifest(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            processes = Mock()
            processes.cleanup.return_value = {'passed': True}
            stack.enter_context(patch.object(runner, '__file__', str(root / 'ros_ws/runner.py')))
            stack.enter_context(patch.object(runner.sys, 'argv', ['runner.py', '--mode', 'inference']))
            stack.enter_context(patch.object(runner, 'configure_environment', return_value={
                'ROS_MASTER_URI': 'http://127.0.0.1:11451'}))
            stack.enter_context(patch.object(runner, 'Processes', return_value=processes))
            stack.enter_context(patch.object(runner, 'install_interrupt_handler'))
            stack.enter_context(patch.object(runner, 'probe_ports', side_effect=PermissionError('socket denied')))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            manifests = list((root / '.runtime/runs').glob('*/manifest.json'))
            self.assertEqual(len(manifests), 1)
            manifest = json.loads(manifests[0].read_text())
            self.assertFalse(manifest['passed'])
            self.assertTrue(any('socket denied' in item for item in manifest['errors']))
            processes.spawn.assert_not_called()
            processes.cleanup.assert_called_once()
