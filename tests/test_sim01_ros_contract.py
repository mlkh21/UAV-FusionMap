"""使用真实生成消息的序列化回归；不启动ROS master。"""
import copy
import io
import unittest

from uav_fusionmap_msgs.msg import AircraftState
from ufm_ros_contract import from_ros_state, to_ros_state


def fixture():
    return dict(header=dict(schema_version='0.1', timestamp=9007199254740993,
                            clock_id='sim:fixture-run', run_id='fixture-run',
                            sample_id='sim.odometry:1:1:9007199254740', frame_id='world_ned',
                            source_type='simulation', status='valid', reason=''),
                position=[1., 2., 3.], orientation_xyzw=[0., 0., 0., 1.],
                linear_velocity=[4., 5., 6.], body_frame_id='body_frd',
                velocity_frame_id='body_frd', state_source='estimated',
                quality=dict(confidence=None, uncertainty=dict(status='unavailable',
                             kind='pose_covariance', value=None, unit='mixed', source='PX4 TODO')))


class StateContractTest(unittest.TestCase):
    def test_real_serialization_roundtrip(self):
        source = fixture()
        msg = to_ros_state(source)
        stream = io.BytesIO()
        msg.serialize(stream)
        decoded = AircraftState().deserialize(stream.getvalue())
        self.assertEqual(from_ros_state(decoded), source)
        self.assertFalse(decoded.quality.confidence_available)
        self.assertEqual(list(decoded.quality.uncertainty.value), [])

    def test_nanoseconds_int64_boundaries(self):
        for stamp in (0, 2**63 - 1):
            source = fixture()
            source['header']['timestamp'] = stamp
            stream = io.BytesIO()
            to_ros_state(source).serialize(stream)
            msg = AircraftState().deserialize(stream.getvalue())
            self.assertEqual(from_ros_state(msg)['header']['timestamp'], stamp)
        for stamp in (-1, 2**63, 1.0, True):
            with self.subTest(stamp=stamp):
                source = fixture()
                source['header']['timestamp'] = stamp
                with self.assertRaises(ValueError):
                    to_ros_state(source)

    def test_reject_invalid_header(self):
        for key, value in [('run_id', ''), ('clock_id', ''), ('sample_id', ''),
                           ('schema_version', '99'), ('status', 'unknown'),
                           ('source_type', 0), ('frame_id', None)]:
            with self.subTest(key=key):
                source = fixture()
                source['header'][key] = value
                with self.assertRaises(ValueError):
                    to_ros_state(source)

    def test_reject_invalid_geometry(self):
        for key, value in [('position', [1., 2.]), ('position', [float('nan'), 0., 0.]),
                           ('orientation_xyzw', [0., 0., 0., 0.]),
                           ('orientation_xyzw', [0., 0., 0., 1.002]),
                           ('linear_velocity', [0., float('inf'), 0.])]:
            with self.subTest(key=key, value=value):
                source = fixture()
                source[key] = value
                with self.assertRaises(ValueError):
                    to_ros_state(source)

    def test_terminal_ignores_unavailable_geometry(self):
        source = fixture()
        source['header'].update(status='unavailable', reason='source timeout', sample_id='sim.terminal:fixture-run')
        source['position'][0] = float('nan')
        source['orientation_xyzw'] = [0., 0., 0., 0.]
        stream = io.BytesIO()
        to_ros_state(source).serialize(stream)
        decoded = from_ros_state(AircraftState().deserialize(stream.getvalue()))
        self.assertEqual(decoded['header'], source['header'])
        source['header']['reason'] = ''
        with self.assertRaises(ValueError):
            to_ros_state(source)

    def test_wire_invalid_enum_and_unknown_quality(self):
        msg = to_ros_state(fixture())
        for field in ('status', 'source_type'):
            bad = copy.deepcopy(msg)
            setattr(bad.header, field, 255)
            with self.assertRaises(ValueError):
                from_ros_state(bad)
        msg.quality.uncertainty.value = [0.] * 36
        with self.assertRaises(ValueError):
            from_ros_state(msg)
        msg = to_ros_state(fixture())
        msg.quality.confidence = float('nan')
        self.assertIsNone(from_ros_state(msg)['quality']['confidence'])
        msg.quality.confidence_available = True
        with self.assertRaises(ValueError):
            from_ros_state(msg)


if __name__ == '__main__':
    unittest.main()
