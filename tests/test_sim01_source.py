"""SIM-01A源契约及时序行为；纯fixture不依赖仿真产物。"""
import unittest

from pymavlink.dialects.v20 import common
from ufm_simulation.mavlink_source import decode_source_packet
from ufm_simulation.source_timeline import SourceTimeline


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


if __name__ == '__main__':
    unittest.main()
