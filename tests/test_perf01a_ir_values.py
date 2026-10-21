"""SENS-IR-01的原始IR与SensorBundle值守恒纯函数测试。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros_ws'))

from perf01a_async_run import verify_ir_value_transport


def frame(sample_id, image, timestamp=4_000_000):
    return dict(sample_id=sample_id, timestamp=timestamp,
                run_id='run', clock_id='sim:run', frame_id='thermal_optical', status=0,
                width=4, height=3, encoding='32FC1', value_unit='fixture_intensity',
                image=image, exposure_start=2_000_000, exposure_end=6_000_000,
                calibration_id='perf01a_fixture_identity_v1')


PROFILE = dict(ir_resolution=[4, 3], fake_infrared=dict(
    background_value=.4, noise_std=0.0, exposure_duration_ns=4_000_000,
    hotspots=[dict(x_px=1, y_px=1, radius_px=0, value=.5)]))
IMAGE = [.4, .4, .4, .4, .4, .9, .4, .4, .4, .4, .4, .4]


class IrValueTransportTest(unittest.TestCase):
    def test_raw_and_bundle_values_and_oracle_match(self):
        result = verify_ir_value_transport(
            [frame('ir:0', IMAGE)],
            [dict(infrared_id='ir:0', infrared=frame('ir:0', IMAGE))],
            PROFILE, ['ir:0'])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['checks'][0]['hotspot_center']['raw_value'], .9)
        self.assertEqual(result['checks'][0]['hotspot_center']['bundle_value'], .9)

    def test_pixel_difference_fails(self):
        raw = frame('ir:0', IMAGE)
        bundle = frame('ir:0', [.4, .4, .4, .4, .4, .8, .4, .4, .4, .4, .4, .4])
        result = verify_ir_value_transport([raw], [dict(infrared_id='ir:0', infrared=bundle)],
                                           PROFILE, ['ir:0'])
        self.assertTrue(any('pixel differs' in error for error in result['errors']))
        self.assertTrue(any('bundle hotspot center oracle differs' in error
                            for error in result['errors']))

    def test_background_pixel_difference_fails(self):
        bundle = frame('ir:0', [.6] + IMAGE[1:])
        result = verify_ir_value_transport([frame('ir:0', IMAGE)],
            [dict(infrared_id='ir:0', infrared=bundle)], PROFILE, ['ir:0'])
        self.assertTrue(any('bundle background oracle differs' in error
                            for error in result['errors']))

    def test_child_timestamp_exposure_and_identity_differences_fail(self):
        bundle = frame('ir:wrong', IMAGE, timestamp=5_000_000)
        bundle['exposure_end'] = 7_000_000
        result = verify_ir_value_transport([frame('ir:0', IMAGE)],
            [dict(infrared_id='ir:0', infrared=bundle)], PROFILE, ['ir:0'])
        self.assertTrue(any('sample_id' in error for error in result['errors']))
        self.assertTrue(any('timestamp' in error for error in result['errors']))
        self.assertTrue(any('exposure_end' in error for error in result['errors']))

    def test_all_bundles_reusing_ir_must_match(self):
        changed = frame('ir:0', IMAGE[:5] + [.1] + IMAGE[6:])
        result = verify_ir_value_transport([frame('ir:0', IMAGE)],
            [dict(infrared_id='ir:0', infrared=frame('ir:0', IMAGE)),
             dict(infrared_id='ir:0', infrared=changed)], PROFILE, ['ir:0'])
        self.assertEqual(len(result['checks']), 2)
        self.assertTrue(any('pixel differs' in error for error in result['errors']))

    def test_missing_raw_frame_fails(self):
        result = verify_ir_value_transport([],
            [dict(infrared_id='ir:0', infrared=frame('ir:0', IMAGE))], PROFILE, ['ir:0'])
        self.assertTrue(any('coverage differs' in error for error in result['errors']))
        self.assertTrue(any('missing from raw' in error for error in result['errors']))


if __name__ == '__main__':
    unittest.main()
