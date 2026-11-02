"""PERF-01-A async contract: independent samples, bounded payloads and accounting."""
import gc
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import weakref

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sensors'))
sys.path.insert(0, str(ROOT / 'ros_ws'))
sys.path.insert(0, str(ROOT / 'simulation'))

from ufm_sensors.perf01a_async import BoundedMatcher, load_profile, make_schedule, expected_matches
from ufm_sensors.perf01a_fixture import make_fake_infrared, make_fake_radar
from ufm_simulation.perf01a_fixture import make_fixture_state
from ufm_sensors.state_adapter import adapt_state
from online_graph_audit import EXPECTED_ONLINE_NODES, validate_online_graph

MS = 1_000_000
CONFIG = ROOT / 'configs/perf01a_async.yaml'


def load_config(path, name='normal'):
    return load_profile(name, path)


def nearest_expected(profile, duration_ns):
    expected = expected_matches(profile, duration_ns)
    return {'pairs': {r: row['infrared_sequence'] for r, row in expected.items() if not row['reason']},
            'rejections': {r: row['reason'] for r, row in expected.items() if row['reason']}}


def pose(sequence, timestamp):
    return adapt_state(make_fixture_state('r', sequence, timestamp), {
        'odom_origin_policy': 'px4_estimator_local_origin',
        'body_origin_policy': 'source_body_virtual_flu'})


def sequence(frame):
    return int(frame['header']['sample_id'].rsplit(':', 1)[1])


