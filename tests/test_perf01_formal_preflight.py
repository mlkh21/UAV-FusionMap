"""Pure-Python contract tests for the PERF-01 formal evidence preflight."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ros_ws"))

from perf01_formal_preflight import (  # noqa: E402
    SCHEMA_VERSION,
    evaluate_formal_preflight,
)


class Perf01FormalPreflightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load((ROOT / "configs/perf01_budget.yaml").read_text())

    def _confirmed_config(self):
        config = copy.deepcopy(self.config)
        config["target_airborne_platform"]["status"] = "confirmed_selected_platform"
        config["reference_sensors"]["radar"].update(
            status="confirmed_selected_sensor", frequency_hz=20.0, timestamp_error_ms=1.0)
        config["reference_sensors"]["infrared"].update(
            status="confirmed_selected_sensor", timestamp_error_ms=1.0)
        config["formal_measurement"].update(
            status="confirmed",
            target_platform_id="platform-01",
            start_endpoint="radar_capture_timestamp",
            end_endpoint="occupancy_ready",
            sampling_clock_source="ptp",
            clock_domain_mapping="ptp-to-monotonic-v1",
            continuous_duration_s=2.0,
        )
        return config

    def _manifest(self, run_directory, config):
        formal = config["formal_measurement"]
        platform = config["target_airborne_platform"]
        radar = config["reference_sensors"]["radar"]
        infrared = config["reference_sensors"]["infrared"]
        rows = [{"sample_id": "radar-%d" % index,
                 "start_monotonic_ns": index * 50_000_000,
                 "end_monotonic_ns": index * 50_000_000 + 10_000_000}
                for index in range(41)]
        contents = {
            "monotonic_stage_timestamps": {
                "start_endpoint": formal["start_endpoint"],
                "end_endpoint": formal["end_endpoint"], "samples": rows},
            "p50_p95_p99_latency": {"sample_count": len(rows),
                                     "percentiles_ms": {"p50": 10.0, "p95": 10.0, "p99": 10.0}},
            "sensor_sync_and_pose_age": {"samples": [
                {"sample_id": row["sample_id"], "radar_ir_delta_ms": 1.0, "pose_age_ms": 2.0}
                for row in rows]},
            "input_output_drop_duplicate_out_of_order_rates": {
                "input_count": len(rows), "output_count": len(rows), "drop_count": 0,
                "timeout_count": 0, "duplicate_count": 0, "out_of_order_count": 0},
            "resource_and_power_measurement": {"samples": [
                {"monotonic_ns": timestamp, "power_w": 12.0, "rss_mb": 512.0,
                 "cpu_percent": 20.0, "gpu_percent": 30.0, "npu_percent": 10.0,
                 "temperature_c": 50.0} for timestamp in (0, 2_050_000_000)]},
            "continuous_run_stability": {"start_monotonic_ns": 0,
                                         "end_monotonic_ns": 2_050_000_000,
                                         "restart_count": 0, "unexpected_terminal_count": 0},
        }
        evidence = {}
        for field, data in contents.items():
            filename = field + ".json"
            (run_directory / filename).write_text(json.dumps({
                "run_id": "perf01-formal-01", "speed_mps": 35.0,
                "source_type": "measured", "clock_source": formal["sampling_clock_source"],
                "data": data,
            }))
            evidence[field] = filename
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "COMPLETE",
            "exit": 0,
            "measurement_complete": True,
            "run_id": "perf01-formal-01",
            "speed_mps": 35.0,
            "run_directory": str(run_directory),
            "target_platform": {
                "id": formal["target_platform_id"],
                "status": "confirmed_selected_platform",
                "model": platform["model"],
                "power_mode": platform["power_mode"],
                "measurement_method": platform["measurement_method"],
            },
            "sensors": {
                "radar": {
                    "status": "confirmed_selected_sensor",
                    "model": radar["model"],
                    "physical_sampling_frequency_hz": radar["frequency_hz"],
                    "sampling_frequency_source": "device_measurement",
                    "sampling_clock_source": formal["sampling_clock_source"],
                    "timestamp_error_ms": radar["timestamp_error_ms"],
                },
                "infrared": {
                    "status": "confirmed_selected_sensor",
                    "model": infrared["model"],
                    "variant": infrared["variant"],
                    "physical_sampling_frequency_hz": infrared["frame_rate_hz"],
                    "sampling_frequency_source": "hardware_capture",
                    "sampling_clock_source": formal["sampling_clock_source"],
                    "timestamp_error_ms": infrared["timestamp_error_ms"],
                },
            },
            "measurement": {
                "start_endpoint": formal["start_endpoint"],
                "end_endpoint": formal["end_endpoint"],
                "sampling_clock_source": formal["sampling_clock_source"],
                "clock_domain_mapping": formal["clock_domain_mapping"],
                "continuous_duration_s": formal["continuous_duration_s"],
                "duration_clock_source": formal["sampling_clock_source"],
            },
            "evidence": evidence,
        }

    def _check_with_change(self, change):
        config = self._confirmed_config()
        with tempfile.TemporaryDirectory() as directory:
            run_directory = Path(directory)
            manifest = self._manifest(run_directory, config)
            change(config, manifest, run_directory)
            manifest_path = run_directory / "formal-manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            return evaluate_formal_preflight(config, manifest, manifest_path)

    @staticmethod
    def _change_evidence(manifest, run_directory, name, change):
        path = run_directory / manifest["evidence"][name]
        payload = json.loads(path.read_text())
        change(payload)
        path.write_text(json.dumps(payload))

    def test_repository_budget_is_not_formal_ready(self):
        result = evaluate_formal_preflight(self.config, {})
        self.assertFalse(result["ready"])
        self.assertEqual(result["mode"], "reference_only")
        self.assertTrue(any("target airborne platform" in item for item in result["blockers"]))

    def test_complete_manifest_passes_without_ros(self):
        config = self._confirmed_config()
        with tempfile.TemporaryDirectory() as directory:
            run_directory = Path(directory)
            manifest = self._manifest(run_directory, config)
            manifest_path = run_directory / "formal-manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            result = evaluate_formal_preflight(config, manifest, manifest_path)
        self.assertTrue(result["ready"])
        self.assertEqual(result["mode"], "formal_ready")
        self.assertEqual(result["blockers"], [])
        self.assertEqual(result["errors"], [])

    def test_fixture_frequency_cannot_replace_physical_frequency(self):
        config = self._confirmed_config()
        with tempfile.TemporaryDirectory() as directory:
            run_directory = Path(directory)
            manifest = self._manifest(run_directory, config)
            radar = manifest["sensors"]["radar"]
            radar.pop("physical_sampling_frequency_hz")
            radar["fixture_frequency_hz"] = 20.0
            radar["sampling_frequency_source"] = "fixture"
            manifest_path = run_directory / "formal-manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            result = evaluate_formal_preflight(config, manifest, manifest_path)
        self.assertFalse(result["ready"])
        self.assertTrue(any("physical_sampling_frequency_hz" in item for item in result["blockers"]))
        self.assertTrue(any("fixture or simulation" in item for item in result["blockers"]))

    def test_each_sensor_requires_sampling_clock_source(self):
        for sensor in ("radar", "infrared"):
            with self.subTest(sensor=sensor):
                def missing(config, manifest, directory):
                    manifest["sensors"][sensor].pop("sampling_clock_source")
                result = self._check_with_change(missing)
                self.assertFalse(result["ready"])
                self.assertTrue(any("sensors.%s.sampling_clock_source" % sensor in item
                                    for item in result["blockers"]))

    def test_sensor_timestamp_error_must_be_finite(self):
        for sensor in ("radar", "infrared"):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(sensor=sensor, source="manifest", value=value):
                    def invalid_manifest(config, manifest, directory):
                        manifest["sensors"][sensor]["timestamp_error_ms"] = value
                    result = self._check_with_change(invalid_manifest)
                    self.assertFalse(result["ready"])
                    self.assertTrue(any("sensors.%s.timestamp_error_ms" % sensor in item
                                        for item in result["blockers"]))
                with self.subTest(sensor=sensor, source="budget", value=value):
                    def invalid_budget(config, manifest, directory):
                        config["reference_sensors"][sensor]["timestamp_error_ms"] = value
                    result = self._check_with_change(invalid_budget)
                    self.assertFalse(result["ready"])
                    self.assertTrue(any("reference_sensors.%s timestamp_error_ms" % sensor in item
                                        for item in result["blockers"]))

    def test_simulation_time_cannot_replace_sampling_clock_or_duration(self):
        config = self._confirmed_config()
        with tempfile.TemporaryDirectory() as directory:
            run_directory = Path(directory)
            manifest = self._manifest(run_directory, config)
            measurement = manifest["measurement"]
            measurement.pop("sampling_clock_source")
            measurement.pop("duration_clock_source")
            measurement["simulation_time_s"] = 2400.0
            manifest_path = run_directory / "formal-manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            result = evaluate_formal_preflight(config, manifest, manifest_path)
        self.assertFalse(result["ready"])
        self.assertTrue(any("sampling_clock_source is required" in item for item in result["errors"]))
        self.assertTrue(any("duration_clock_source is required" in item for item in result["errors"]))

    def test_missing_evidence_and_wrong_run_directory_fail_closed(self):
        config = self._confirmed_config()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_directory = root / "run"
            run_directory.mkdir()
            manifest = self._manifest(run_directory, config)
            missing = config["validation"]["required_evidence"][0]
            (run_directory / manifest["evidence"][missing]).unlink()
            manifest["run_directory"] = str(root)
            manifest_path = run_directory / "formal-manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            result = evaluate_formal_preflight(config, manifest, manifest_path)
        self.assertFalse(result["ready"])
        self.assertTrue(any("does not contain the manifest" in item for item in result["blockers"]))
        self.assertTrue(any("required evidence file is missing" in item for item in result["blockers"]))

    def test_malformed_nested_input_fails_closed_without_exception(self):
        config = self._confirmed_config()
        config["formal_measurement"] = None
        result = evaluate_formal_preflight(config, {"schema_version": "wrong"})
        self.assertFalse(result["ready"])
        self.assertTrue(result["errors"] or result["blockers"])

    def test_non_mapping_budget_fails_closed_without_exception(self):
        result = evaluate_formal_preflight([], {})
        self.assertFalse(result["ready"])
        self.assertEqual(result["mode"], "reference_only")
        self.assertTrue(any("budget config must be a mapping" in item
                            for item in result["errors"]))

    def test_empty_or_passed_only_evidence_cannot_be_formal_ready(self):
        for text in ("", "{}", '{"passed": true}'):
            with self.subTest(text=text):
                def change(config, manifest, directory):
                    (directory / manifest["evidence"]["p50_p95_p99_latency"]).write_text(text)
                result = self._check_with_change(change)
                self.assertFalse(result["ready"])
                self.assertTrue(result["blockers"] or result["errors"])

    def test_reported_p99_must_match_samples_and_meet_20_ms(self):
        def forged(config, manifest, directory):
            self._change_evidence(manifest, directory, "p50_p95_p99_latency",
                                  lambda value: value["data"]["percentiles_ms"].update(p99=19.0))
        result = self._check_with_change(forged)
        self.assertFalse(result["ready"])
        self.assertTrue(any("p99" in item for item in result["blockers"]))

        def one_outlier(config, manifest, directory):
            self._change_evidence(manifest, directory, "monotonic_stage_timestamps",
                                  lambda value: value["data"]["samples"][-1].update(
                                      end_monotonic_ns=2_020_001_000))
        result = self._check_with_change(one_outlier)
        self.assertFalse(result["ready"])
        self.assertTrue(any("end_to_end_age" in item for item in result["blockers"]))

        def slow(config, manifest, directory):
            self._change_evidence(manifest, directory, "monotonic_stage_timestamps",
                                  lambda value: value["data"]["samples"][-1].update(
                                      end_monotonic_ns=2_030_000_000))
            self._change_evidence(manifest, directory, "p50_p95_p99_latency",
                                  lambda value: value["data"]["percentiles_ms"].update(p99=30.0))
        result = self._check_with_change(slow)
        self.assertFalse(result["ready"])
        self.assertTrue(any("p99" in item for item in result["blockers"]))

    def test_sync_pose_drop_and_timeout_limits_fail_closed(self):
        def sync(config, manifest, directory):
            self._change_evidence(manifest, directory, "sensor_sync_and_pose_age",
                                  lambda value: value["data"]["samples"][0].update(
                                      radar_ir_delta_ms=5.001, pose_age_ms=10.001))
        result = self._check_with_change(sync)
        self.assertFalse(result["ready"])
        self.assertTrue(any("radar_ir_delta_ms" in item for item in result["blockers"]))
        self.assertTrue(any("pose_age_ms" in item for item in result["blockers"]))

        def drops(config, manifest, directory):
            self._change_evidence(manifest, directory, "input_output_drop_duplicate_out_of_order_rates",
                                  lambda value: value["data"].update(
                                      input_count=42, output_count=41, drop_count=1, timeout_count=1))
        result = self._check_with_change(drops)
        self.assertFalse(result["ready"])
        self.assertTrue(any("drop_rate" in item for item in result["blockers"]))
        self.assertTrue(any("timeout_rate" in item for item in result["blockers"]))

    def test_zero_samples_wrong_identity_and_short_duration_fail_closed(self):
        def zero(config, manifest, directory):
            self._change_evidence(manifest, directory, "monotonic_stage_timestamps",
                                  lambda value: value["data"].update(samples=[]))
        result = self._check_with_change(zero)
        self.assertFalse(result["ready"])

        def identity(config, manifest, directory):
            self._change_evidence(manifest, directory, "sensor_sync_and_pose_age",
                                  lambda value: value.update(run_id="other-run"))
        result = self._check_with_change(identity)
        self.assertFalse(result["ready"])
        self.assertTrue(any("run_id" in item for item in result["blockers"]))

        def duration(config, manifest, directory):
            self._change_evidence(manifest, directory, "continuous_run_stability",
                                  lambda value: value["data"].update(end_monotonic_ns=1_000_000_000))
        result = self._check_with_change(duration)
        self.assertFalse(result["ready"])
        self.assertTrue(any("duration" in item for item in result["blockers"]))

    def test_power_speed_and_empty_resource_samples_fail_closed(self):
        def power(config, manifest, directory):
            self._change_evidence(manifest, directory, "resource_and_power_measurement",
                                  lambda value: value["data"]["samples"][0].update(power_w=26.0))
        result = self._check_with_change(power)
        self.assertFalse(result["ready"])
        self.assertTrue(any("power_w" in item for item in result["blockers"]))

        def speed(config, manifest, directory):
            manifest["speed_mps"] = 71.0
        result = self._check_with_change(speed)
        self.assertFalse(result["ready"])
        self.assertTrue(any("speed_mps" in item for item in result["blockers"]))

        def empty(config, manifest, directory):
            self._change_evidence(manifest, directory, "resource_and_power_measurement",
                                  lambda value: value["data"].update(samples=[]))
        result = self._check_with_change(empty)
        self.assertFalse(result["ready"])

    def test_malformed_identity_and_counts_fail_closed_without_exception(self):
        def identity(config, manifest, directory):
            self._change_evidence(manifest, directory, "sensor_sync_and_pose_age",
                                  lambda value: value["data"]["samples"][0].update(sample_id={"invalid": 1}))
        result = self._check_with_change(identity)
        self.assertFalse(result["ready"])
        self.assertTrue(any("sample_id" in item for item in result["blockers"]))

        def counts(config, manifest, directory):
            self._change_evidence(manifest, directory, "input_output_drop_duplicate_out_of_order_rates",
                                  lambda value: value["data"].update(output_count=True))
        result = self._check_with_change(counts)
        self.assertFalse(result["ready"])
        self.assertTrue(any("invalid counts" in item for item in result["blockers"]))

    def test_clock_and_run_samples_must_match(self):
        def clock(config, manifest, directory):
            self._change_evidence(manifest, directory, "monotonic_stage_timestamps",
                                  lambda value: value.update(clock_source="/clock"))
        result = self._check_with_change(clock)
        self.assertFalse(result["ready"])
        self.assertTrue(any("clock_source" in item for item in result["blockers"]))

        def coverage(config, manifest, directory):
            self._change_evidence(manifest, directory, "monotonic_stage_timestamps",
                                  lambda value: value["data"]["samples"][-1].update(
                                      start_monotonic_ns=1_500_000_000, end_monotonic_ns=1_510_000_000))
        result = self._check_with_change(coverage)
        self.assertFalse(result["ready"])
        self.assertTrue(any("cover continuous run" in item for item in result["blockers"]))

    def test_stage_samples_must_follow_frequency_and_order(self):
        def clustered(config, manifest, directory):
            def pack_rows(value):
                for index, row in enumerate(value["data"]["samples"][:-1]):
                    row["start_monotonic_ns"] = index * 1_000_000
                    row["end_monotonic_ns"] = index * 1_000_000 + 10_000_000
            self._change_evidence(manifest, directory, "monotonic_stage_timestamps", pack_rows)
        result = self._check_with_change(clustered)
        self.assertFalse(result["ready"])
        self.assertTrue(any("sample interval" in item for item in result["blockers"]))

        def out_of_order(config, manifest, directory):
            self._change_evidence(manifest, directory, "monotonic_stage_timestamps",
                                  lambda value: value["data"]["samples"].reverse())
        result = self._check_with_change(out_of_order)
        self.assertFalse(result["ready"])
        self.assertTrue(any("strictly increasing" in item for item in result["blockers"]))


if __name__ == "__main__":
    unittest.main()
