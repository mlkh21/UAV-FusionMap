"""业务未采用与传输损失必须独立核账。"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ros_ws'))
from perf01a_async_report import (state_drain_ready, diagnose_oracle_reasons,
                                  summarize_async_wire, summarize_timing,
                                  transport_accounting, validate_maps)


class AsyncReportTest(unittest.TestCase):
    def test_endpoint_probe_reports_same_sample_downstream_endpoints(self):
        root = 'sensors.bundle:fixture.radar:r:0'
        def event(stage, end, duration=0):
            return dict(parent_sample_id=root, stage=stage, monotonic_ns=end,
                        metric_value_ns=duration, business_timestamp=0,
                        status='valid')
        events = [
            event('radar_receive', 0), event('sensor_bundle_ready', 10),
            event('occupancy_ready', 40), event('map_snapshot_publish', 72),
            event('timing.bundle_encode', 15, 5), event('timing.bundle_publish', 30, 15),
            event('timing.bundle_callback', 30, 0), event('timing.bundle_decode', 35, 5),
            event('timing.perception', 40, 5), event('timing.occupancy_publish', 50, 10),
            event('timing.occupancy_callback', 50, 0), event('timing.occupancy_decode', 52, 2),
            event('timing.map_update', 65, 10), event('timing.map_snapshot', 66, 1),
            event('timing.map_encode', 67, 1), event('timing.map_publish', 70, 3),
        ]
        decisions = [dict(radar_id='fixture.radar:r:0', reason='', timestamp=0)]
        producer = [dict(sample_id='fixture.radar:r:0', generated_monotonic_ns=0)]
        receipts = [dict(sample_id='fixture.radar:r:0', receive_monotonic_ns=0)]
        disabled = summarize_timing(events, decisions, producer, receipts)
        enabled = summarize_timing(events, decisions, producer, receipts, endpoint_probe=True)
        self.assertNotIn('endpoint_latencies_ns', disabled)
        self.assertEqual(enabled['endpoint_latencies_ns']['radar_to_occupancy_publish_call_ns']['p99'], 50.0)
        self.assertEqual(enabled['endpoint_latencies_ns']['radar_to_occupancy_callback_ns']['p99'], 50.0)
        self.assertEqual(enabled['endpoint_latencies_ns']['radar_to_map_update_end_ns']['p99'], 65.0)
        self.assertEqual(enabled['endpoint_latencies_ns']['radar_to_map_snapshot_publish_ns']['p99'], 72.0)

    def test_finish_requires_actual_source_clock_and_all_states_released(self):
        source = dict(state_count=221, last_ns=2_200_000_000)
        status = dict(run_id='r', received=221, published=219,
                      pending=2, clock_ns=2_180_000_000)
        self.assertFalse(state_drain_ready(source, dict(status, clock_ns=-1), 'r'))
        self.assertFalse(state_drain_ready(source, status, 'r'))
        status.update(published=221, pending=0)
        self.assertFalse(state_drain_ready(source, status, 'r'))
        status['clock_ns'] = source['last_ns']
        self.assertTrue(state_drain_ready(source, status, 'r'))
        status['clock_ns'] = str(source['last_ns'])
        self.assertTrue(state_drain_ready(source, status, 'r'))
        self.assertFalse(state_drain_ready(source, status, 'other'))

    def test_oracle_reason_diagnostic_keeps_strict_mismatch_visible(self):
        expected = {'19': dict(reason='infrared_unavailable', infrared_sequence=None)}
        decisions = [dict(radar_id='fixture.radar:r:19', infrared_id=None,
                          timestamp=950_000_000, reason='radar_ir_timeout',
                          decision_clock_ns=990_000_000, decision_monotonic_ns=1_467_000_000)]
        infrared = [dict(sample_id='fixture.infrared:r:24', timestamp_ns=480_000_000,
                         run_id='r', clock_id='sim:r', disposition='not_adopted',
                         received_clock_ns=521_000_000, received_ns=1_000_000_000,
                         terminal_ns=1_501_000_000, reason='wall_timeout')]
        diagnostic = diagnose_oracle_reasons(expected, decisions, infrared, 40_000_000,
                                             500_000_000, 5_000_000)
        self.assertEqual(diagnostic['mismatches'][0]['candidate_id'], infrared[0]['sample_id'])
        self.assertEqual(diagnostic['mismatches'][0]['classification'], 'wall_clock_carryover')
        self.assertEqual(diagnostic['strict_oracle_passed'], False)
        decisions[0]['decision_monotonic_ns'] = 1_501_000_000
        self.assertEqual(diagnose_oracle_reasons(expected, decisions, infrared, 40_000_000,
                     500_000_000, 5_000_000)['mismatches'][0]['classification'], 'unexplained')

    def test_wall_clock_diagnostic_fails_closed_for_invalid_candidate_evidence(self):
        expected = {'19': dict(reason='infrared_unavailable', infrared_sequence=None)}
        decision = dict(radar_id='fixture.radar:r:19', infrared_id=None,
                        timestamp=950_000_000, reason='radar_ir_timeout',
                        decision_clock_ns=990_000_000, decision_monotonic_ns=1_467_000_000)
        candidate = dict(sample_id='fixture.infrared:r:24', run_id='r', clock_id='sim:r',
                         timestamp_ns=480_000_000, received_clock_ns=521_000_000,
                         received_ns=1_000_000_000, terminal_ns=1_501_000_000,
                         disposition='not_adopted', reason='wall_timeout')
        for field, value in (('reason', 'infrared_overflow'), ('run_id', 'other'),
                             ('clock_id', 'sim:other'), ('disposition', 'adopted'),
                             ('terminal_ns', None), ('received_clock_ns', None),
                             ('sample_id', 'fixture.infrared:other:24')):
            with self.subTest(field=field):
                changed = dict(candidate, **{field: value})
                result = diagnose_oracle_reasons(expected, [decision], [changed],
                                                 40_000_000, 500_000_000, 5_000_000)
                self.assertEqual(result['mismatches'][0]['classification'], 'unexplained')

    def test_reason_diagnostic_requires_all_preregistered_radar_ids_once(self):
        expected = {0: dict(reason='radar_ir_timeout', infrared_sequence=None),
                    1: dict(reason='radar_ir_timeout', infrared_sequence=None)}
        decision = dict(radar_id='fixture.radar:r:0', infrared_id=None,
                        timestamp=0, reason='radar_ir_timeout')
        missing = diagnose_oracle_reasons(expected, [decision], [], 40, 500, 5)
        self.assertFalse(missing['strict_oracle_passed'])
        self.assertIn('missing_decision', [r['classification'] for r in missing['mismatches']])
        duplicate = diagnose_oracle_reasons(expected, [decision, decision], [], 40, 500, 5)
        self.assertFalse(duplicate['strict_oracle_passed'])
        self.assertIn('duplicate_decision', [r['classification'] for r in duplicate['mismatches']])

    def setUp(self):
        self.schedule = [dict(sequence=i, timestamp_ns=i * 20, arrival_ns=i * 20 + 2,
                              drop=i == 3) for i in range(5)]
        self.producer = dict(rows=[dict(r, sample_id='ir:%d' % r['sequence'],
                                       published=not r['drop']) for r in self.schedule])
        self.receipts = [dict(sample_id=r['sample_id'], timestamp=r['timestamp_ns'])
                         for r in self.producer['rows'] if r['published']]

    def test_unused_ir_and_injected_omissions_are_not_transport_losses(self):
        report = transport_accounting(self.schedule, self.producer, self.receipts, ['ir:0', 'ir:0'])
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['generated'], 5)
        self.assertEqual(report['received'], 4)
        self.assertEqual(report['adopted_unique'], 1)
        self.assertEqual(report['adoption_references'], 2)
        self.assertEqual(report['not_adopted'], 3)
        self.assertEqual(report['injected_missing'], 1)
        self.assertEqual(report['unexpected_lost'], 0)

    def test_real_loss_and_unpublished_reception_are_detected(self):
        report = transport_accounting(self.schedule, self.producer, self.receipts[1:], [])
        self.assertEqual(report['unexpected_lost_ids'], ['ir:0'])
        self.assertTrue(report['errors'])
        receipts = self.receipts + [dict(sample_id='ir:3', timestamp=60)]
        report = transport_accounting(self.schedule, self.producer, receipts, [])
        self.assertEqual(report['unexpected_received_ids'], ['ir:3'])

    def test_schedule_change_and_timestamp_rewrite_fail(self):
        producer = copy.deepcopy(self.producer)
        producer['rows'][0]['timestamp_ns'] = 999
        report = transport_accounting(self.schedule, producer, self.receipts, [])
        self.assertIn('generation schedule metadata differs', report['errors'])
        self.assertIn('sampling timestamp changed in transport', report['errors'])

    def test_extra_map_after_rejected_input_fails(self):
        records = dict(bundle=[], occupancy=[], map=[dict(timestamp=0, sample_id='map',
            run_id='r', clock_id='sim:r', status=0, revision=1, cells=[])])
        errors = validate_maps(records, [], 'r')
        self.assertIn('map: reference timestamps differ', errors)
        self.assertIn('map: occupied/unknown semantics changed', errors)

    def test_dynamic_expected_cell_is_checked_without_stationary_hardcode(self):
        root = 'sensors.bundle:radar:0'
        header = dict(timestamp=100_000_000, run_id='r', clock_id='sim:r', status=0)
        decision = dict(radar_id='radar:0', infrared_id='ir:0', timestamp=100_000_000, reason='')
        records = dict(
            bundle=[dict(header, sample_id=root, radar_id='radar:0', infrared_id='ir:0',
                         radar_timestamp=100_000_000, infrared_timestamp=100_000_000,
                         state_timestamp=100_000_000, radar_ir_delta_ns=0, pose_age_ns=0)],
            occupancy=[dict(header, sample_id='perception.occupancy:' + root)],
            map=[dict(header, sample_id='map', revision=1,
                      cells=[dict(index=[32, 36, 8], probability=.9, observed=True,
                                  timestamp=100_000_000)])])
        self.assertEqual(validate_maps(records, [decision], 'r',
                                       expected_cells={100_000_000: [32, 36, 8]}), [])
        self.assertIn('map: occupied/unknown semantics changed',
                      validate_maps(records, [decision], 'r'))

    def test_radar_point_map_oracle_accepts_cumulative_noisy_cells(self):
        root = 'sensors.bundle:radar:0'
        header = dict(timestamp=100_000_000, run_id='r', clock_id='sim:r', status=0)
        decision = dict(radar_id='radar:0', infrared_id='ir:0', timestamp=100_000_000, reason='')
        identity = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
        records = dict(
            bundle=[dict(header, sample_id=root, radar_id='radar:0', infrared_id='ir:0',
                         radar_timestamp=100_000_000, infrared_timestamp=100_000_000,
                         state_timestamp=100_000_000, radar_ir_delta_ns=0, pose_age_ns=0,
                         radar_points=[[4.01, 0., 0.]], radar_to_odom=identity)],
            occupancy=[dict(header, sample_id='perception.occupancy:' + root)],
            map=[dict(header, sample_id='map', revision=1,
                      cells=[dict(index=[40, 16, 8], probability=.9, observed=True,
                                  timestamp=100_000_000)])])
        self.assertEqual(validate_maps(records, [decision], 'r', map_oracle='radar_points'), [])
        changed = copy.deepcopy(records)
        changed['map'][0]['cells'][0]['index'] = [39, 16, 8]
        self.assertIn('map: dynamic occupied cell set changed',
                      validate_maps(changed, [decision], 'r', map_oracle='radar_points'))

    def test_rewritten_child_timestamps_cannot_hide_behind_declared_ages(self):
        root = 'sensors.bundle:radar:0'
        header = dict(timestamp=100_000_000, run_id='r', clock_id='sim:r', status=0)
        decision = dict(radar_id='radar:0', infrared_id='ir:0', timestamp=100_000_000, reason='')
        bundle = dict(header, sample_id=root, radar_id='radar:0', infrared_id='ir:0',
                      radar_timestamp=100_000_000, infrared_timestamp=100_000_000,
                      state_timestamp=100_000_000, radar_ir_delta_ns=0, pose_age_ns=0)
        records = dict(bundle=[bundle], occupancy=[dict(header, sample_id='perception.occupancy:' + root)],
                       map=[dict(header, sample_id='map', revision=1, cells=[dict(index=[32, 24, 8],
                           probability=.9, observed=True, timestamp=100_000_000)])])
        self.assertEqual(validate_maps(records, [decision], 'r'), [])
        for field in ('infrared_timestamp', 'state_timestamp', 'radar_timestamp'):
            changed = copy.deepcopy(records)
            changed['bundle'][0][field] = 999_000_000
            self.assertIn('bundle: chosen input or time gate mismatch', validate_maps(changed, [decision], 'r'))

    def test_async_wire_chain_has_identity_and_nonoverlapping_intervals(self):
        def wire(sample, operation, start, end, size=64):
            return dict(sample_id=sample, operation=operation, start_ns=start,
                        end_ns=end, thread_cpu_ns=end-start, wire_bytes=size)
        audits = dict(infrared=dict(rows=[wire('ir:0', 'serialize:InfraredFrame', 10, 20)]),
                      sensor=dict(rows=[wire('ir:0', 'deserialize:InfraredFrame', 30, 40),
                                        dict(sample_id='ir:0', operation='callback:InfraredFrame', callback_ns=42),
                                        wire('sensors.bundle:radar:0', 'serialize:SensorBundle', 60, 70)]),
                      perception=dict(rows=[wire('sensors.bundle:radar:0',
                                                 'deserialize:SensorBundle', 80, 90, 128)]))
        audits['sensor']['rows'][-1]['wire_bytes'] = 128
        audits['perception']['rows'].append(dict(sample_id='sensors.bundle:radar:0',
                                                 operation='callback:SensorBundle', callback_ns=95))
        receipts = [dict(sample_id='ir:0', receive_monotonic_ns=42,
                         lock_wait_ns=3, decode_ns=2, cache_and_emit_ns=4)]
        decisions = [dict(radar_id='radar:0', infrared_id='ir:0', reason='')]
        report = summarize_async_wire(audits, receipts, decisions)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['infrared']['serialized_to_deserialize_ns']['p99'], 10)
        self.assertEqual(report['infrared']['deserialize_to_callback_ns']['p99'], 2)
        self.assertEqual(report['bundle']['serialized_to_deserialize_ns']['p99'], 10)
        self.assertEqual(report['bundle']['deserialize_to_callback_ns']['p99'], 5)
        altered = copy.deepcopy(audits)
        altered['perception']['rows'][0]['sample_id'] = 'other'
        self.assertTrue(summarize_async_wire(altered, receipts, decisions)['errors'])
        altered = copy.deepcopy(audits)
        altered['sensor']['rows'][0]['start_ns'] = 15
        self.assertTrue(summarize_async_wire(altered, receipts, decisions)['errors'])


if __name__ == '__main__':
    unittest.main()