def replay(profile, duration_ns, poll_mode='after'):
    """Drive 1ms source ticks and independent 100Hz states, including drain."""
    schedule = make_schedule(profile, duration_ns)
    pending = sorted((sample['arrival_ns'], kind, sample['sequence'], sample)
                     for kind, samples in schedule.items() for sample in samples if not sample['drop'])
    matcher = BoundedMatcher('r', profile)
    decisions = []
    index = 0
    for stamp in range(0, duration_ns + 200 * MS + 1, MS):
        decisions.extend(matcher.observe_clock(stamp, stamp))
        if poll_mode in ('before', 'each'):
            decisions.extend(matcher.advance(stamp, stamp))
        if stamp % (10 * MS) == 0:
            decisions.extend(matcher.add_state(pose(stamp // (10 * MS), stamp), stamp))
        while index < len(pending) and pending[index][0] <= stamp:
            _, kind, _, sample = pending[index]
            index += 1
            if poll_mode == 'each':
                decisions.extend(matcher.advance(stamp, stamp))
            timestamp = sample['timestamp_ns']
            if kind == 'infrared':
                decisions.extend(matcher.add_infrared(make_fake_infrared('r', sample['sequence'], timestamp), stamp))
            else:
                decisions.extend(matcher.add_radar(make_fake_radar('r', sample['sequence'], timestamp), stamp))
            if poll_mode == 'each':
                decisions.extend(matcher.advance(stamp, stamp))
        if poll_mode in ('after', 'each'):
            decisions.extend(matcher.advance(stamp, stamp))
    if index != len(pending):
        raise AssertionError('source drain does not cover planned arrivals')
    decisions.extend(matcher.finish(stamp))
    return matcher, decisions, schedule


class ScheduleTest(unittest.TestCase):
    def test_exact_policy_closes_only_when_same_time_inputs_exist(self):
        profile = load_config(CONFIG)
        profile['pairing_policy'] = 'exact'
        matcher, decisions, _ = replay(profile, 2000 * MS)
        self.assertEqual({sequence(d['radar']): d['reason'] for d in decisions},
                         {seq: row['reason'] for seq, row in expected_matches(profile, 2000 * MS).items()})
        self.assertEqual(sum(not d['reason'] for d in decisions), 20)
        self.assertEqual(matcher.audit()['counts']['radar']['received'], 40)

        matcher = BoundedMatcher('r', profile)
        matcher.observe_clock(100 * MS, 0)
        matcher.add_state(pose(10, 100 * MS), 0)
        matcher.add_radar(make_fake_radar('r', 2, 100 * MS), 0)
        self.assertEqual(matcher.advance(110 * MS, MS), [])
        matcher.add_infrared(make_fake_infrared('r', 5, 100 * MS), MS)
        early, = matcher.advance(110 * MS, MS)
        self.assertIsNotNone(early['bundle'])
        self.assertEqual(early['data_age_ns'], 10 * MS)
        self.assertEqual(matcher.cache_sizes['radar'], 0)

        matcher = BoundedMatcher('r', profile)
        matcher.observe_clock(100 * MS, 0)
        matcher.add_state(pose(10, 100 * MS), 0)
        matcher.add_radar(make_fake_radar('r', 2, 100 * MS), 0)
        matcher.observe_clock(141 * MS, MS)
        matcher.add_infrared(make_fake_infrared('r', 5, 100 * MS), MS)
        late, = matcher.advance(141 * MS, MS)
        self.assertEqual(late['reason'], 'infrared_unavailable')
        self.assertIsNone(late['bundle'])

    def test_producer_capacity_default_and_validation(self):
        profile = load_config(CONFIG)
        self.assertEqual(profile['producer_capacity'], 16)
        for capacity in (0, -1, True, 1.5):
            with self.subTest(capacity=capacity), self.assertRaisesRegex(ValueError, 'producer_capacity'):
                BoundedMatcher('r', dict(profile, producer_capacity=capacity))

    def test_independent_rates_and_normal_analytical_oracle(self):
        profile = load_config(CONFIG, 'normal')
        schedule = make_schedule(profile, 1_000 * MS)
        self.assertEqual([s['timestamp_ns'] for s in schedule['radar']], list(range(0, 1000 * MS, 50 * MS)))
        self.assertEqual([s['timestamp_ns'] for s in schedule['infrared']], list(range(0, 1000 * MS, 20 * MS)))
        expected = nearest_expected(profile, 1000 * MS)
        self.assertEqual(expected['pairs'], {r: r * 5 // 2 for r in range(0, 20, 2)})
        self.assertEqual(expected['rejections'], {r: 'radar_ir_timeout' for r in range(1, 20, 2)})

    def test_phase_offset_is_five_ms_boundary(self):
        expected = nearest_expected(load_config(CONFIG, 'phase_offset'), 1000 * MS)
        self.assertEqual(expected['pairs'], {r: (r * 50) // 20 for r in range(20)})
        self.assertEqual(expected['rejections'], {})

    def test_faults_are_deterministic_and_have_real_arrival_inversion(self):
        jitter = load_config(CONFIG, 'jitter')
        self.assertEqual(make_schedule(jitter, 2_000 * MS), make_schedule(jitter, 2_000 * MS))
        self.assertNotEqual(make_schedule(jitter, 2_000 * MS)['infrared'],
                            make_schedule(load_config(CONFIG), 2_000 * MS)['infrared'])
        schedule = make_schedule(load_config(CONFIG, 'out_of_order'), 2_000 * MS)
        for samples in schedule.values():
            self.assertTrue(any(a['arrival_ns'] > b['arrival_ns'] for a, b in zip(samples, samples[1:])))
        missing = make_schedule(load_config(CONFIG, 'missing'), 2_000 * MS)
        self.assertTrue(any(s['drop'] for s in missing['infrared']))
        self.assertFalse(any(s['drop'] for s in missing['radar']))

    def test_all_scenes_against_independent_oracle_and_recovery(self):
        accepted_counts = dict(normal=20, phase_offset=40, jitter=20,
                               out_of_order=15, missing=15, overflow=20, recovery=12)
        for name in accepted_counts:
            with self.subTest(scene=name):
                profile = load_config(CONFIG, name)
                with patch.object(BoundedMatcher, '__init__', side_effect=AssertionError('oracle invoked matcher')):
                    expected = nearest_expected(profile, 2000 * MS)
                matcher, decisions, schedule = replay(profile, 2000 * MS)
                pairs = {sequence(d['radar']): sequence(d['bundle']['infrared'])
                         for d in decisions if d['bundle'] is not None}
                rejected = {sequence(d['radar']): d['reason'] for d in decisions if d['bundle'] is None}
                self.assertEqual(pairs, expected['pairs'])
                self.assertEqual(rejected, expected['rejections'])
                self.assertEqual(len(pairs), accepted_counts[name])
                recovery = [s['sequence'] for s in schedule['radar']
                            if s['timestamp_ns'] >= profile['recovery_start_ns']]
                self.assertTrue(recovery)
                self.assertTrue(any(s in pairs for s in recovery))
                for index in recovery:
                    self.assertEqual(index in pairs, name == 'phase_offset' or
                                     schedule['radar'][index]['timestamp_ns'] % (100 * MS) == 0)
                self.assertEqual(matcher.cache_sizes, {'radar': 0, 'infrared': 0, 'state': 0})
                audit = matcher.audit(schedule)
                for kind in ('radar', 'infrared'):
                    counts = audit['counts'][kind]
                    self.assertEqual(counts['generated'], len(schedule[kind]))
                    self.assertEqual(counts['generated'], counts['received'] + counts['declared_dropped'])
                    self.assertEqual(counts['received'], counts['adopted'] + counts['not_adopted'])
                    self.assertEqual(counts['unexpected_missing'], 0)
                    self.assertEqual(counts['pending'], 0)
                if name == 'overflow':
                    self.assertIn('radar_overflow', rejected.values())

    def test_overflow_is_extra_sampling_before_deadline_and_recovers_baseline(self):
        profile = load_config(CONFIG, 'overflow')
        schedule = make_schedule(profile, 2000 * MS)
        timestamps = [s['timestamp_ns'] for s in schedule['radar']]
        self.assertEqual(timestamps, sorted(list(range(0, 2000 * MS, 50 * MS)) +
                                           list(range(501 * MS, 513 * MS, MS))))
        self.assertEqual([s['sequence'] for s in schedule['radar']], list(range(52)))
        self.assertTrue(all(s['arrival_ns'] == s['timestamp_ns'] for s in schedule['radar']))
        self.assertEqual(sum(s.get('injected_burst', False) for s in schedule['radar']), 12)
        expected = expected_matches(profile, 2000 * MS)
        self.assertEqual([r['timestamp_ns'] for r in expected.values() if r['reason'] == 'radar_overflow'],
                         list(range(500 * MS, 505 * MS, MS)))
        reference = None
        for mode in ('after', 'before', 'each'):
            with self.subTest(poll_mode=mode):
                matcher, decisions, _ = replay(profile, 2000 * MS, mode)
                actual = {sequence(d['radar']): dict(
                    timestamp_ns=d['radar']['header']['timestamp'], reason=d['reason'],
                    infrared_sequence=sequence(d['bundle']['infrared']) if d['bundle'] else None)
                    for d in decisions}
                self.assertEqual(actual, expected)
                overflow = [d for d in decisions if d['reason'] == 'radar_overflow']
                self.assertEqual(len(overflow), 5)
                self.assertTrue(all(d['data_age_ns'] < profile['max_wait_ns'] for d in overflow))
                self.assertEqual(matcher.audit()['high_water']['radar'], 8)
                ordering = [sequence(d['radar']) for d in decisions]
                if reference is not None:
                    self.assertEqual(ordering, reference)
                reference = ordering

    def test_oracle_models_100hz_state_eviction_not_one_state_per_radar(self):
        profile = dict(load_config(CONFIG), state_capacity=4)
        oracle = expected_matches(profile, 1000 * MS)
        # At t=40ms the 0ms pose is evicted by the fifth 100Hz state.
        self.assertEqual(oracle[0]['reason'], 'pose_unavailable')
        _, decisions, _ = replay(profile, 1000 * MS)
        self.assertEqual({sequence(d['radar']): d['reason'] for d in decisions},
                         {i: row['reason'] for i, row in oracle.items()})
        self.assertTrue(all(row['reason'] for row in oracle.values()))

    def test_jitter_uses_100hz_historical_pose_and_nonzero_age(self):
        profile = load_config(CONFIG, 'jitter')
        matcher, decisions, _ = replay(profile, 2000 * MS)
        bundles = [d['bundle'] for d in decisions if d['bundle']]
        self.assertTrue(any(0 < b['pose_age_ns'] < 10 * MS for b in bundles))
        for bundle in bundles:
            timestamp = bundle['header']['timestamp']
            self.assertEqual(bundle['state']['header']['timestamp'], timestamp // (10 * MS) * (10 * MS))
        self.assertEqual(matcher.audit()['counts']['state']['received'], 221)

    def test_out_of_order_rejects_radar_after_arrival_deadline(self):
        expected = expected_matches(load_config(CONFIG, 'out_of_order'), 2000 * MS)
        self.assertEqual([i for i, row in expected.items() if row['reason'] == 'arrival_deadline_exceeded'],
                         [10, 12, 14, 16, 18])

    def test_recovery_has_long_ir_outage_then_fresh_pairs(self):
        profile = load_config(CONFIG, 'recovery')
        self.assertGreater(profile['fault_stop_ns'] - profile['fault_start_ns'],
                           profile['max_wall_wait_ns'])
        matcher, decisions, schedule = replay(profile, 2000 * MS)
        outage = [d for d in decisions if profile['fault_start_ns'] <=
                  d['radar']['header']['timestamp'] < profile['fault_stop_ns']]
        self.assertTrue(any(d['reason'] == 'infrared_unavailable' for d in outage))
        recovered = [d for d in decisions if d['bundle'] and
                     d['radar']['header']['timestamp'] >= profile['recovery_start_ns']]
        self.assertGreater(len(recovered), 2)
        self.assertTrue(all(d['bundle']['infrared']['header']['timestamp'] >= profile['fault_stop_ns']
                            for d in recovered))
        self.assertEqual(matcher.audit(schedule)['counts']['infrared']['unexpected_missing'], 0)


class MatcherTest(unittest.TestCase):
    def setUp(self):
        self.config = load_config(CONFIG)
        self.matcher = BoundedMatcher('r', self.config)

    def prime(self, timestamp=100 * MS):
        self.matcher.add_state(pose(1, timestamp), 0)
        self.matcher.add_radar(make_fake_radar('r', 1, timestamp), 0)

    def test_observe_clock_records_receipt_cutoff_without_eager_matching(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('r', 1, 100 * MS), 0)
        self.assertEqual(self.matcher.observe_clock(140 * MS, 1), [])
        late = make_fake_infrared('r', 2, 101 * MS)
        self.matcher.observe_clock(141 * MS, 2)
        self.matcher.add_infrared(late, 3)
        row = self.matcher.audit()['records']['infrared'][late['header']['sample_id']]
        self.assertEqual(row['received_clock_ns'], 141 * MS)
        decision, = self.matcher.advance(141 * MS, 4)
        self.assertEqual(decision['reason'], '')
        self.assertEqual(decision['data_age_ns'], 41 * MS)
        self.assertEqual(sequence(decision['bundle']['infrared']), 1)

    def test_delayed_poll_cannot_salvage_late_ir(self):
        self.matcher.observe_clock(100 * MS, 0)
        self.prime()
        self.matcher.observe_clock(141 * MS, 1)
        self.matcher.add_infrared(make_fake_infrared('r', 1, 100 * MS), 2)
        decision, = self.matcher.advance(141 * MS, 3)
        self.assertEqual(decision['reason'], 'infrared_unavailable')
        self.assertEqual(decision['data_age_ns'], 41 * MS)

    def test_preclock_receipt_needs_a_real_clock_bound_before_deadline(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('r', 0, 100 * MS), 0)
        self.matcher.observe_clock(141 * MS, 1)
        decision, = self.matcher.advance(141 * MS, 2)
        self.assertEqual(decision['reason'], 'arrival_deadline_exceeded')
        row, = self.matcher.audit()['records']['infrared'].values()
        self.assertIsNone(row['received_clock_ns'])

    def test_preclock_radar_deadline_checked_on_advance_and_eof(self):
        for first_clock, reason in ((140 * MS, ''), (140 * MS + 1, 'arrival_deadline_exceeded'),
                                    (142 * MS, 'arrival_deadline_exceeded')):
            for finish in (False, True):
                with self.subTest(first_clock=first_clock, finish=finish):
                    matcher = BoundedMatcher('r', self.config)
                    radar = make_fake_radar('r', 0, 100 * MS)
                    matcher.add_state(pose(0, 100 * MS), 0)
                    matcher.add_radar(radar, 0)
                    matcher.add_infrared(make_fake_infrared('r', 0, 100 * MS), 0)
                    self.assertEqual(matcher.observe_clock(first_clock, 1), [])
                    decisions = matcher.finish(2) if finish else matcher.advance(first_clock, 2)
                    decision, = decisions
                    self.assertEqual(decision['reason'], reason)
                    self.assertEqual(decision['bundle'] is None, bool(reason))
                    self.assertEqual(decision['data_age_ns'], first_clock - 100 * MS)
                    row = matcher.audit()['records']['radar'][radar['header']['sample_id']]
                    self.assertIsNone(row['received_clock_ns'])
                    self.assertEqual(row['disposition'], 'not_adopted' if reason else 'adopted')

    def test_preclock_radar_timely_first_clock_survives_delayed_decision(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('r', 0, 100 * MS), 0)
        self.matcher.observe_clock(139 * MS, 1)
        decision, = self.matcher.advance(142 * MS, 2)
        self.assertEqual(decision['reason'], '')
        self.assertIsNotNone(decision['bundle'])
        self.assertEqual(decision['data_age_ns'], 42 * MS)

    def test_historical_state_must_arrive_before_radar_deadline(self):
        for receipt_clock, reason in ((140 * MS, ''), (141 * MS, 'pose_unavailable')):
            with self.subTest(receipt_clock=receipt_clock):
                matcher = BoundedMatcher('r', self.config)
                matcher.observe_clock(100 * MS, 0)
                matcher.add_radar(make_fake_radar('r', 0, 100 * MS), 0)
                matcher.add_infrared(make_fake_infrared('r', 0, 100 * MS), 0)
                matcher.observe_clock(receipt_clock, 1)
                matcher.add_state(pose(0, 100 * MS), 1)
                decision, = matcher.advance(142 * MS, 2)
                self.assertEqual(decision['reason'], reason)
                self.assertEqual(decision['bundle'] is None, bool(reason))

    def test_radar_arrival_deadline_is_inclusive_and_distinct_from_watermark(self):
        for arrival, reason in ((140 * MS, ''), (140 * MS + 1, 'arrival_deadline_exceeded')):
            with self.subTest(arrival=arrival):
                matcher = BoundedMatcher('r', self.config)
                matcher.observe_clock(100 * MS, 0)
                matcher.add_state(pose(0, 100 * MS), 0)
                matcher.add_infrared(make_fake_infrared('r', 0, 100 * MS), 0)
                matcher.observe_clock(arrival, 1)
                decisions = matcher.add_radar(make_fake_radar('r', 0, 100 * MS), 1)
                decisions += matcher.advance(arrival, 1)
                self.assertEqual(len(decisions), 1)
                self.assertEqual(decisions[0]['reason'], reason)
        self.matcher.add_radar(make_fake_radar('r', 1, 100 * MS), 0)
        self.matcher.advance(140 * MS, 1)
        late, = self.matcher.add_radar(make_fake_radar('r', 0, 50 * MS), 2)
        self.assertEqual(late['reason'], 'late_radar')

    def test_poll_before_first_clock_expires_without_inventing_clock(self):
        self.prime()
        self.assertEqual(self.matcher.poll(499 * MS), [])
        decision, = self.matcher.poll(500 * MS)
        self.assertEqual(decision['reason'], 'wall_timeout')
        self.assertIsNone(self.matcher.clock_ns)
        self.assertEqual(self.matcher.cache_sizes, dict(radar=0, infrared=0, state=0))

    def test_deadline_nearest_tie_earlier_and_original_timestamps(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('r', 2, 105 * MS), MS)
        self.assertEqual(self.matcher.advance(139 * MS, 2 * MS), [])
        self.matcher.add_infrared(make_fake_infrared('r', 1, 95 * MS), 3 * MS)
        decision, = self.matcher.advance(140 * MS, 7 * MS)
        self.assertEqual(decision['reason'], '')
        self.assertEqual(decision['bundle']['infrared']['header']['timestamp'], 95 * MS)
        self.assertEqual(decision['bundle']['header']['timestamp'], 100 * MS)
        self.assertEqual(decision['wait_ns'], 7 * MS)
        self.assertEqual(decision['data_age_ns'], 40 * MS)

    def test_historical_pose_is_not_overwritten_and_ten_ms_is_inclusive(self):
        for age, reason in ((10 * MS, ''), (10 * MS + 1, 'pose_age_exceeded')):
            with self.subTest(age=age):
                matcher = BoundedMatcher('r', self.config)
                matcher.add_state(pose(0, 100 * MS - age), 0)
                matcher.add_state(pose(1, 130 * MS), 0)
                matcher.add_radar(make_fake_radar('r', 0, 100 * MS), 0)
                matcher.add_infrared(make_fake_infrared('r', 0, 100 * MS), 0)
                decision, = matcher.advance(140 * MS, 1)
                self.assertEqual(decision['reason'], reason)
                if not reason:
                    self.assertEqual(decision['bundle']['state']['header']['timestamp'], 90 * MS)

    def test_wall_timeout_when_clock_paused_including_earlier_radar_blocking(self):
        self.matcher.add_radar(make_fake_radar('r', 2, 200 * MS), 0)
        self.matcher.add_radar(make_fake_radar('r', 1, 100 * MS), 400 * MS)
        self.matcher.advance(0, 499 * MS)
        decisions = self.matcher.advance(0, 500 * MS)
        self.assertEqual([sequence(d['radar']) for d in decisions], [1, 2])
        self.assertEqual([d['reason'] for d in decisions], ['wall_timeout_order_barrier', 'wall_timeout'])
        self.assertEqual(self.matcher.cache_sizes['radar'], 0)

    def test_future_samples_cannot_bypass_clock_at_eof(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('r', 1, 100 * MS), 0)
        self.matcher.advance(90 * MS, 1)
        decision, = self.matcher.finish(2)
        self.assertEqual(decision['reason'], 'clock_unavailable')
        self.assertIsNone(decision['bundle'])

    def test_eof_finalizes_pending_without_inventing_clock(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('r', 1, 100 * MS), 0)
        self.matcher.advance(100 * MS, 1)
        decision, = self.matcher.finish(2)
        self.assertEqual(decision['reason'], '')
        self.assertEqual(decision['data_age_ns'], 0)
        self.assertEqual(self.matcher.finish(2), [])
        self.assertEqual(self.matcher.audit()['counts']['infrared']['pending'], 0)

    def test_ordered_output_late_rejection_duplicates_and_ir_reuse(self):
        self.matcher.observe_clock(104 * MS, 0)
        self.matcher.add_state(pose(0, 100 * MS), 0)
        self.matcher.add_infrared(make_fake_infrared('r', 0, 102 * MS), 0)
        later = make_fake_radar('r', 2, 104 * MS)
        self.matcher.add_radar(later, 0)
        self.matcher.add_radar(make_fake_radar('r', 1, 100 * MS), 1)
        self.assertEqual(self.matcher.add_radar(later, 2), [])
        decisions = self.matcher.advance(144 * MS, 3)
        self.assertEqual([sequence(d['radar']) for d in decisions], [1, 2])
        self.assertEqual([sequence(d['bundle']['infrared']) for d in decisions], [0, 0])
        late, = self.matcher.add_radar(make_fake_radar('r', 0, 90 * MS), 4)
        self.assertEqual(late['reason'], 'late_radar')
        self.matcher.finish(5)
        self.assertEqual(self.matcher.audit()['counts']['infrared']['adopted'], 1)
        self.assertEqual(self.matcher.audit()['counts']['radar']['duplicate_receipts'], 1)

    def test_ir_eviction_uses_timestamp_and_ledger_retains_no_payload(self):
        class Payload(list):
            pass
        self.matcher = BoundedMatcher('r', dict(self.config, infrared_capacity=2))
        self.prime()
        infrared = make_fake_infrared('r', 0, 100 * MS)
        infrared['image'] = Payload([0.5] * 1024)
        old_payload = weakref.ref(infrared['image'])
        self.matcher.add_infrared(infrared, 0)
        self.matcher.add_infrared(make_fake_infrared('r', 1, 120 * MS), 1)
        self.matcher.add_infrared(make_fake_infrared('r', 2, 80 * MS), 2)
        decision, = self.matcher.advance(140 * MS, 3)
        self.assertEqual(sequence(decision['bundle']['infrared']), 0)
        del infrared, decision
        self.matcher.finish(4)
        gc.collect()
        self.assertIsNone(old_payload())
        self.assertNotIn('image', json.dumps(self.matcher.audit()))
        self.assertLessEqual(self.matcher.audit()['high_water']['infrared'], 2)

    def test_state_and_radar_capacity_bounds_and_mutation_isolation(self):
        matcher = BoundedMatcher('r', dict(self.config, radar_capacity=2, state_capacity=2))
        outcomes = []
        for i in range(10):
            original = pose(i, i * MS)
            outcomes += matcher.add_state(original, i)
            original['header']['timestamp'] = 999 * MS
            outcomes += matcher.add_radar(make_fake_radar('r', i, i * MS), i)
            self.assertLessEqual(matcher.cache_sizes['radar'], 2)
            self.assertLessEqual(matcher.cache_sizes['state'], 2)
        self.assertEqual([d['reason'] for d in outcomes], ['radar_overflow'] * 8)
        outcomes += matcher.finish(10)
        self.assertEqual(len(outcomes), 10)
        self.assertEqual(matcher.audit()['counts']['state']['pending'], 0)

    def test_new_radar_drains_due_before_capacity_with_worker_delayed(self):
        for receipt in ('timely', 'late_ir', 'late_state'):
            with self.subTest(receipt=receipt):
                matcher = BoundedMatcher('r', self.config)
                matcher.observe_clock(500 * MS, 0)
                if receipt != 'late_state':
                    matcher.add_state(pose(0, 500 * MS), 0)
                if receipt != 'late_ir':
                    matcher.add_infrared(make_fake_infrared('r', 0, 500 * MS), 0)
                for stamp in range(505, 513):
                    matcher.observe_clock(stamp * MS, (stamp - 500) * MS)
                    self.assertEqual(matcher.add_radar(
                        make_fake_radar('r', stamp - 490, stamp * MS), (stamp - 500) * MS), [])
                self.assertEqual(matcher.cache_sizes['radar'], 8)
                self.assertEqual(matcher.observe_clock(546 * MS, 46 * MS), [])
                if receipt == 'late_ir':
                    matcher.add_infrared(make_fake_infrared('r', 0, 500 * MS), 46 * MS)
                if receipt == 'late_state':
                    matcher.add_state(pose(0, 500 * MS), 46 * MS)
                decisions = matcher.add_radar(make_fake_radar('r', 23, 550 * MS), 46 * MS)
                self.assertEqual([sequence(d['radar']) for d in decisions], [15, 16])
                expected = {'timely': '', 'late_ir': 'infrared_unavailable',
                            'late_state': 'pose_unavailable'}[receipt]
                self.assertEqual(decisions[0]['reason'], expected)
                self.assertEqual(decisions[0]['bundle'] is not None, receipt == 'timely')
                self.assertEqual(decisions[0]['data_age_ns'], 41 * MS)
                self.assertEqual(matcher.cache_sizes['radar'], 7)
                self.assertEqual(matcher.advance(546 * MS, 47 * MS), [])
                decisions += matcher.finish(48 * MS)
                self.assertEqual(len({sequence(d['radar']) for d in decisions}), 9)
                self.assertFalse(any(d['reason'] == 'radar_overflow' for d in decisions))
                self.assertEqual(matcher.audit()['counts']['radar']['pending'], 0)

    def test_full_cache_rejects_older_ir_without_copying_large_payload(self):
        class UnreadPixels(list):
            def __iter__(self):
                raise AssertionError('evicted incoming image must not be copied')
        matcher = BoundedMatcher('r', dict(self.config, infrared_capacity=1))
        matcher.add_infrared(make_fake_infrared('r', 1, 100 * MS), 0)
        old = make_fake_infrared('r', 0, 80 * MS)
        old['image'] = UnreadPixels([0.5] * 327680)
        self.assertEqual(matcher.add_infrared(old, 1), [])
        matcher.finish(2)
        self.assertEqual(matcher.audit()['records']['infrared'][old['header']['sample_id']]['reason'],
                         'infrared_overflow')

    def test_audit_capacity_is_explicit_and_eof_still_releases_payloads(self):
        matcher = BoundedMatcher('r', dict(self.config, audit_capacity=2))
        matcher.add_radar(make_fake_radar('r', 0, 0), 0)
        matcher.add_infrared(make_fake_infrared('r', 0, 0), 0)
        with self.assertRaisesRegex(RuntimeError, 'audit_capacity'):
            matcher.add_infrared(make_fake_infrared('r', 1, 20 * MS), 1)
        matcher.finish(2)
        self.assertEqual(matcher.cache_sizes, dict(radar=0, infrared=0, state=0))
        for counts in matcher.audit()['counts'].values():
            self.assertEqual(counts['pending'], 0)

    def test_pause_releases_unused_ir_and_state_with_no_radar(self):
        self.matcher.add_infrared(make_fake_infrared('r', 0, 0), 0)
        self.matcher.add_state(pose(0, 0), 0)
        self.assertEqual(self.matcher.advance(0, 500 * MS), [])
        self.assertEqual(self.matcher.cache_sizes, dict(radar=0, infrared=0, state=0))
        for kind in ('infrared', 'state'):
            self.assertEqual(self.matcher.audit()['counts'][kind]['timeouts'], 1)

    def test_future_ir_at_eof_and_just_outside_five_ms_are_rejected(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('r', 0, 105 * MS), 0)
        self.matcher.advance(100 * MS, 1)
        decision, = self.matcher.finish(2)
        self.assertEqual(decision['reason'], 'infrared_unavailable')
        matcher = BoundedMatcher('r', self.config)
        matcher.add_radar(make_fake_radar('r', 0, 100 * MS), 0)
        matcher.add_state(pose(0, 100 * MS), 0)
        matcher.add_infrared(make_fake_infrared('r', 0, 105 * MS + 1), 0)
        decision, = matcher.advance(140 * MS, 1)
        self.assertEqual(decision['reason'], 'radar_ir_timeout')

    def test_mismatch_and_clock_regression_fail_closed(self):
        self.prime()
        self.matcher.add_infrared(make_fake_infrared('other', 0, 100 * MS), 1)
        decision, = self.matcher.advance(140 * MS, 2)
        self.assertEqual(decision['reason'], 'infrared_unavailable')
        self.matcher.add_radar(make_fake_radar('r', 2, 150 * MS), 3)
        stopped, = self.matcher.advance(139 * MS, 4)
        self.assertEqual(stopped['reason'], 'clock_regression')
        with self.assertRaises(ValueError):
            self.matcher.advance(150 * MS, 3)

    def test_audit_detects_missing_delivery_and_declared_omissions_separately(self):
        profile = load_config(CONFIG, 'missing')
        schedule = make_schedule(profile, 2000 * MS)
        self.matcher.add_radar(make_fake_radar('r', 0, 0), 0)
        self.matcher.finish(1)
        counts = self.matcher.audit(schedule)['counts']
        self.assertEqual(counts['radar']['unexpected_missing'], 39)
        omissions = sum(s['drop'] for s in schedule['infrared'])
        self.assertGreater(omissions, 0)
        self.assertEqual(counts['infrared']['declared_dropped'], omissions)
        self.assertEqual(counts['infrared']['unexpected_missing'], 100 - omissions)


class OnlineGraphAuditTest(unittest.TestCase):
    def setUp(self):
        self.publishers = [
            ('/clock', ['/perf01a_source']),
            ('/uav/sim/state', ['/perf01a_source']),
            ('/uav/sensors/radar', ['/perf01a_radar']),
            ('/uav/sensors/infrared', ['/perf01a_infrared']),
            ('/uav/sensors/bundle', ['/perf01a_sensor']),
            ('/uav/perception/occupancy', ['/perf01a_perception']),
            ('/uav/map/snapshot', ['/perf01a_mapping']),
        ]
        self.subscribers = [
            ('/clock', ['/perf01a_async_runner', '/perf01a_sensor']),
            ('/uav/sim/state', ['/perf01a_sensor']),
            ('/uav/sensors/radar', ['/perf01a_sensor']),
            ('/uav/sensors/infrared', ['/perf01a_sensor']),
            ('/uav/sensors/bundle', ['/perf01a_perception', '/perf01a_async_runner']),
            ('/uav/perception/occupancy', ['/perf01a_mapping', '/perf01a_async_runner']),
            ('/uav/map/snapshot', ['/perf01a_async_runner']),
        ]

    def test_normal_online_graph_passes(self):
        result = validate_online_graph(self.publishers, self.subscribers)
        self.assertTrue(result['passed'])
        self.assertEqual(result['forbidden_topics'], [])
        self.assertEqual(result['forbidden_nodes'], [])

    def test_empty_graph_does_not_vacuously_pass(self):
        result = validate_online_graph([], [])
        self.assertFalse(result['passed'])
        self.assertIn('online graph is empty', result['errors'])
        self.assertEqual(result['missing_nodes'], sorted(EXPECTED_ONLINE_NODES))

    def test_missing_online_node_fails_closed(self):
        publishers = [entry for entry in self.publishers if '/perf01a_mapping' not in entry[1]]
        subscribers = [entry for entry in self.subscribers if '/perf01a_mapping' not in entry[1]]
        result = validate_online_graph(publishers, subscribers)
        self.assertFalse(result['passed'])
        self.assertIn('/perf01a_mapping', result['missing_nodes'])

    def test_training_topic_in_either_direction_fails(self):
        publishers = self.publishers + [('/uav/training/lidar_supervision', ['/unexpected'])]
        subscribers = self.subscribers + [('/uav/training/labels', ['/perf01a_async_runner'])]
        result = validate_online_graph(publishers, subscribers)
        self.assertFalse(result['passed'])
        self.assertEqual(result['forbidden_topics'],
                         ['/uav/training/labels', '/uav/training/lidar_supervision'])

    def test_renamed_lidar_node_fails_even_without_lidar_topic(self):
        publishers = self.publishers + [('/uav/sensors/debug', ['/fake_lidar'])]
        result = validate_online_graph(publishers, self.subscribers)
        self.assertFalse(result['passed'])
        self.assertEqual(result['forbidden_nodes'], ['/fake_lidar'])


if __name__ == '__main__':
    unittest.main()
