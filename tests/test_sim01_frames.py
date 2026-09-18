"""SIM-01A 坐标、身份及失效传播的确定性契约检查。"""
import copy
import math
import unittest

from ufm_sensors.state_adapter import (
    adapt_state, frd_to_flu, ned_to_enu, orientation_ned_frd_to_enu_flu,
)


FRAMES = {
    "odom_origin_policy": "px4_estimator_local_origin",
    "body_origin_policy": "source_body_virtual_flu",
}


def sample():
    return {
        "header": {"schema_version": "0.1", "timestamp": 123456789000,
                   "clock_id": "sim:test", "run_id": "test",
                   "sample_id": "sim.odometry:1:1:123456789",
                   "frame_id": "world_ned", "source_type": "simulation",
                   "status": "valid", "reason": ""},
        "position": [1., 2., 3.], "orientation_xyzw": [0., 0., 0., 1.],
        "linear_velocity": [4., 5., 6.], "body_frame_id": "body_frd",
        "velocity_frame_id": "body_frd", "state_source": "estimated",
        "quality": {"confidence": None, "uncertainty": {
            "status": "unavailable", "value": None}},
    }


class FramesTest(unittest.TestCase):
    def assertSameRotation(self, actual, expected):
        self.assertAlmostEqual(abs(sum(a*b for a, b in zip(actual, expected))), 1., places=6)

    def test_axis_vectors_and_round_trip(self):
        for convert, expected in ((ned_to_enu, [2., 1., -3.]),
                                  (frd_to_flu, [1., -2., -3.])):
            self.assertEqual(convert([1., 2., 3.]), expected)
            self.assertEqual(convert(convert([1., 2., 3.])), [1., 2., 3.])

    def test_known_attitudes(self):
        s = math.sqrt(.5)
        for source, expected in (([0, 0, 0, 1], [0, 0, s, s]),
                                 ([0, 0, s, s], [0, 0, 0, 1]),
                                 ([s, 0, 0, s], [.5, .5, .5, .5])):
            with self.subTest(source=source):
                self.assertSameRotation(orientation_ned_frd_to_enu_flu(source), expected)

    def test_arbitrary_attitude_sign_and_inverse(self):
        q = [1/math.sqrt(30), 2/math.sqrt(30), 3/math.sqrt(30), 4/math.sqrt(30)]
        converted = orientation_ned_frd_to_enu_flu(q)
        self.assertSameRotation(converted, orientation_ned_frd_to_enu_flu([-x for x in q]))
        self.assertSameRotation(orientation_ned_frd_to_enu_flu(converted), q)

    def test_adapt_state_identity_frames_and_no_input_mutation(self):
        source = sample()
        before = copy.deepcopy(source)
        result = adapt_state(source, FRAMES)
        self.assertEqual(result["position"], [2., 1., -3.])
        self.assertEqual(result["linear_velocity"], [4., -5., -6.])
        self.assertEqual(result["body_frame_id"], "base_link")
        self.assertEqual(result["velocity_frame_id"], "base_link")
        self.assertEqual(result["header"]["frame_id"], "odom")
        self.assertEqual(result["header"]["source_type"], "derived")
        self.assertEqual(result["header"]["sample_id"], "sensors.state:"+source["header"]["sample_id"])
        for key in ("run_id", "clock_id", "timestamp"):
            self.assertEqual(result["header"][key], source["header"][key])
        self.assertEqual(result["state_source"], "estimated")
        result["position"][0] = 999
        self.assertEqual(source, before)

    def test_repeat_is_deterministic(self):
        self.assertEqual(adapt_state(sample(), FRAMES), adapt_state(sample(), FRAMES))

    def test_unknown_covariance_and_confidence_are_not_fabricated(self):
        source = sample()
        source["quality"] = {"confidence": 1., "uncertainty": {
            "status": "available", "value": [0.] * 36}}
        quality = adapt_state(source, FRAMES)["quality"]
        self.assertIsNone(quality["confidence"])
        self.assertEqual(quality["uncertainty"]["status"], "unavailable")
        self.assertIsNone(quality["uncertainty"]["value"])

    def test_unavailable_quality_provenance_is_preserved(self):
        source = sample()
        source["quality"]["uncertainty"].update(
            kind="position_covariance", unit="mixed m/rad products",
            source="PX4 EKF2 TODO: orientation covariance not propagated")
        original = copy.deepcopy(source["quality"])
        result = adapt_state(source, FRAMES)
        self.assertEqual(result["quality"], original)
        result["quality"]["uncertainty"]["source"] = "changed by consumer"
        self.assertEqual(source["quality"], original)

    def test_origin_policy_must_be_explicit(self):
        for config in ({}, {"odom_origin_policy": "px4_estimator_local_origin"},
                       dict(FRAMES, body_origin_policy="imu_is_body")):
            with self.assertRaises(ValueError):
                adapt_state(sample(), config)

    def test_source_frames_and_estimator_checked(self):
        for field, value in (("body_frame_id", "base_link"),
                             ("velocity_frame_id", "world_ned"),
                             ("state_source", "ground_truth")):
            source = sample()
            source[field] = value
            with self.assertRaises(ValueError):
                adapt_state(source, FRAMES)
        for field, value in (("frame_id", "odom"), ("source_type", "derived")):
            source = sample()
            source["header"][field] = value
            with self.assertRaises(ValueError):
                adapt_state(source, FRAMES)

    def test_invalid_geometry_rejected(self):
        for field, value in (("position", [float("nan"), 0, 0]),
                             ("linear_velocity", [0, float("inf"), 0]),
                             ("position", [1, 2]), ("position", ["1", 2, 3]),
                             ("orientation_xyzw", [0, 0, 0, 0]),
                             ("orientation_xyzw", [0, 0, 0, 2])):
            source = sample()
            source[field] = value
            with self.assertRaises(ValueError):
                adapt_state(source, FRAMES)

    def test_quaternion_tolerance(self):
        self.assertSameRotation(orientation_ned_frd_to_enu_flu([0, 0, 0, 1.0009]),
                                [0, 0, math.sqrt(.5), math.sqrt(.5)])
        with self.assertRaises(ValueError):
            orientation_ned_frd_to_enu_flu([0, 0, 0, 1.0011])
        for tolerance in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                orientation_ned_frd_to_enu_flu([0, 0, 0, 1], tolerance)

    def test_header_identity_and_time_rejected(self):
        for key, value in (("run_id", ""), ("sample_id", ""), ("clock_id", "sim:other"),
                           ("timestamp", -1), ("timestamp", 1.5), ("timestamp", True),
                           ("timestamp", 2**63), ("schema_version", "unknown"),
                           ("status", "unknown")):
            source = sample()
            source["header"][key] = value
            with self.assertRaises(ValueError):
                adapt_state(source, FRAMES)

    def test_terminal_propagates_without_geometry_or_origin_configuration(self):
        source = sample()
        source["header"].update(status="unavailable", reason="terminal:source_reset")
        source["position"] = [float("nan")]*3
        source["orientation_xyzw"] = [0]*4
        result = adapt_state(source, {})
        self.assertEqual(result["header"]["status"], "unavailable")
        self.assertEqual(result["header"]["reason"], "terminal:source_reset")
        self.assertEqual(result["header"]["timestamp"], source["header"]["timestamp"])
        self.assertEqual(result["header"]["frame_id"], "odom")
        source["header"]["run_id"] = ""
        with self.assertRaises(ValueError):
            adapt_state(source, FRAMES)

    def test_degraded_reason_preserved_and_missing_reason_rejected(self):
        source = sample()
        source["header"].update(status="degraded", reason="source_degraded")
        self.assertEqual(adapt_state(source, FRAMES)["header"]["reason"], "source_degraded")
        source["header"]["reason"] = ""
        with self.assertRaises(ValueError):
            adapt_state(source, FRAMES)


if __name__ == "__main__":
    unittest.main()
