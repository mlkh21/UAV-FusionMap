"""性能统计不得用重复拒绝掩盖丢失，也不得接受负阶段时延。"""
import unittest
from perf01a_metrics import PerfAggregator


def event(root, stage, stamp, status='valid'):
    return dict(run_id='r', clock_id='sim:r', sample_id=root + ':' + stage,
                parent_sample_id=root, stage=stage, monotonic_ns=stamp,
                metric_value_ns=0, business_timestamp=0, status=status, reason='')


class MetricsTest(unittest.TestCase):
    def test_rejection_cannot_cancel_another_dropped_frame(self):
        metrics = PerfAggregator('r')
        for root in ('a', 'b'):
            metrics.record(event(root, 'radar_receive', 1))
        metrics.record(event('a', 'sensor_bundle_ready', 2, 'timeout'))
        metrics.record(event('a', 'occupancy_ready', 3, 'unavailable'))
        report = metrics.report()
        self.assertEqual(report['drop_rate'], 1.)
        self.assertEqual(report['explicit_rejections'], 1)

    def test_negative_latency_and_duplicate_events_fail(self):
        metrics = PerfAggregator('r')
        for stage, stamp in zip(('radar_receive', 'sensor_bundle_ready', 'occupancy_ready',
                                 'map_snapshot_publish'), (2, 1, 3, 4)):
            metrics.record(event('a', stage, stamp))
        self.assertEqual(metrics.report()['closed_samples'], 0)
        self.assertIn('stage_time_regression', metrics.report()['errors'])
        metrics.record(event('a', 'radar_receive', 2))
        self.assertIn('duplicate_event', metrics.report()['errors'])
