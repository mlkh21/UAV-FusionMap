"""IFACE-01 restricted PointCloud2 fixture adapter; not a real-device driver."""
import math
import struct
import sys
import unittest
from pathlib import Path
import yaml
import rospy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sensors'))
sys.path.insert(0, str(ROOT / 'ros_ws'))

from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointField
from std_msgs.msg import Header
from ufm_sensors.radar_raw_adapter import adapt_radar_rows
from radar_raw_bridge import decode_radar_cloud


def fixture_profile():
    return yaml.safe_load((ROOT / 'configs/iface01_radar_fixture.yaml').read_text(encoding='utf-8'))


def raw_cloud(points=None, names=('x_m', 'y_m', 'z_m', 'vr_mps', 'snr_db')):
    fields = [PointField(name=k, offset=i*4, datatype=PointField.FLOAT32, count=1)
              for i, k in enumerate(names)]
    header = Header(stamp=rospy.Time(0, 100_000_000), frame_id='radar_fixture')
    return point_cloud2.create_cloud(header, fields, points if points is not None else [
        (3.0, -1.0, 0.5, 2.5, 7.0), (4.0, 1.0, -0.5, -1.0, 10.0)])


def identity():
    return {'run_id':'fixture-run', 'clock_id':'sim:fixture-run',
            'sample_id':'raw.radar:fixture-run:1', 'scan_start_ns':100_000_000,
            'scan_end_ns':100_000_000}


class RadarRawFixtureTest(unittest.TestCase):
    def test_field_mapping_follows_byte_offsets_not_requested_name_order(self):
        cloud = raw_cloud(points=[(7., 2.5, .5, -1., 3.)],
                          names=('snr_db', 'vr_mps', 'z_m', 'y_m', 'x_m'))
        cloud.fields.reverse()
        point = decode_radar_cloud(cloud, fixture_profile(), identity())['points'][0]
        self.assertEqual([point[key] for key in ('x', 'y', 'z', 'doppler', 'power')],
                         [3., -1., .5, 2.5, 7.])

    def test_declared_fields_support_big_endian_wire_data(self):
        cloud = raw_cloud(points=[(1, 2, 3, -4, 6)])
        cloud.is_bigendian = True
        cloud.data = struct.pack('>5f', 1, 2, 3, -4, 6)
        result = decode_radar_cloud(cloud, fixture_profile(), identity())
        self.assertEqual(result['points'][0]['z'], 3.0)
        self.assertEqual(result['points'][0]['doppler'], -4.0)

    def test_explicit_fields_units_sign_and_ros_round_trip(self):
        from ufm_ros_contract.perf01a_codec import to_ros_radar, from_ros_radar
        output = decode_radar_cloud(raw_cloud(), fixture_profile(), identity())
        self.assertEqual(output['header']['timestamp'], 100_000_000)
        self.assertEqual(output['header']['frame_id'], 'radar_fixture')
        self.assertEqual(output['header']['source_type'], 'fixture')
        self.assertEqual(output['points'][0]['doppler'], 2.5)  # away is positive
        self.assertEqual(output['points'][1]['doppler'], -1.0)
        self.assertEqual(output['points'][0]['power'], 7.0)
        wire = from_ros_radar(to_ros_radar(output))
        self.assertEqual(wire['points'], output['points'])
        self.assertEqual(wire['power_quantity'], 'signal_to_noise_ratio')
        self.assertEqual(wire['power_unit'], 'dB')

    def test_sign_inversion_only_when_declared(self):
        cfg = fixture_profile()
        cfg['doppler_positive'] = 'toward'
        output = decode_radar_cloud(raw_cloud(), cfg, identity())
        self.assertEqual([p['doppler'] for p in output['points']], [-2.5, 1.0])

    def test_no_echo_and_explicit_unavailable_channels(self):
        cfg = fixture_profile()
        cfg.update(doppler_field=None, doppler_unit='unavailable',
                   doppler_positive='unavailable', power_field=None,
                   power_quantity='unavailable', power_unit='unavailable')
        result = decode_radar_cloud(raw_cloud(points=[(1.0, 2.0, 3.0)],
                                              names=('x_m', 'y_m', 'z_m')), cfg, identity())
        self.assertFalse(result['points'][0]['doppler_available'])
        self.assertFalse(result['points'][0]['power_available'])
        self.assertEqual(result['points'][0]['doppler'], 0.0)
        self.assertEqual(decode_radar_cloud(raw_cloud(points=[]), fixture_profile(), identity())['points'], [])

    def test_reject_nonzero_scan_and_clock_or_frame_substitution(self):
        meta = identity()
        meta['scan_end_ns'] += 1
        with self.assertRaises(ValueError):
            decode_radar_cloud(raw_cloud(), fixture_profile(), meta)
        meta = identity()
        meta['clock_id'] = 'sim:elsewhere'
        with self.assertRaises(ValueError):
            decode_radar_cloud(raw_cloud(), fixture_profile(), meta)
        cfg = fixture_profile()
        cfg['frame_id'] = 'base_link'
        with self.assertRaises(ValueError):
            decode_radar_cloud(raw_cloud(), cfg, identity())

    def test_reject_missing_semantics_and_invalid_payload(self):
        for key, value in (('position_unit', 'cm'), ('doppler_unit', None),
                           ('doppler_positive', None), ('power_quantity', 'received_power'),
                           ('scan_reference', 'start'), ('mode', 'measured')):
            cfg = fixture_profile()
            cfg[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                decode_radar_cloud(raw_cloud(), cfg, identity())
        cfg = fixture_profile()
        del cfg['power_quantity']
        with self.assertRaises(ValueError):
            decode_radar_cloud(raw_cloud(), cfg, identity())
        with self.assertRaises(ValueError):
            decode_radar_cloud(raw_cloud(points=[(math.nan, 0, 0, 1, 2)]), fixture_profile(), identity())
        cloud = raw_cloud()
        cloud.fields[-1].datatype = PointField.UINT8
        with self.assertRaises(ValueError):
            decode_radar_cloud(cloud, fixture_profile(), identity())
        alias = raw_cloud()
        alias.fields[3].offset = alias.fields[0].offset
        with self.assertRaises(ValueError):
            decode_radar_cloud(alias, fixture_profile(), identity())
        with self.assertRaises(ValueError):
            decode_radar_cloud(raw_cloud(points=[(1, 2, 3, 4, 5, 6)],
                names=('x_m', 'y_m', 'z_m', 'vr_mps', 'snr_db', 'time_offset_ns')),
                fixture_profile(), identity())


if __name__ == '__main__':
    unittest.main()
