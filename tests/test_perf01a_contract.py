"""PERF-01-A占位闭环的公开契约回归；不启动ROS master或研究模型。"""
import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for relative in ("mapping", "perception", "sensors", "simulation", "ros_ws"):
    sys.path.insert(0, str(ROOT / relative))

from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.placeholder import placeholder_infer
from ufm_sensors.perf01a_fixture import (build_sensor_bundle, make_fake_infrared,
                                          make_fake_radar,
                                          validate_bundle)
from ufm_simulation.perf01a_fixture import make_fixture_state
from ufm_sensors.state_adapter import adapt_state
from perf01a_metrics import PerfAggregator, percentile


def valid_bundle(run_id="perf-run", radar_timestamp=100_000_000,
                 infrared_timestamp=None, state_timestamp=None, point=(8.0, 0.0, 0.0)):
    infrared_timestamp = (radar_timestamp if infrared_timestamp is None
                          else infrared_timestamp)
    state_timestamp = (radar_timestamp if state_timestamp is None else state_timestamp)
    radar = make_fake_radar(run_id, 1, radar_timestamp, point=point)
    infrared = make_fake_infrared(run_id, 1, infrared_timestamp)
    state = adapt_state(make_fixture_state(run_id, 1, state_timestamp), {
        "odom_origin_policy": "px4_estimator_local_origin",
        "body_origin_policy": "source_body_virtual_flu"})
    state["orientation_xyzw"] = [0.0, 0.0, 0.0, 1.0]
    bundle, reason = build_sensor_bundle(radar, infrared, [state])
    if bundle is None:
        raise AssertionError(reason)
    return bundle


class SensorAndPerceptionContractTest(unittest.TestCase):
    def test_points_in_one_voxel_produce_one_observed_cell(self):
        bundle = valid_bundle()
        point = dict(bundle['radar']['points'][0], x=8.01)
        bundle['radar']['points'].extend([point, dict(point)])
        observation = placeholder_infer(bundle)
        self.assertEqual(len(observation['voxels']), 1)
        self.assertEqual(observation['voxels'][0]['probability'], .9)
        local_map = SparseLocalMap()
        self.assertTrue(local_map.update(observation))
        self.assertEqual(len(local_map.cells), 1)

    def test_rotated_translated_state_places_point_in_odom(self):
        state = adapt_state(make_fixture_state("run-a", 1, 100), {
            "odom_origin_policy": "px4_estimator_local_origin",
            "body_origin_policy": "source_body_virtual_flu"})
        state["position"] = [1.0, 2.0, 3.0]
        bundle, reason = build_sensor_bundle(make_fake_radar("run-a", 1, 100, (4, 0, 0)),
                                            make_fake_infrared("run-a", 1, 100), [state])
        self.assertEqual(reason, "")
        observation = placeholder_infer(bundle)
        self.assertEqual(observation["voxels"][0]["index"], [34, 28, 14])
        self.assertEqual(observation["context"]["source_frame_id"], "odom")
        self.assertEqual(observation["context"]["T_mapping_source"][3], 0.0)
        self.assertEqual(observation["context"]["T_mapping_body"][3], 1.0)

    def test_context_requires_adapted_pose_and_fixture_calibration(self):
        radar = make_fake_radar("run-a", 1, 100)
        infrared = make_fake_infrared("run-a", 1, 100)
        state = make_fixture_state("run-a", 1, 100)
        bundle, reason = build_sensor_bundle(radar, infrared, [state])
        self.assertIsNone(bundle)
        self.assertEqual(reason, "pose_frame_mismatch")
        state = valid_bundle("run-a", 100)["state"]
        bundle, reason = build_sensor_bundle(radar, infrared, [state], calibration_id="unknown")
        self.assertIsNone(bundle)
        self.assertEqual(reason, "calibration_unavailable")
        state["orientation_xyzw"] = [0, 0, 0, 0]
        bundle, reason = build_sensor_bundle(radar, infrared, [state])
        self.assertIsNone(bundle)
        self.assertEqual(reason, "pose_invalid")

    def test_valid_bundle_preserves_time_and_excludes_lidar(self):
        bundle = valid_bundle()
        self.assertEqual(bundle["header"]["timestamp"], 100_000_000)
        self.assertEqual(bundle["radar_ir_delta_ns"], 0)
        self.assertEqual(bundle["pose_age_ns"], 0)
        self.assertTrue(validate_bundle(bundle))
        for forbidden in ("lidar", "occupancy_target", "observed_mask"):
            invalid = copy.deepcopy(bundle)
            invalid[forbidden] = []
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(ValueError):
                    validate_bundle(invalid)

    def test_sync_pose_and_run_fail_closed(self):
        radar = make_fake_radar("run-a", 1, 100_000_000)
        infrared = make_fake_infrared("run-a", 1, 106_000_000)
        state = make_fixture_state("run-a", 1, 100_000_000)
        bundle, reason = build_sensor_bundle(radar, infrared, [state])
        self.assertIsNone(bundle)
        self.assertEqual(reason, "radar_ir_timeout")

        state = make_fixture_state("run-a", 1, 0)
        bundle, reason = build_sensor_bundle(radar, make_fake_infrared("run-a", 1, 100_000_000), [state])
        self.assertIsNone(bundle)
        self.assertEqual(reason, "pose_age_exceeded")

        state = make_fixture_state("run-b", 1, 100_000_000)
        bundle, reason = build_sensor_bundle(radar, make_fake_infrared("run-a", 1, 100_000_000), [state])
        self.assertIsNone(bundle)
        self.assertEqual(reason, "pose_run_mismatch")

    def test_placeholder_only_emits_observed_occupancy(self):
        occupancy = placeholder_infer(valid_bundle())
        self.assertEqual(occupancy["header"]["source_type"], "fixture")
        self.assertEqual(len(occupancy["voxels"]), 1)
        self.assertTrue(occupancy["voxels"][0]["observed"])
        unavailable = copy.deepcopy(valid_bundle())
        unavailable["header"].update(status="unavailable", reason="sensor timeout")
        degraded = placeholder_infer(unavailable)
        self.assertEqual(degraded["header"]["status"], "unavailable")
        self.assertEqual(degraded["voxels"], [])

    def test_unavailable_transform_never_produces_observed_voxels(self):
        bundle = valid_bundle()
        bundle["context"]["T_mapping_source_status"] = "unavailable"
        observation = placeholder_infer(bundle)
        self.assertEqual(observation["header"]["status"], "unavailable")
        self.assertEqual(observation["header"]["reason"], "transform_unavailable")
        self.assertEqual(observation["voxels"], [])
        bundle = valid_bundle()
        bundle["context"]["T_mapping_source"] = [0.0] * 16
        with self.assertRaises(ValueError):
            placeholder_infer(bundle)


