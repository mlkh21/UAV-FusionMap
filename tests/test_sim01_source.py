"""SIM-01A源契约及时序行为；纯fixture不依赖仿真产物。"""
import copy
import unittest

from pymavlink.dialects.v20 import common
from ufm_simulation.mavlink_source import decode_source_packet
from ufm_simulation.source_timeline import SourceTimeline
from sim01_imu_audit import audit_imu_samples
from imu_physics_validation import check_scenarios


def odometry(t=1_000_000, reset=3):
    sender = common.MAVLink(None, srcSystem=1, srcComponent=1)
    msg = common.MAVLink_odometry_message(
        t, 1, 12, 1., 2., 3., [1., 0., 0., 0.], 4., 5., 6.,
        0., 0., 0., [1.] * 21, [1.] * 21, reset, 8, 0)
    return msg, sender


def state(t, reset=3):
    msg, sender = odometry(t, reset)
    return decode_source_packet(msg.pack(sender))


def imu(t):
    return {'type': 'imu', 'time_usec': t}


class SourceDecodeTests(unittest.TestCase):
    def test_state_contract_and_unknown_quality(self):
        s = state(1_234_567)['state']
        self.assertEqual(s['header']['timestamp'], 1_234_567_000)
        self.assertEqual(s['orientation_xyzw'], [0., 0., 0., 1.])
        self.assertEqual(s['velocity_frame_id'], 'body_frd')
        self.assertEqual(s['quality']['uncertainty']['status'], 'unavailable')
        self.assertIsNone(s['quality']['uncertainty']['value'])
        self.assertIsNone(s['quality']['confidence'])
        self.assertEqual(s['state_source'], 'estimated')

    def test_bad_frame_estimator_nan_quaternion_and_crc(self):
        for key, value in [('frame_id', 4), ('estimator_type', 2),
                           ('x', float('nan')), ('q', [0., 0., 0., 0.]),
                           ('q', [1.01, 0., 0., 0.])]:
            with self.subTest(key=key, value=value):
                msg, sender = odometry()
                setattr(msg, key, value)
                with self.assertRaises(ValueError):
                    decode_source_packet(msg.pack(sender))
        msg, sender = odometry()
        raw = bytearray(msg.pack(sender)); raw[-1] ^= 1
        with self.assertRaises(ValueError):
            decode_source_packet(raw)
        with self.assertRaises(ValueError):
            decode_source_packet(msg.pack(sender), framing_status=2)

    def test_wrong_source_filtered_and_valid_imu(self):
        msg, sender = odometry()
        sender.srcSystem = 2
        self.assertIsNone(decode_source_packet(msg.pack(sender)))
        sender.srcSystem = 1
        m = common.MAVLink_highres_imu_message(
            123456, 0., 0., -9.8, 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 63)
        self.assertEqual(decode_source_packet(m.pack(sender)), imu(123456))
        m.fields_updated = 0
        with self.assertRaises(ValueError):
            decode_source_packet(m.pack(sender))

    def test_imu_values_are_not_exposed_as_business_samples(self):
        sender = common.MAVLink(None, srcSystem=1, srcComponent=1)
        m = common.MAVLink_highres_imu_message(
            123456, 1., 2., -9.8, 4., 5., 6., 0., 0., 0., 0., 0., 0., 0., 63)
        sample = decode_source_packet(m.pack(sender))
        self.assertEqual(sample, imu(123456))
        events = SourceTimeline('imu-only').consume(sample, 0.)
        self.assertEqual(events, [{'type': 'clock', 'timestamp': 123456000}])

    def test_nonfinite_imu_components_do_not_advance_source_clock(self):
        sender = common.MAVLink(None, srcSystem=1, srcComponent=1)
        timeline = SourceTimeline('imu-invalid')
        for index in range(6):
            values = [1., 2., -9.8, 4., 5., 6.]
            values[index] = float('nan')
            m = common.MAVLink_highres_imu_message(
                123456, *values, *([0.] * 7), 63)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'invalid_imu_fields'):
                timeline.consume(decode_source_packet(m.pack(sender)), index * .01)
        self.assertIsNone(timeline.last_clock_ns)

    def test_optional_imu_values_match_source_and_timeline(self):
        sender = common.MAVLink(None, srcSystem=1, srcComponent=1)
        msg = common.MAVLink_highres_imu_message(
            123456, 1., 2., -9.8, 4., 5., 6., *([0.] * 7), 63)
        wire = msg.pack(sender)
        self.assertEqual(decode_source_packet(wire), imu(123456))
        sample = decode_source_packet(wire, include_imu_values=True)
        self.assertEqual(sample['imu_values'], {
            'linear_acceleration': [1., 2., -9.800000190734863],
            'angular_velocity': [4., 5., 6.]})
        timeline = SourceTimeline('imu-test', emit_imu=True)
        events = timeline.consume(sample, 0.)
        self.assertEqual([e['type'] for e in events], ['clock', 'imu'])
        self.assertEqual(events[1]['imu']['header']['timestamp'], events[0]['timestamp'])
        self.assertEqual(events[1]['imu']['header']['frame_id'], 'body_frd')
        self.assertEqual(events[1]['imu']['acceleration_type'], 'specific_force')
        self.assertIsNone(events[1]['imu']['acceleration_covariance'])
        self.assertEqual(timeline.consume(sample, .01), [])
        self.assertEqual(timeline.counters['duplicate_imu'], 1)
        conflicting = dict(sample, imu_values={
            'linear_acceleration': [7., 2., -9.8],
            'angular_velocity': [4., 5., 6.]})
        conflict_events = timeline.consume(conflicting, .02)
        self.assertEqual(timeline.phase, 'FAULT')
        self.assertEqual([e['imu']['header']['status'] for e in conflict_events
                          if e['type'] == 'imu'], ['unavailable'])
        with self.assertRaisesRegex(ValueError, 'imu_values_required'):
            SourceTimeline('imu-test', emit_imu=True).consume(imu(123456), 0.)

    def test_optional_imu_terminal_stops_valid_publication(self):
        timeline = SourceTimeline('imu-run', emit_imu=True)
        sample = dict(imu(2_000_000), imu_values={
            'linear_acceleration': [0., 0., -9.8], 'angular_velocity': [0., 0., 0.]})
        timeline.consume(sample, 0.)
        sample['time_usec'] = 1_000_000
        events = timeline.consume(sample, .1)
        terminal = [e['imu'] for e in events if e['type'] == 'imu'][0]
        self.assertEqual(terminal['header']['status'], 'unavailable')
        self.assertEqual(terminal['linear_acceleration'], [0., 0., 0.])
        self.assertEqual(timeline.consume(dict(sample, time_usec=3_000_000), .2), [])

    def test_overflow_and_small_quaternion_error(self):
        msg, sender = odometry((2**63-1)//1000+1)
        with self.assertRaises(ValueError):
            decode_source_packet(msg.pack(sender))
        msg, sender = odometry(); msg.q = [1.0005, 0., 0., 0.]
        s = decode_source_packet(msg.pack(sender))['state']
        self.assertAlmostEqual(s['orientation_xyzw'][3], 1.)


class TimelineTests(unittest.TestCase):
    def make(self, **kwargs):
        return SourceTimeline('run-test', **kwargs)

    def activate(self, timeline):
        # 每墙秒保持两路新样本；最后一个覆盖状态满足10秒预热。
        events = []
        for n in range(12):
            t = (n+1)*1_000_000
            events += timeline.consume(imu(t), n*.1)
            events += timeline.consume(state(t), n*.1+.01)
        self.assertEqual(timeline.phase, 'ACTIVE')
        return events

    def test_warmup_no_backfill_and_run_identity(self):
        timeline = self.make(); events = self.activate(timeline)
        emitted = [e['state'] for e in events if e['type'] == 'state']
        self.assertTrue(emitted)
        self.assertTrue(all(s['header']['timestamp'] >= 11_000_000_000 for s in emitted))
        for s in emitted:
            self.assertEqual(s['header']['run_id'], 'run-test')
            self.assertEqual(s['header']['clock_id'], 'sim:run-test')

    def test_future_state_clock_first_duplicate_and_conflict(self):
        tl = self.make(); self.activate(tl)
        self.assertEqual(tl.consume(state(12_020_000), 1.2), [])
        events = tl.consume(imu(12_020_000), 1.21)
        self.assertEqual([e['type'] for e in events], ['clock', 'state'])
        self.assertEqual(tl.consume(state(12_020_000), 1.22), [])
        conflicting = state(12_020_000); conflicting['state']['position'][0] = 99.
        events = tl.consume(conflicting, 1.23)
        self.assertTrue(any(e['type'] == 'diagnostic' for e in events))
        self.assertFalse(any(e['type'] == 'state' for e in events))

    def test_preparing_reset_restarts_window_active_reset_terminal(self):
        tl = self.make()
        for n in range(10):
            tl.consume(imu((n+1)*1_000_000), n*.1)
            tl.consume(state((n+1)*1_000_000, 3 if n < 5 else 4), n*.1+.01)
        self.assertEqual(tl.phase, 'PREPARING')
        for n in range(10,17):
            tl.consume(imu((n+1)*1_000_000), n*.1)
            tl.consume(state((n+1)*1_000_000, 4), n*.1+.01)
        self.assertEqual(tl.phase, 'ACTIVE')
        events = tl.consume(state(17_000_000, 5), 1.8)
        self.assertEqual(tl.phase, 'FAULT')
        terminal = [e['state'] for e in events if e['type']=='state'][0]
        self.assertEqual(terminal['header']['status'], 'unavailable')
        self.assertTrue(terminal['header']['reason'].startswith('terminal:'))
        self.assertNotEqual(terminal['header']['sample_id'], 'sim.odometry:1:1:17000000')
        self.assertEqual(terminal['header']['sample_id'], 'sim.terminal:estimator_reset:17000000')
        self.assertEqual(tl.consume(imu(18_000_000), 1.9), [])
        self.assertEqual(tl.poll_timeout(4.), [])

    def test_imu_regression_faults_in_preparing_and_active(self):
        for active in (False, True):
            tl = self.make()
            if active: self.activate(tl)
            else: tl.consume(imu(2_000_000), 0.)
            events = tl.consume(imu(1_000_000), 1.2)
            self.assertEqual(tl.phase, 'FAULT')
            self.assertTrue(any('regression' in e.get('reason','') for e in events))

    def test_independent_timeouts_and_duplicate_not_liveness(self):
        for stalled in ('imu', 'odometry'):
            tl = self.make(); self.activate(tl)
            for n in range(1,5):
                sample = state(12_000_000+n*1_000_000) if stalled=='imu' else imu(12_000_000+n*1_000_000)
                tl.consume(sample, 1.11+n*.4)
            tl.poll_timeout(3.2)
            self.assertEqual(tl.phase, 'FAULT')
        tl = self.make(); self.activate(tl)
        tl.consume(imu(12_000_000), 3.)
        tl.consume(state(12_000_000), 3.01)
        tl.poll_timeout(3.2)
        self.assertEqual(tl.phase, 'FAULT')

    def test_pending_expiry_overflow_and_startup_timeout(self):
        tl = self.make(pending_limit=1); self.activate(tl)
        tl.consume(state(13_000_000), 1.2)
        events = tl.consume(state(14_000_000), 1.3)
        self.assertTrue(any(e['type']=='diagnostic' for e in events))
        events = tl.poll_timeout(1.8)
        self.assertTrue(any('pending_timeout' in e.get('reason','') for e in events))
        tl = self.make(); tl.poll_timeout(0.); tl.poll_timeout(60.)
        self.assertEqual(tl.phase, 'FAULT')

    def test_old_state_drop_but_old_reset_is_not_hidden(self):
        tl = self.make(); self.activate(tl)
        ev = tl.consume(state(11_500_000), 1.3)
        self.assertFalse(any(e['type']=='state' for e in ev))
        tl.consume(state(11_500_000, reset=4), 1.4)
        self.assertEqual(tl.phase, 'FAULT')


def live_imu_samples(count=300):
    run_id = 'live-run'
    raw, source, adapted, clocks = {}, {}, {}, []
    for index in range(count):
        ns = (index + 1) * 20_000_000
        source_id = 'sim.imu:%d' % (ns // 1000)
        source_sample = {
            'header': {'timestamp': ns, 'run_id': run_id, 'clock_id': 'sim:' + run_id,
                       'sample_id': source_id, 'frame_id': 'body_frd',
                       'source_type': 'simulation', 'status': 'valid'},
            'acceleration_type': 'specific_force', 'linear_acceleration': [1., 2., -9.8],
            'angular_velocity': [.1, -.2, .3], 'acceleration_covariance': None,
            'angular_velocity_covariance': None, 'calibration_id': ''}
        adapted_sample = copy.deepcopy(source_sample)
        adapted_sample['header'].update(sample_id='sensors.imu:' + source_id,
                                        frame_id='imu', source_type='derived')
        adapted_sample['linear_acceleration'] = [1., -2., 9.8]
        adapted_sample['angular_velocity'] = [.1, .2, -.3]
        adapted_sample['calibration_id'] = 'sim_pilot_virtual_flu_v1'
        source[source_id], adapted[adapted_sample['header']['sample_id']] = source_sample, adapted_sample
        raw[source_id] = {'timestamp': ns, 'linear_acceleration': [1., 2., -9.8],
                          'angular_velocity': [.1, -.2, .3]}
        clocks.append(ns)
    return raw, source, adapted, clocks


class Sim01LiveImuAuditTests(unittest.TestCase):
    def audit(self, data):
        return audit_imu_samples(*data, 'live-run')

    def test_complete_live_contract_passes(self):
        report = self.audit(live_imu_samples())
        self.assertTrue(report['passed'], report['errors'])
        self.assertEqual(report['raw_source_matches'], 300)

    def test_missing_raw_sample_fails_closed(self):
        data = live_imu_samples()
        data[0].pop(next(iter(data[0])))
        report = self.audit(data)
        self.assertFalse(report['passed'])
        self.assertIn('insufficient independently matched IMU samples', report['errors'])

    def test_axis_or_value_mismatch_fails(self):
        data = live_imu_samples()
        data[2][next(iter(data[2]))]['linear_acceleration'][1] = 2.
        report = self.audit(data)
        self.assertFalse(report['passed'])
        self.assertIn('source to adapted IMU axis/value mismatch', report['errors'])

    def test_nonfinite_and_unknown_quality_fail(self):
        data = live_imu_samples()
        data[1][next(iter(data[1]))]['linear_acceleration'][0] = float('nan')
        data[1][next(iter(data[1]))]['acceleration_covariance'] = [0.] * 9
        report = self.audit(data)
        self.assertFalse(report['passed'])
        self.assertIn('source acceleration contains a non-finite value', report['errors'])
        self.assertIn('source IMU covariance is not explicitly unavailable', report['errors'])

    def test_wrong_domain_and_clock_fail(self):
        data = live_imu_samples()
        data[1][next(iter(data[1]))]['header']['run_id'] = 'other'
        data[3][-1] = data[3][-2]
        report = self.audit(data)
        self.assertFalse(report['passed'])
        self.assertIn('source IMU metadata or clock mismatch', report['errors'])
        self.assertIn('clock timestamps are not strictly increasing', report['errors'])


def physical_scenario_samples():
    base = dict(scenario='ground', roll_initial_deg=0, steps=750, dt_s=.004,
                pilot_last_mps2=[1.4, 0., -9.7], pilot_mean_mps2=[1.3, 0., -9.6],
                pilot_0p2s_mps2=[0., 0., -9.], body_forces_mean_mps2=[1.3, 0., -9.7],
                gravity_mps2=9.82, eyepoint_struct_in=[20., 0., 5.],
                roll_0p2s_deg=0.)
    cases = {name: copy.deepcopy(base) for name in
             ('ground', 'freefall', 'roll-positive', 'roll-negative')}
    cases['freefall'].update(scenario='freefall', pilot_0p2s_mps2=[0., 0., 0.])
    cases['roll-positive'].update(roll_initial_deg=20, roll_0p2s_deg=19.,
                                  pilot_0p2s_mps2=[0., -3., -10.])
    cases['roll-negative'].update(roll_initial_deg=-20, roll_0p2s_deg=-19.,
                                  pilot_0p2s_mps2=[0., 3., -10.])
    return cases


class ImuPhysicsScenarioAuditTests(unittest.TestCase):
    def test_independent_scenario_contrasts(self):
        self.assertEqual(check_scenarios(physical_scenario_samples()), [])

    def test_missing_scenario_fails(self):
        cases = physical_scenario_samples()
        del cases['freefall']
        self.assertIn('missing JSBSim scenario', check_scenarios(cases))

    def test_gravity_not_removed_from_freefall_fails(self):
        cases = physical_scenario_samples()
        cases['freefall']['pilot_0p2s_mps2'][2] = -9.8
        self.assertIn('early freefall pilot force is gravity-like', check_scenarios(cases))

    def test_wrong_roll_or_install_point_fails(self):
        cases = physical_scenario_samples()
        cases['roll-positive']['pilot_0p2s_mps2'][1] = 3.
        self.assertIn('roll contrast not observed at actual sample attitude', check_scenarios(cases))
        cases['roll-positive']['eyepoint_struct_in'] = [0., 0., 0.]
        self.assertIn('invalid scenario configuration or sample: roll-positive', check_scenarios(cases))

    def test_missing_attitude_receipt_fails_closed(self):
        cases = physical_scenario_samples()
        del cases['roll-positive']['roll_0p2s_deg']
        self.assertIn('missing scenario fields: roll-positive', check_scenarios(cases))


if __name__ == '__main__':
    unittest.main()
