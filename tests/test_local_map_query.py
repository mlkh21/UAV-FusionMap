"""Local Map query contract tests; no ROS master or hardware required."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for relative in ("mapping", "perception", "sensors", "ros_ws"):
    sys.path.insert(0, str(ROOT / relative))

from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.placeholder import placeholder_infer
from test_perf01a_contract import valid_bundle


def observation(timestamp=100, point=(8.0, 0.0, 0.0), probability=0.9,
                run_id="perf-run"):
    result = placeholder_infer(valid_bundle(run_id=run_id, radar_timestamp=timestamp,
                                           point=point))
    result["voxels"][0]["probability"] = probability
    return result


class LocalMapQueryTest(unittest.TestCase):
    def query(self, local_map, **overrides):
        args = dict(map_id="perf01a-local", frame_id="odom", run_id="perf-run",
                    clock_id="sim:perf-run", query_timestamp=100,
                    point=(8.0, 0.0, 0.0), max_age_ns=50)
        args.update(overrides)
        return local_map.query(**args)

    def test_fresh_probability_is_classified_only_with_explicit_thresholds(self):
        local_map = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        self.assertTrue(local_map.update(observation(probability=0.9)))
        result = self.query(local_map)
        self.assertEqual(result["status"], "occupied")
        self.assertEqual(result["probability"], 0.9)
        self.assertEqual(result["revision"], 1)
        self.assertEqual(result["last_observed_timestamp"], 100)
        self.assertEqual(result["index"], [48, 16, 8])

        free_map = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        free_map.update(observation(probability=0.1))
        self.assertEqual(self.query(free_map)["status"], "free")

    def test_missing_thresholds_preserve_probability_as_unknown(self):
        local_map = SparseLocalMap()
        local_map.update(observation(probability=0.9))
        result = self.query(local_map)
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["reason"], "classification_thresholds_unconfigured")
        self.assertEqual(result["probability"], 0.9)

    def test_unobserved_and_outside_points_are_unknown(self):
        local_map = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        local_map.update(observation())
        missing = self.query(local_map, point=(0.0, 0.0, 0.0))
        self.assertEqual(missing["status"], "unknown")
        self.assertEqual(missing["reason"], "no_observation")
        outside = self.query(local_map, point=(16.0, 0.0, 0.0))
        self.assertEqual(outside["status"], "unknown")
        self.assertEqual(outside["reason"], "outside_coverage")
        self.assertIsNone(outside["index"])

    def test_large_finite_outside_points_do_not_overflow_or_mutate_map(self):
        local_map = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        local_map.update(observation())
        before = local_map.snapshot()
        for axis in range(3):
            for value in (-1e308, 1e308):
                point = [0.0, 0.0, 0.0]
                point[axis] = value
                with self.subTest(point=point):
                    result = self.query(local_map, point=point)
                    self.assertEqual(result["status"], "unknown")
                    self.assertEqual(result["reason"], "outside_coverage")
                    self.assertIsNone(result["index"])
                    self.assertIsNone(result["probability"])
        self.assertEqual(local_map.snapshot(), before)

    def test_age_boundary_and_future_query_time(self):
        local_map = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        local_map.update(observation(timestamp=100))
        self.assertEqual(self.query(local_map, query_timestamp=150,
                                   max_age_ns=50)["status"], "occupied")
        stale = self.query(local_map, query_timestamp=151, max_age_ns=50)
        self.assertEqual(stale["status"], "stale")
        self.assertEqual(stale["probability"], 0.9)
        future = self.query(local_map, query_timestamp=99)
        self.assertEqual(future["status"], "unavailable")
        self.assertEqual(future["reason"], "query_before_latest_map_time")

    def test_identity_mismatch_and_empty_map_are_unavailable(self):
        local_map = SparseLocalMap()
        empty = self.query(local_map)
        self.assertEqual(empty["status"], "unavailable")
        self.assertEqual(empty["reason"], "map_unavailable")
        local_map.update(observation())
        for override in ({"map_id": "other"}, {"frame_id": "map"},
                         {"run_id": "other"}, {"clock_id": "wall"}):
            with self.subTest(override=override):
                result = self.query(local_map, **override)
                self.assertEqual(result["status"], "unavailable")

    def test_invalid_thresholds_and_requests_fail_without_mutation(self):
        for kwargs in ({"free_threshold": 0.7, "occupied_threshold": 0.7},
                       {"free_threshold": -0.1, "occupied_threshold": 0.7},
                       {"free_threshold": 0.2}, {"occupied_threshold": 0.8}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                SparseLocalMap(**kwargs)
        local_map = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        local_map.update(observation())
        before = copy.deepcopy(local_map.snapshot())
        for override in ({"max_age_ns": -1}, {"query_timestamp": -1},
                         {"point": (float("nan"), 0.0, 0.0)}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.query(local_map, **override)
        self.assertEqual(local_map.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
