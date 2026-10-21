"""独立核对在线原始fake Radar和实际采用的SensorBundle雷达值。"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros_ws'))

from perf01a_async_run import verify_radar_value_transport


PROFILE = dict(fake_radar=dict(scan_duration_ns=2_000_000))


def frame(sample_id='fixture.radar:run:0', points=None):
    if points is None:
        points = [dict(x=5., y=.25, z=.5, doppler=0., power=.95,
                       doppler_available=False, power_available=True)]
    return dict(header=dict(schema_version='0.1', timestamp=2_000_000,
                            run_id='run', clock_id='sim:run', sample_id=sample_id,
                            frame_id='radar', source_type='fixture', status='valid', reason=''),
                points=points, scan_start=1_000_000, scan_end=3_000_000,
                power_quantity='uncalibrated_intensity', power_unit='arbitrary',
                doppler_reference='sensor_relative',
                quality=dict(confidence=None, uncertainty=dict(status='unavailable',
                             kind='', value=None, unit='', source='fixture; quality not calibrated')))


def adopted(radar):
    return dict(radar_id=radar['header']['sample_id'], radar=radar,
                timestamp=radar['header']['timestamp'],
                run_id=radar['header']['run_id'], clock_id=radar['header']['clock_id'])


class RadarValueTransportTest(unittest.TestCase):
    def check(self, raw, chosen, ids=None):
        return verify_radar_value_transport(raw, chosen, PROFILE,
                                             ids if ids is not None else ['fixture.radar:run:0'])

    def test_adopted_frame_retains_all_points_values_units_and_times(self):
        original = frame()
        result = self.check([original], [adopted(copy.deepcopy(original))])
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['raw_frames'], 1)
        self.assertEqual(result['bundle_frames'], 1)
        self.assertEqual(result['checks'][0]['point_count'], 1)

    def test_small_float32_quantization_is_tolerated(self):
        original = frame()
        chosen = copy.deepcopy(original)
        chosen['points'][0]['power'] += 3e-8
        self.assertEqual(self.check([original], [adopted(chosen)])['errors'], [])

    def test_changed_point_coordinate_and_power_are_rejected(self):
        original = frame()
        for field in ('x', 'y', 'z', 'power'):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                changed['points'][0][field] += .1
                errors = self.check([original], [adopted(changed)])['errors']
                self.assertTrue(any(field in error for error in errors), errors)

    def test_availability_units_and_quality_cannot_be_fabricated(self):
        original = frame()
        for section, field, value in (('points', 'doppler_available', True),
                                      ('points', 'power_available', False),
                                      ('root', 'power_unit', 'dBm'),
                                      ('root', 'doppler_reference', 'unknown'),
                                      ('quality', 'confidence', 1.)):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                target = changed['points'][0] if section == 'points' else (
                    changed['quality'] if section == 'quality' else changed)
                target[field] = value
                errors = self.check([original], [adopted(changed)])['errors']
                self.assertTrue(any(field in error for error in errors), errors)

    def test_identity_scan_time_and_bundle_reference_are_checked(self):
        original = frame()
        for section, field, value in (('header', 'frame_id', 'base_link'),
                                      ('header', 'clock_id', 'sim:other'),
                                      ('root', 'scan_end', 4_000_000),
                                      ('header', 'timestamp', 2_000_001)):
            with self.subTest(field=field):
                changed = copy.deepcopy(original)
                target = changed['header'] if section == 'header' else changed
                target[field] = value
                errors = self.check([original], [adopted(changed)])['errors']
                self.assertTrue(any(field in error for error in errors), errors)
        mismatch = adopted(copy.deepcopy(original))
        mismatch['run_id'] = 'other'
        self.assertTrue(any('run_id' in err for err in
                            self.check([original], [mismatch])['errors']))

    def test_missing_duplicate_or_unexpected_publication_fails(self):
        original = frame()
        good = adopted(copy.deepcopy(original))
        self.assertTrue(any('coverage' in err for err in self.check([], [good])['errors']))
        self.assertTrue(any('duplicated' in err for err in
                            self.check([original, original], [good])['errors']))
        extra = frame('fixture.radar:run:1')
        self.assertTrue(any('coverage' in err for err in
                            self.check([original, extra], [good])['errors']))

    def test_empty_echo_stays_empty_and_does_not_imply_free(self):
        original = frame(points=[])
        self.assertEqual(self.check([original], [adopted(copy.deepcopy(original))])['errors'], [])
        changed = copy.deepcopy(original)
        changed['points'].append(frame()['points'][0])
        self.assertTrue(any('point count' in err for err in
                            self.check([original], [adopted(changed)])['errors']))


if __name__ == '__main__':
    unittest.main()
