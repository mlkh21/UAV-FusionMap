"""分段必须闭合；轻量观察只能省略像素扫描，不能省略身份和丢帧校验。"""
import copy
import unittest
from unittest.mock import Mock, patch

from perf01a_timing import expected_timing, timing_report
from perf01a_validation import validate_receipts
from perf01a_compare import base_samples
from ufm_ros_contract.perf01a_ros import PerfTrace


PROFILE = dict(ir_resolution=[2, 2], fault='none')
ROOT = 'sensors.bundle:fixture.radar:r:0'


def events():
    intervals = dict(fixture_generation=(1, 4), infrared_generation=(2, 3),
        infrared_encode=(4, 5), infrared_publish=(5, 6), pairing=(6, 8),
        radar_encode=(8, 9), radar_publish=(9, 10), bundle_encode=(10, 12),
        bundle_publish=(12, 14), bundle_callback=(16, 16), bundle_decode=(17, 19),
        perception=(20, 22), occupancy_encode=(23, 24), occupancy_publish=(24, 25),
        occupancy_callback=(28, 28), occupancy_decode=(29, 30), map_update=(31, 33),
        map_snapshot=(34, 35), map_encode=(36, 37), map_publish=(38, 39))
    rows = [dict(parent_sample_id=ROOT, stage='timing.' + name, monotonic_ns=end,
                 metric_value_ns=end - start, business_timestamp=0, status='valid')
            for name, (start, end) in intervals.items()]
    rows.extend(dict(parent_sample_id=ROOT, stage=stage, monotonic_ns=stamp)
                for stage, stamp in [('radar_receive', 0), ('occupancy_ready', 23),
                                     ('map_snapshot_publish', 40)])
    return rows


class TimingTest(unittest.TestCase):
    def test_probe_off_comparison_uses_original_endpoints(self):
        rows = events()
        for row in rows:
            row.setdefault('status', 'valid')
        base = [r for r in rows if not r['stage'].startswith('timing.')]
        self.assertEqual(base_samples(rows), base_samples(base))
        self.assertEqual(base_samples(base), [dict(sensor_to_occupancy_ns=23, sensor_to_map_ns=40)])

    def test_critical_path_sums_without_double_counting_publish(self):
        report = timing_report(events(), expected_timing(1, PROFILE, 'r'), 50_000_000)
        self.assertEqual(report['errors'], [])
        sample = report['samples'][0]
        self.assertEqual(sum(sample['segments_ns'].values()), 40)
        self.assertEqual(sample['sensor_to_occupancy_ns'], 23)
        self.assertEqual(sample['segments_ns']['bundle_send_to_callback'], 4)
        self.assertEqual(report['spans_ns']['bundle_publish']['p99'], 2)

    def test_missing_duplicate_and_regressed_timing_fail(self):
        for rows in (events()[1:], events() + [events()[0]]):
            self.assertTrue(timing_report(rows, expected_timing(1, PROFILE, 'r'), 1)['errors'])
        rows = events()
        next(r for r in rows if r['stage'] == 'timing.bundle_callback')['monotonic_ns'] = 1
        self.assertTrue(timing_report(rows, expected_timing(1, PROFILE, 'r'), 1)['errors'])

    def test_rejected_sample_stages_keep_ir_missing_distinct(self):
        profile = dict(PROFILE, fault='ir_missing', start_sequence=0, stop_sequence=1,
                       expected_rejection='infrared_unavailable')
        self.assertEqual(expected_timing(1, profile, 'r')[ROOT],
                         {'fixture_generation', 'pairing', 'radar_encode', 'radar_publish'})

    def test_trace_defers_events_and_preserves_result(self):
        publisher = Mock()
        trace = PerfTrace(True)
        with patch('ufm_ros_contract.perf01a_ros.time.monotonic_ns', side_effect=[10, 15]):
            self.assertEqual(trace.call('pairing', lambda: 42), 42)
        publisher.publish.assert_not_called()
        trace.flush(publisher, 'r', ROOT, 0)
        event = publisher.publish.call_args[0][0]
        self.assertEqual((event.monotonic_ns, event.metric_value_ns), (15, 5))
        trace = PerfTrace(False)
        trace.call('pairing', lambda: 42)
        self.assertEqual(trace.spans, [])

    def test_light_preserves_count_identity_timestamp_and_shape(self):
        identities = dict(state='fixture.state:r:0', radar='fixture.radar:r:0',
            infrared='fixture.infrared:r:0', bundle=ROOT, occupancy='perception.occupancy:' + ROOT,
            map='map:1')
        records = {key: [dict(sample_id=value, timestamp=0, run_id='r', status=0)]
                   for key, value in identities.items()}
        for key in ('infrared', 'bundle'):
            records[key][0].update(image_shape=[2, 2], pixel_count=4)
        records['bundle'][0].update(radar_id=identities['radar'], infrared_id=identities['infrared'],
                                    radar_ir_delta_ns=0, pose_age_ns=0)
        records['map'][0].update(revision=1, cell_count=1, cells=[dict(observed=True, timestamp=0)])
        check = lambda data, mode: validate_receipts(data, 1, PROFILE, 'r', 50_000_000, mode)
        self.assertEqual(check(records, 'light'), [])
        self.assertIn('infrared: image payload differs', check(records, 'full'))
        for key, field, value in [('radar', 'sample_id', 'wrong'), ('state', 'timestamp', 1),
                                  ('bundle', 'pixel_count', 3)]:
            bad = copy.deepcopy(records)
            bad[key][0][field] = value
            self.assertTrue(check(bad, 'light'))
        records['map'] = []
        self.assertIn('map: count or identity mismatch', check(records, 'light'))
