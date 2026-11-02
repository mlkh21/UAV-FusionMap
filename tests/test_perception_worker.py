"""Bounded CPU process execution: deadline, busy ordering, crash and shutdown."""
import multiprocessing
import os
import time
import unittest

from test_perf01a_contract import valid_bundle
from ufm_perception.engine import PerceptionEngine, UntrustedInputError
from ufm_perception.worker import BoundedPerceptionWorker


class SlowEngine(PerceptionEngine):
    def process(self, bundle):
        if bundle['header']['sample_id'].endswith(':slow'):
            time.sleep(2.)
        if bundle['header']['sample_id'].endswith(':crash'):
            os._exit(3)
        return super().process(bundle)


class WorkerTest(unittest.TestCase):
    def make(self, deadline=2.):
        worker = BoundedPerceptionWorker(SlowEngine('perf-run'), deadline)
        self.addCleanup(worker.close)
        return worker

    def bundle(self, stamp=100_000_000, suffix=''):
        bundle = valid_bundle(radar_timestamp=stamp)
        bundle['header']['sample_id'] += ':' + str(stamp) + suffix
        return bundle

    def wait(self, worker):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            result = worker.poll()
            if result is not None:
                return result
            time.sleep(.01)
        self.fail('worker result timeout')

    def test_normal_result_and_shutdown(self):
        worker = self.make()
        self.assertIsNone(worker.submit(self.bundle()))
        self.assertEqual(self.wait(worker)['header']['status'], 'valid')
        self.assertIsNone(worker.active_pid)
        worker.close()
        with self.assertRaises(RuntimeError):
            worker.submit(self.bundle(200_000_000))

    def test_deadline_stops_process_then_next_frame_recovers(self):
        worker = self.make(.4)
        worker.submit(self.bundle(suffix=':slow'))
        pid = worker.active_pid
        result = self.wait(worker)
        self.assertEqual(result['header']['reason'], 'perception_backend_timeout')
        self.assertNotIn(pid, [child.pid for child in multiprocessing.active_children()])
        worker.deadline_s = 2.
        worker.submit(self.bundle(200_000_000))
        self.assertEqual(self.wait(worker)['header']['status'], 'valid')

    def test_busy_output_supersedes_old_result_without_queueing(self):
        worker = self.make(.4)
        worker.submit(self.bundle(suffix=':slow'))
        result = worker.submit(self.bundle(200_000_000))
        self.assertEqual(result['header']['reason'], 'perception_backend_busy')
        deadline = time.monotonic() + 3
        while worker.active_pid is not None and time.monotonic() < deadline:
            self.assertIsNone(worker.poll())
            time.sleep(.01)
        self.assertIsNone(worker.active_pid)
        self.assertEqual(worker.discarded_results, 1)
        with self.assertRaises(UntrustedInputError):
            worker.submit(self.bundle(150_000_000))

    def test_crashed_worker_is_unavailable(self):
        worker = self.make()
        worker.submit(self.bundle(suffix=':crash'))
        self.assertEqual(self.wait(worker)['header']['reason'], 'perception_worker_exited')

    def test_close_terminates_active_job(self):
        worker = self.make()
        worker.submit(self.bundle(suffix=':slow'))
        pid = worker.active_pid
        worker.close()
        self.assertNotIn(pid, [child.pid for child in multiprocessing.active_children()])


if __name__ == '__main__':
    unittest.main()
