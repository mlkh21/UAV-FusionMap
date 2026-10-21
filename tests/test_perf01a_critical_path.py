"""Read-only critical-path join must reject missing or inconsistent evidence."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros_ws'))
from perf01a_critical_path import analyze, analyze_match_trace, analyze_stages, analyze_wait_trace


class CriticalPathTest(unittest.TestCase):
    def setUp(self):
        self.root = 'sensors.bundle:radar:0'
        self.report = dict(run_id='r', passed=True, errors=[], wire=dict(errors=[]),
                           segmented=dict(errors=[], samples=[dict(root=self.root,
                               sensor_to_occupancy_ns=20, segments_ns=dict(pairing_wait_and_build=8))]))
        self.matcher = dict(run_id='r', errors=[], receipts=dict(
            radar=[dict(sample_id='radar:0', timestamp=100, receive_monotonic_ns=2)],
            infrared=[dict(sample_id='ir:0', timestamp=100, receive_monotonic_ns=6,
                           lock_wait_ns=1, decode_ns=1, cache_and_emit_ns=1)]),
            decisions=[dict(radar_id='radar:0', infrared_id='ir:0', timestamp=100,
                            reason='', decision_monotonic_ns=10)])
        self.producer = dict(run_id='r', rows=[dict(sample_id='ir:0', published=True,
                           generated_monotonic_ns=0, publish_monotonic_ns=1)])
        self.ir_wire = dict(rows=[dict(sample_id='ir:0', operation='serialize:InfraredFrame',
                                       timestamp=100, start_ns=2, end_ns=3, wire_bytes=100)])
        self.sensor_wire = dict(rows=[dict(sample_id='ir:0', operation='deserialize:InfraredFrame',
                                           start_ns=4, end_ns=5, wire_bytes=100),
                                      dict(sample_id='ir:0', operation='callback:InfraredFrame',
                                           callback_ns=6),
                                      dict(sample_id=self.root, operation='serialize:SensorBundle',
                                           infrared_id='ir:0', start_ns=12, end_ns=13, wire_bytes=120)])
        self.perception_wire = dict(rows=[dict(sample_id=self.root,
                                               operation='deserialize:SensorBundle',
                                               infrared_id='ir:0', start_ns=14, end_ns=15, wire_bytes=120),
                                          dict(sample_id=self.root, operation='callback:SensorBundle',
                                               callback_ns=16)])

    def analyze(self):
        return analyze(self.report, self.matcher, self.producer, self.ir_wire,
                       self.sensor_wire, self.perception_wire)

    def test_join_tracks_signed_arrival_and_closed_boundaries(self):
        row = self.analyze()['samples'][0]
        self.assertEqual(row['ir_callback_minus_radar_callback_ns'], 4)
        self.assertEqual(row['parts_ns']['last_input_callback_to_decision_ns'], 4)
        self.assertEqual(row['parts_ns']['bundle_queue_transport_schedule_ns'], 1)
        self.assertEqual(self.analyze()['sensor_to_occupancy_ns']['p99'], 20.0)

    def test_missing_duplicate_mismatched_and_failed_input_rejected(self):
        cases = [lambda: self.ir_wire['rows'].clear(),
                 lambda: self.ir_wire['rows'].append(copy.deepcopy(self.ir_wire['rows'][0])),
                 lambda: self.sensor_wire['rows'][0].update(wire_bytes=99),
                 lambda: self.report.update(passed=False),
                 lambda: self.matcher['decisions'].append(copy.deepcopy(self.matcher['decisions'][0]))]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                fixtures = copy.deepcopy((self.report, self.matcher, self.producer, self.ir_wire,
                                          self.sensor_wire, self.perception_wire))
                try:
                    mutate()
                    with self.assertRaises((ValueError, KeyError)):
                        self.analyze()
                finally:
                    (self.report, self.matcher, self.producer, self.ir_wire,
                     self.sensor_wire, self.perception_wire) = fixtures

    def test_wall_clock_regression_is_not_clamped(self):
        self.perception_wire['rows'][0]['start_ns'] = 12
        with self.assertRaisesRegex(ValueError, 'wall-clock stage order'):
            self.analyze()

    def test_valid_nonzero_sampling_offset_retains_radar_reference(self):
        self.matcher['receipts']['infrared'][0]['timestamp'] = 105
        self.ir_wire['rows'][0]['timestamp'] = 105
        self.assertEqual(self.analyze()['count'], 1)

    def test_match_trace_joins_exact_state_clock_worker_and_rejects_missing_lock(self):
        self.report['profile'] = dict(pairing_policy='exact')
        self.matcher['match_trace'] = dict(locks=[
            dict(lock_id=0, role='clock', timestamp=100, entered_ns=0,
                 acquired_ns=0, released_ns=1),
            dict(lock_id=1, role='state', timestamp=100, entered_ns=1,
                 acquired_ns=1, released_ns=4),
            dict(lock_id=3, role='radar', timestamp=100, entered_ns=1,
                 acquired_ns=1, released_ns=4),
            dict(lock_id=4, role='infrared', timestamp=100, entered_ns=5,
                 acquired_ns=5, released_ns=7),
            dict(lock_id=2, role='worker', timestamp=100, entered_ns=7,
                 acquired_ns=8, released_ns=11)],
            state_inputs=[dict(sample_id='state:0', timestamp=100, begin_ns=2, matcher_end_ns=3,
                               end_ns=3, lock_id=1)],
            sensor_inputs=[dict(kind='radar', sample_id='radar:0', timestamp=100,
                                begin_ns=2, matcher_end_ns=3, end_ns=3, lock_id=3),
                           dict(kind='infrared', sample_id='ir:0', timestamp=100,
                                begin_ns=6, matcher_end_ns=7, end_ns=7, lock_id=4)])
        self.matcher['decisions'][0]['trigger'] = dict(source='advance', begin_ns=9, lock_id=2)
        row = analyze_match_trace(self.report, self.matcher)['samples'][0]
        self.assertEqual(row['last_required_input_ns'], 7)
        self.assertEqual(row['ready_to_worker_lock_ns'], 1)
        self.assertEqual(row['worker_lock_to_decision_ns'], 2)
        self.assertEqual(row['lock_held_since_ready_ns'], dict(worker=2))
        self.matcher['match_trace']['locks'] = [r for r in self.matcher['match_trace']['locks']
                                               if r['lock_id'] != 2]
        with self.assertRaises(KeyError):
            analyze_match_trace(self.report, self.matcher)

    def test_stage_trace_requires_released_lock_and_keeps_cpu_separate(self):
        locks = {3: dict(lock_id=3, role='state', timestamp=100, sample_id='state:0',
                         acquired_ns=10, released_ns=40)}
        rows = [dict(name='state.publish', lock_id=3, sample_id='state:0',
                     start_ns=12, end_ns=35, thread_cpu_ns=2)]
        result = analyze_stages(rows, locks)
        self.assertEqual(result['by_name']['state.publish']['wall_ns']['p99'], 23)
        self.assertEqual(result['by_name']['state.publish']['thread_cpu_ns']['p99'], 2)
        for field, value in (('lock_id', 4), ('end_ns', 41), ('thread_cpu_ns', -1)):
            bad = dict(rows[0], **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                analyze_stages([bad], locks)

    def test_wait_trace_distinguishes_sleep_lock_and_uncovered_cpu(self):
        locks = {0: dict(lock_id=0, role='clock', acquired_ns=10, released_ns=30,
                         cpu_acquired_ns=4, cpu_released_ns=19, lock_thread_cpu_ns=15),
                 1: dict(lock_id=1, role='worker', entered_ns=32, acquired_ns=34,
                         released_ns=44, cpu_acquired_ns=20, cpu_released_ns=28,
                         lock_thread_cpu_ns=8)}
        trace = dict(worker_polls=[dict(lock_id=1, sleep_start_ns=0, wake_ns=31,
                                        sleep_thread_cpu_ns=1)], stages=[
            dict(lock_id=0, name='gate.consume_clock', start_ns=12, end_ns=22,
                 thread_cpu_start_ns=5, thread_cpu_end_ns=13, thread_cpu_ns=8),
            dict(lock_id=1, name='matcher.advance', start_ns=35, end_ns=41,
                 thread_cpu_start_ns=21, thread_cpu_end_ns=26, thread_cpu_ns=5)])
        result = analyze_wait_trace(trace, locks)
        self.assertEqual(result['lock_gaps'][0], dict(wall_ns=10, thread_cpu_ns=7))
        self.assertEqual(result['lock_gaps'][1], dict(wall_ns=4, thread_cpu_ns=3))
        self.assertEqual(result['worker_polls'][1]['wake_ns'], 31)
        nested = dict(lock_id=0, name='matcher.inner', start_ns=13, end_ns=20,
                      thread_cpu_start_ns=6, thread_cpu_end_ns=11, thread_cpu_ns=5)
        trace['stages'].append(nested)
        self.assertEqual(analyze_wait_trace(trace, locks)['lock_gaps'][0],
                         dict(wall_ns=10, thread_cpu_ns=7))
        trace['stages'].pop()
        trace['worker_polls'].clear()
        with self.assertRaisesRegex(ValueError, 'worker poll/lock identity'):
            analyze_wait_trace(trace, locks)
        trace['worker_polls'].append(dict(lock_id=1, sleep_start_ns=0, wake_ns=31,
                                          sleep_thread_cpu_ns=1))
        trace['stages'][0]['thread_cpu_end_ns'] = 20
        with self.assertRaisesRegex(ValueError, 'stage thread CPU boundary'):
            analyze_wait_trace(trace, locks)
        trace['stages'][0]['thread_cpu_end_ns'] = 13
        trace['worker_polls'][0]['wake_ns'] = 33
        with self.assertRaises(ValueError):
            analyze_wait_trace(trace, locks)
