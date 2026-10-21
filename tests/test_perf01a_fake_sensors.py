"""功能级fake Radar/IR参数化回归。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sensors"))

from ufm_sensors.perf01a_fixture import (make_fake_infrared, make_fake_radar,
                                          make_motion_radar)


class FakeSensorParameterTest(unittest.TestCase):
    def test_defaults_preserve_fixed_fixture_values(self):
        radar = make_fake_radar("r", 0, 100)
        infrared = make_fake_infrared("r", 0, 100)
        self.assertEqual(len(radar["points"]), 1)
        self.assertEqual([radar["points"][0][key] for key in ("x", "y", "z", "power")],
                         [8.0, 0.0, 0.0, 1.0])
        self.assertEqual(radar["scan_start"], radar["scan_end"])
        self.assertEqual(infrared["image"], [0.5] * 4)
        self.assertEqual(infrared["exposure_start"], infrared["exposure_end"])

    def test_radar_fov_and_range_gate_returns_without_marking_free_space(self):
        visible = make_fake_radar("r", 0, 100, point=(5.0, 0.0, 0.0),
                                  fov_deg=(90.0, 30.0), max_range_m=6.0)
        side = make_fake_radar("r", 0, 100, point=(5.0, 5.1, 0.0),
                               fov_deg=(90.0, 30.0), max_range_m=20.0)
        far = make_fake_radar("r", 0, 100, point=(7.0, 0.0, 0.0),
                              fov_deg=(90.0, 30.0), max_range_m=6.0)
        self.assertEqual(len(visible["points"]), 1)
        self.assertEqual(side["points"], [])
        self.assertEqual(far["points"], [])

    def test_motion_radar_keeps_doppler_unavailable_when_parameterized(self):
        radar = make_motion_radar("r", 3, 2_000_000, 0.0,
                                  [(1.0, 5.0, 0.0), (20.0, 5.0, 0.0)],
                                  fov_deg=(120.0, 30.0), max_range_m=10.0,
                                  scan_duration_ns=2_000_000)
        self.assertEqual(len(radar["points"]), 1)
        self.assertFalse(radar["points"][0]["doppler_available"])
        self.assertEqual(radar["scan_start"], 1_000_000)
        self.assertEqual(radar["scan_end"] - radar["scan_start"], 2_000_000)

    def test_seeded_radar_and_ir_noise_is_reproducible(self):
        radar_args = dict(point=(8.0, 0.0, 0.0), position_noise_std_m=.1,
                          power_noise_std=.2, seed=23)
        first = make_fake_radar("r", 4, 100, **radar_args)
        second = make_fake_radar("r", 4, 100, **radar_args)
        changed = make_fake_radar("r", 5, 100, **radar_args)
        self.assertEqual(first["points"], second["points"])
        self.assertNotEqual(first["points"], changed["points"])

        ir_args = dict(width=2, height=2, background_value=.4, noise_std=.1, seed=23)
        first_ir = make_fake_infrared("r", 4, 100, **ir_args)
        second_ir = make_fake_infrared("r", 4, 100, **ir_args)
        self.assertEqual(first_ir["image"], second_ir["image"])
        self.assertNotEqual(first_ir["image"], [.4] * 4)

        timed_ir = make_fake_infrared("r", 4, 100, exposure_duration_ns=20)
        self.assertEqual((timed_ir["exposure_start"], timed_ir["exposure_end"]), (90, 110))

    def test_zero_noise_full_ir_avoids_random_draws_without_changing_pixels(self):
        with patch('ufm_sensors.perf01a_fixture._sample_rng',
                   side_effect=AssertionError('zero noise must not sample')):
            frame = make_fake_infrared('r', 0, 0, 640, 512, background_value=.4,
                hotspots=[dict(x_px=1, y_px=1, radius_px=0, value=.5)], seed=23)
        self.assertEqual(len(frame['image']), 640 * 512)
        self.assertEqual(frame['image'][0], .4)
        self.assertAlmostEqual(frame['image'][641], .9)
        self.assertEqual(frame['image'][-1], .4)

    def test_ir_hotspots_use_row_major_pixels_and_overlap_additively(self):
        infrared = make_fake_infrared(
            "r", 0, 100, width=4, height=3, background_value=.2,
            hotspots=[
                dict(x_px=1, y_px=1, radius_px=0, value=.5),
                dict(x_px=2, y_px=1, radius_px=1, value=.3),
            ])
        self.assertEqual(infrared["image"], [.2, .2, .5, .2,
                                              .2, 1.0, .5, .5,
                                              .2, .2, .5, .2])

    def test_ir_hotspot_validation_fails_closed(self):
        with self.assertRaises(ValueError):
            make_fake_infrared("r", 0, 0, width=2, height=2,
                               hotspots=[dict(x_px=2, y_px=0, value=1.)])
        with self.assertRaises(ValueError):
            make_fake_infrared("r", 0, 0, hotspots=[dict(x_px=0, y_px=0, radius_px=-1)])
        with self.assertRaises(ValueError):
            make_fake_infrared("r", 0, 0, hotspots=[dict(x_px=0, y_px=0, value=float('nan'))])

    def test_invalid_parameter_ranges_fail_closed(self):
        with self.assertRaises(ValueError):
            make_fake_radar("r", 0, 0, fov_deg=(0.0, 30.0))
        with self.assertRaises(ValueError):
            make_fake_radar("r", 0, 0, max_range_m=0.0)
        with self.assertRaises(ValueError):
            make_fake_infrared("r", 0, 0, noise_std=-.1)
        with self.assertRaises(ValueError):
            make_fake_infrared("r", 0, 0, exposure_duration_ns=-1)
        with self.assertRaises(ValueError):
            make_fake_infrared("r", 0, 0, exposure_duration_ns=2)


if __name__ == "__main__":
    unittest.main()
