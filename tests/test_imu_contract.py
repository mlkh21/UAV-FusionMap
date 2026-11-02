"""Phase 2可选IMU承载、坐标与独立clock门禁。"""
import copy
import io
import unittest

from uav_fusionmap_msgs.msg import ImuSample
from ufm_ros_contract import from_ros_imu, to_ros_imu
from ufm_sensors.imu_adapter import ImuClockGate, adapt_imu


def source(ns=2_000_000_000):
    return dict(header=dict(schema_version='0.1', timestamp=ns, run_id='run',
                            clock_id='sim:run', sample_id='sim.imu:%d' % (ns // 1000),
                            source_type='simulation', status='valid', reason='',
                            frame_id='body_frd'), acceleration_type='specific_force',
                linear_acceleration=[1., 2., -9.8], angular_velocity=[.1, -.2, .3],
                acceleration_covariance=None, angular_velocity_covariance=None,
                calibration_id='')


class ImuContractTests(unittest.TestCase):
    def test_identity_history_is_bounded_and_old_input_does_not_revive(self):
        gate = ImuClockGate('run', pending_limit=1, identity_history_limit=4)
        for i in range(200):
            ns = i * 1_000_000
            sample = adapt_imu(source(ns), 'run', 'sim_pilot_virtual_flu_v1')
            gate.consume_clock(ns, i * .001)
            self.assertEqual(gate.consume_imu(sample, i * .001), [sample])
            self.assertLessEqual(gate.identity_count, 4)
        self.assertEqual(gate.consume_imu(adapt_imu(source(0), 'run',
                         'sim_pilot_virtual_flu_v1'), .2), [])
        sample['linear_acceleration'][0] = 9.
        with self.assertRaisesRegex(ValueError, 'conflict'):
            gate.consume_imu(sample, .21)

    def test_message_roundtrip_and_axes(self):
        raw = source()
        msg = to_ros_imu(raw)
        wire = io.BytesIO()
        msg.serialize(wire)
        decoded = ImuSample()
        decoded.deserialize(wire.getvalue())
        self.assertEqual(from_ros_imu(decoded), raw)
        derived = adapt_imu(from_ros_imu(decoded), 'run', 'sim_pilot_virtual_flu_v1')
        self.assertEqual(derived['linear_acceleration'], [1., -2., 9.8])
        self.assertEqual(derived['angular_velocity'], [.1, .2, -.3])
        self.assertEqual(derived['header']['timestamp'], raw['header']['timestamp'])
        self.assertEqual(derived['header']['sample_id'], 'sensors.imu:' + raw['header']['sample_id'])
        self.assertEqual(derived['header']['frame_id'], 'imu')
        self.assertEqual(from_ros_imu(to_ros_imu(derived)), derived)

    def test_fail_closed_identity_calibration_semantics_and_quality(self):
        for path, value in [('header.frame_id', 'imu'), ('header.run_id', 'other'),
                            ('header.clock_id', 'sim:other'), ('acceleration_type', 'gravity_removed'),
                            ('acceleration_covariance', [0.] * 9)]:
            with self.subTest(path=path):
                sample = copy.deepcopy(source())
                obj = sample
                keys = path.split('.')
                for key in keys[:-1]:
                    obj = obj[key]
                obj[keys[-1]] = value
                with self.assertRaises(ValueError):
                    adapt_imu(sample, 'run', 'sim_pilot_virtual_flu_v1')
        with self.assertRaisesRegex(ValueError, 'calibration'):
            adapt_imu(source(), 'run', '')
        invalid = to_ros_imu(source())
        invalid.acceleration_covariance_available = True
        with self.assertRaises(ValueError):
            from_ros_imu(invalid)
        invalid = source()
        invalid['linear_acceleration'][1] = float('nan')
        with self.assertRaises(ValueError):
            to_ros_imu(invalid)

    def test_clock_coverage_duplicate_conflict_timeout_terminal(self):
        gate = ImuClockGate('run', timeout_wall_s=.5)
        s = adapt_imu(source(), 'run', 'sim_pilot_virtual_flu_v1')
        self.assertEqual(gate.consume_imu(s, 0.), [])
        self.assertEqual(gate.consume_clock(1_000_000_000, .1), [])
        self.assertEqual(gate.consume_clock(2_000_000_000, .2), [s])
        self.assertEqual(gate.consume_imu(s, .3), [])
        conflict = copy.deepcopy(s)
        conflict['linear_acceleration'][0] = 7.
        with self.assertRaisesRegex(ValueError, 'conflict'):
            gate.consume_imu(conflict, .4)
        pending = adapt_imu(source(3_000_000_000), 'run', 'sim_pilot_virtual_flu_v1')
        self.assertEqual(gate.consume_imu(pending, .5), [])
        gate.poll_timeout(1.)
        self.assertEqual(gate.consume_clock(3_000_000_000, 1.1), [])
        terminal = copy.deepcopy(s)
        terminal['header'].update(status='unavailable', reason='terminal:imu_regression',
                                  sample_id='sim.imu.terminal:imu_regression:2000000')
        terminal['linear_acceleration'] = [0.] * 3
        terminal['angular_velocity'] = [0.] * 3
        self.assertEqual(gate.consume_imu(terminal, 1.2), [terminal])
        self.assertEqual(gate.consume_imu(adapt_imu(source(4_000_000_000),
                           'run', 'sim_pilot_virtual_flu_v1'), 1.3), [])

    def test_clock_regression_locks_imu(self):
        gate = ImuClockGate('run')
        gate.consume_clock(2_000_000_000, 0.)
        with self.assertRaisesRegex(ValueError, 'regression'):
            gate.consume_clock(1_000_000_000, .1)
        self.assertTrue(gate.locked)


if __name__ == '__main__':
    unittest.main()