class LocalMapContractTest(unittest.TestCase):
    def test_invalid_header_is_rejected_without_seeding_map(self):
        for key, value in (('schema_version', 'unsupported'), ('timestamp', -1),
                           ('run_id', ''), ('sample_id', ''), ('source_type', 'unknown')):
            local_map = SparseLocalMap()
            before = local_map.snapshot()
            observation = placeholder_infer(valid_bundle())
            observation['header'][key] = value
            if key == 'timestamp':
                observation['context']['reference_timestamp'] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                local_map.update(observation)
            self.assertEqual(local_map.snapshot(), before)

    def test_dedup_unknown_stale_and_run_isolation(self):
        local_map = SparseLocalMap(staleness_limit_ns=50, max_active_cells=2)
        observation = placeholder_infer(valid_bundle())
        self.assertTrue(local_map.update(observation))
        self.assertFalse(local_map.update(copy.deepcopy(observation)))
        conflict = copy.deepcopy(observation)
        conflict["voxels"][0]["probability"] = 0.1
        with self.assertRaises(ValueError):
            local_map.update(conflict)

        unknown = copy.deepcopy(observation)
        unknown["header"]["sample_id"] = "perception.occupancy:unknown"
        unknown["header"]["timestamp"] += 1
        unknown["context"]["reference_timestamp"] += 1
        unknown["voxels"] = [dict(index=[1, 1, 1], probability=0.5, observed=False)]
        self.assertTrue(local_map.update(unknown))
        self.assertEqual(len(local_map.cells), 1)
        self.assertEqual(local_map.stale_cells(100_000_151), [(48, 16, 8)])

        other_run = copy.deepcopy(observation)
        other_run["header"].update(run_id="other", clock_id="sim:other", sample_id="other")
        with self.assertRaises(ValueError):
            local_map.update(other_run)

    def test_rolling_limit_keeps_recent_cells(self):
        local_map = SparseLocalMap(shape=(8, 8, 8), origin=(0, 0, 0), max_active_cells=2)
        for sequence, index in enumerate(([0, 0, 0], [1, 1, 1], [2, 2, 2]), start=1):
            index = [sequence - 1] * 3
            point = [(sequence - 1) * 0.5 + 0.1] * 3
            observation = placeholder_infer(valid_bundle(radar_timestamp=sequence * 100,
                                                         point=point),
                                            shape=(8, 8, 8), origin=(0.0, 0.0, 0.0))
            observation["header"]["sample_id"] += ":%d" % sequence
            observation["voxels"][0]["index"] = index
            self.assertTrue(local_map.update(observation))
        self.assertEqual(set(local_map.cells), {(1, 1, 1), (2, 2, 2)})

    def test_rejects_geometry_context_and_old_observations_atomically(self):
        observation = placeholder_infer(valid_bundle())
        invalid_updates = [
            ("resolution", [1, 1, 1]), ("origin", [0, 0, 0]),
            ("shape", [1, 1, 1]),
        ]
        for key, value in invalid_updates:
            candidate = copy.deepcopy(observation)
            candidate[key] = value
            local_map = SparseLocalMap()
            with self.subTest(key=key), self.assertRaises(ValueError):
                local_map.update(candidate)
            self.assertEqual(local_map.snapshot()["header"]["status"], "unavailable")
        for key, value in (("source_frame_id", "radar"),
                           ("reference_timestamp", 99),
                           ("T_mapping_source_status", "unavailable")):
            candidate = copy.deepcopy(observation)
            candidate["context"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                SparseLocalMap().update(candidate)
        local_map = SparseLocalMap()
        local_map.update(observation)
        before = local_map.snapshot()
        old = placeholder_infer(valid_bundle(radar_timestamp=99))
        with self.assertRaises(ValueError):
            local_map.update(old)
        self.assertEqual(before, local_map.snapshot())

    def test_unavailable_first_observation_does_not_validate_map(self):
        observation = placeholder_infer(valid_bundle())
        observation["header"].update(status="unavailable", reason="timeout")
        observation["voxels"] = []
        local_map = SparseLocalMap()
        self.assertFalse(local_map.update(observation))
        self.assertEqual(local_map.snapshot()["header"]["status"], "unavailable")
        self.assertEqual(local_map.cells, {})

    def test_invalid_late_voxel_cannot_partially_modify_map(self):
        local_map = SparseLocalMap()
        observation = placeholder_infer(valid_bundle())
        observation["voxels"].append(dict(index=[999, 0, 0], probability=.9, observed=True))
        with self.assertRaises(ValueError):
            local_map.update(observation)
        self.assertEqual(local_map.cells, {})
        self.assertEqual(local_map.snapshot()["revision"], 0)

    def test_old_delivery_rejected_after_many_newer_observations(self):
        local_map = SparseLocalMap(max_active_cells=2)
        first = placeholder_infer(valid_bundle(radar_timestamp=1))
        for timestamp in range(1, 258):
            observation = placeholder_infer(valid_bundle(radar_timestamp=timestamp))
            observation["header"]["sample_id"] += ":%d" % timestamp
            self.assertTrue(local_map.update(observation))
        revision = local_map.snapshot()["revision"]
        with self.assertRaises(ValueError):
            local_map.update(first)
        self.assertEqual(local_map.snapshot()["revision"], revision)
        self.assertEqual(len(local_map.cells), 1)


def event(root, stage, monotonic_ns, status="valid", metric=0):
    return dict(run_id="perf-run", sample_id=root + ":" + stage,
                parent_sample_id=root, stage=stage, monotonic_ns=monotonic_ns,
                metric_value_ns=metric, business_timestamp=monotonic_ns,
                clock_id="sim:perf-run", status=status, reason="" if status == "valid" else "timeout")


class PerfMetricsContractTest(unittest.TestCase):
    def test_nearest_rank_percentiles(self):
        self.assertEqual(percentile([5, 1, 3, 2, 4], .50), 3.0)
        self.assertEqual(percentile([5, 1, 3, 2, 4], .99), 5.0)
        self.assertIsNone(percentile([], .50))

    def test_identity_closure_and_rejection_counts(self):
        aggregator = PerfAggregator("perf-run")
        stages = ("radar_receive", "sensor_bundle_ready", "occupancy_ready", "map_snapshot_publish")
        for offset, stage in enumerate(stages):
            aggregator.record(event("sample-a", stage, 100 + offset * 10, metric=offset * 10))
        aggregator.record(event("sample-b", "radar_receive", 200))
        aggregator.record(event("sample-b", "sensor_bundle_ready", 210, status="timeout"))
        report = aggregator.report(finished_ns=300)
        self.assertEqual(report["unique_radar_samples"], 2)
        self.assertEqual(report["closed_samples"], 1)
        self.assertEqual(report["identity_closure_rate"], 0.5)
        self.assertEqual(report["timeout_count"], 1)
        self.assertIn("map_snapshot_publish", report["missing_stages"])
        self.assertEqual(report["latency_percentiles"]["sensor_to_map_ns"]["p50"], 30.0)


if __name__ == "__main__":
    unittest.main()
