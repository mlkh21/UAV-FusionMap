"""M1 optional diagnostic must not masquerade as resource acceptance."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros_ws'))
from m1_resource_observer import mapping_resource_report


def sample(timestamp, pid=23, role='perf01a_mapping', rss=100):
    return dict(monotonic_ns=timestamp, processes=[dict(pid=pid, created=1.,
                role=role, rss_bytes=rss, cpu_s=timestamp / 1e9)])


class M1ResourceObserverTest(unittest.TestCase):
    def test_peak_rss_is_only_sampled_local_fixture_rss(self):
        report = mapping_resource_report([sample(1, rss=100), sample(2, rss=150)], [])
        self.assertEqual(report['sample_count'], 2)
        self.assertEqual(report['rss_peak_sampled_bytes'], 150)
        self.assertFalse(report['formal_perf_validated'])
        self.assertFalse(report['hardware_validated'])
        self.assertFalse(report['power_validated'])

    def test_rejects_missing_coverage_restart_and_sampler_error(self):
        for rows, errors in (([sample(1)], []),
                             ([sample(1, role='observer'), sample(2, role='observer')], []),
                             ([sample(1), sample(2, pid=24)], []),
                             ([sample(2), sample(1)], []),
                             ([sample(1), sample(2)], ['lost sampler'])):
            with self.subTest(rows=rows, errors=errors), self.assertRaises(ValueError):
                mapping_resource_report(rows, errors)


if __name__ == '__main__':
    unittest.main()
