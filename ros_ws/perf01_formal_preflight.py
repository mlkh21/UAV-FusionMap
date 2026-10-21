"""Read-only PERF-01 formal measurement evidence preflight.

This module validates the evidence contract for one completed formal run.  It
does not start ROS, inspect ROS state, or infer physical timing from fixture or
simulation-time fields.
"""

import argparse
import json
import math
from pathlib import Path

import yaml

from perf01_budget_gate import evaluate_budget
from perf01a_metrics import percentile_set


SCHEMA_VERSION = "perf01.formal_measurement.v0.1"
PHYSICAL_FREQUENCY_SOURCES = {
    "device_measurement",
    "hardware_capture",
    "vendor_datasheet_confirmed",
}
FORBIDDEN_CLOCK_SOURCES = {
    "fixture",
    "fixture_frequency",
    "simulation",
    "simulation_time",
    "sim_time",
    "ros_sim_time",
    "/clock",
}


def _missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite(value):
    return _number(value) and math.isfinite(value)


def _count(value):
    return type(value) is int and value >= 0


def _time(value):
    return type(value) is int and value >= 0


def _add_missing(errors, label, value):
    if _missing(value):
        errors.append(label + " is required")
        return True
    return False


def _resolve_evidence_path(run_directory, value):
    if isinstance(value, dict):
        value = value.get("path")
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = run_directory / path
    return path


def _within_directory(path, directory):
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _validate_platform(config, manifest, blockers, errors):
    expected = _mapping(config.get("target_airborne_platform"))
    formal = _mapping(config.get("formal_measurement"))
    actual = manifest.get("target_platform")
    if not isinstance(actual, dict):
        errors.append("manifest.target_platform must be a mapping")
        return

    if actual.get("status") != "confirmed_selected_platform":
        blockers.append("manifest target platform is not confirmed_selected_platform")
    if actual.get("id") != formal.get("target_platform_id"):
        blockers.append("manifest target platform id does not match formal_measurement.target_platform_id")
    for field in ("model", "power_mode", "measurement_method"):
        if _missing(actual.get(field)):
            errors.append("manifest.target_platform.%s is required" % field)
        elif actual.get(field) != expected.get(field):
            blockers.append("manifest.target_platform.%s does not match budget" % field)


def _validate_sensor(name, config_sensor, actual, measurement, blockers, errors):
    config_sensor = _mapping(config_sensor)
    label = "manifest.sensors.%s" % name
    if not isinstance(actual, dict):
        errors.append(label + " must be a mapping")
        return

    if actual.get("status") != "confirmed_selected_sensor":
        blockers.append(label + ".status is not confirmed_selected_sensor")
    if _missing(actual.get("model")):
        errors.append(label + ".model is required")
    elif actual.get("model") != config_sensor.get("model"):
        blockers.append(label + ".model does not match budget")

    if "variant" in config_sensor and not _missing(config_sensor.get("variant")):
        if actual.get("variant") != config_sensor.get("variant"):
            blockers.append(label + ".variant does not match budget")

    frequency = actual.get("physical_sampling_frequency_hz")
    if not _number(frequency) or frequency <= 0:
        blockers.append(label + ".physical_sampling_frequency_hz is required and must be positive")
    source = actual.get("sampling_frequency_source")
    if source in FORBIDDEN_CLOCK_SOURCES:
        blockers.append(label + ".sampling_frequency_source cannot be fixture or simulation time")
    elif source not in PHYSICAL_FREQUENCY_SOURCES:
        blockers.append(label + ".sampling_frequency_source must identify a physical source")

    expected_frequency = config_sensor.get("frequency_hz")
    if expected_frequency is None:
        expected_frequency = config_sensor.get("frame_rate_hz")
    if not _number(expected_frequency) or expected_frequency <= 0:
        blockers.append("budget reference_sensors.%s physical frequency is not confirmed" % name)
    elif _number(frequency) and frequency != expected_frequency:
        blockers.append(label + ".physical_sampling_frequency_hz does not match budget")

    timestamp_error = actual.get("timestamp_error_ms")
    if not _finite(timestamp_error) or timestamp_error < 0:
        blockers.append(label + ".timestamp_error_ms is required, finite and nonnegative")
    expected_error = config_sensor.get("timestamp_error_ms")
    if not _finite(expected_error) or expected_error < 0:
        blockers.append("budget reference_sensors.%s timestamp_error_ms is not confirmed" % name)
    elif _finite(timestamp_error) and timestamp_error > expected_error:
        blockers.append(label + ".timestamp_error_ms exceeds budget")

    declared_clock = actual.get("sampling_clock_source")
    if _missing(declared_clock) or declared_clock != measurement.get("sampling_clock_source"):
        blockers.append(label + ".sampling_clock_source does not match measurement clock")


def _validate_measurement(config, manifest, blockers, errors):
    formal = _mapping(config.get("formal_measurement"))
    actual = manifest.get("measurement")
    if not isinstance(actual, dict):
        errors.append("manifest.measurement must be a mapping")
        return

    for field in (
        "start_endpoint",
        "end_endpoint",
        "sampling_clock_source",
        "clock_domain_mapping",
        "continuous_duration_s",
        "duration_clock_source",
    ):
        _add_missing(errors, "manifest.measurement." + field, actual.get(field))

    for field in ("start_endpoint", "end_endpoint", "sampling_clock_source", "clock_domain_mapping"):
        expected = formal.get(field)
        value = actual.get(field)
        if _missing(expected):
            blockers.append("budget formal_measurement.%s is not confirmed" % field)
        elif value != expected:
            blockers.append("manifest.measurement.%s does not match budget" % field)

    clock_source = actual.get("sampling_clock_source")
    if clock_source in FORBIDDEN_CLOCK_SOURCES:
        blockers.append("manifest measurement cannot use simulation time as sampling clock")
    if actual.get("duration_clock_source") != clock_source:
        blockers.append("manifest.measurement.duration_clock_source must equal sampling_clock_source")
    if actual.get("duration_clock_source") in FORBIDDEN_CLOCK_SOURCES:
        blockers.append("manifest measurement duration cannot use simulation time")

    duration = actual.get("continuous_duration_s")
    expected_duration = formal.get("continuous_duration_s")
    if not _number(duration) or duration <= 0:
        blockers.append("manifest.measurement.continuous_duration_s must be positive")
    if not _number(expected_duration) or expected_duration <= 0:
        blockers.append("budget formal_measurement.continuous_duration_s is not confirmed")
    elif _number(duration) and duration < expected_duration:
        blockers.append("manifest continuous duration is shorter than budget")


def _validate_run_and_evidence(config, manifest, manifest_path, blockers, errors):
    run_value = manifest.get("run_directory")
    if _missing(run_value) or not isinstance(run_value, str):
        blockers.append("manifest.run_directory is required")
        return {}

    run_directory = Path(run_value).expanduser()
    if not run_directory.is_absolute():
        blockers.append("manifest.run_directory must be absolute")
        return {}
    if not run_directory.is_dir():
        blockers.append("manifest.run_directory does not exist as a directory")
        return {}

    if manifest_path is None:
        blockers.append("manifest path is required to bind the manifest to its run directory")
    elif run_directory.resolve() != manifest_path.resolve().parent:
        blockers.append("manifest.run_directory does not contain the manifest")

    validation = _mapping(config.get("validation"))
    required = validation.get("required_evidence", ())
    evidence = manifest.get("evidence")
    if not isinstance(required, (list, tuple)) or not required:
        errors.append("budget validation.required_evidence must be a non-empty list")
        return {}
    if not isinstance(evidence, dict):
        errors.append("manifest.evidence must be a mapping")
        return {}

    paths = {}
    for field in required:
        value = evidence.get(field)
        if _missing(value):
            blockers.append("required evidence field is missing: " + str(field))
            continue
        evidence_path = _resolve_evidence_path(run_directory, value)
        if evidence_path is None:
            blockers.append("required evidence field has no path: " + str(field))
            continue
        if not _within_directory(evidence_path, run_directory):
            blockers.append("required evidence is outside run directory: " + str(field))
            continue
        if not evidence_path.is_file():
            blockers.append("required evidence file is missing: " + str(field))
            continue
        paths[field] = evidence_path
        if isinstance(value, dict) and "passed" in value and value.get("passed") is not True:
            blockers.append("required evidence is not passed: " + str(field))
    return paths


def _load_evidence(manifest, paths, blockers):
    result = {}
    for name, path in paths.items():
        try:
            value = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            blockers.append("evidence.%s is not readable JSON: %s" % (name, exc))
            continue
        if not isinstance(value, dict) or not isinstance(value.get("data"), dict):
            blockers.append("evidence.%s needs structured data; passed=true alone is insufficient" % name)
            continue
        for field, expected in (("run_id", manifest.get("run_id")),
                                ("speed_mps", manifest.get("speed_mps")),
                                ("clock_source", _mapping(manifest.get("measurement")).get(
                                    "sampling_clock_source")), ("source_type", "measured")):
            if value.get(field) != expected or _missing(expected):
                blockers.append("evidence.%s.%s does not match this measured run" % (name, field))
        result[name] = value["data"]
    return result


def _validate_sample_values(config, manifest, data, blockers):
    stages = data["monotonic_stage_timestamps"]
    formal = _mapping(config.get("formal_measurement"))
    for field in ("start_endpoint", "end_endpoint"):
        if stages.get(field) != formal.get(field) or _missing(formal.get(field)):
            blockers.append("evidence.monotonic_stage_timestamps.%s differs from budget" % field)
    rows = stages.get("samples")
    if not isinstance(rows, list) or not rows:
        blockers.append("evidence.monotonic_stage_timestamps.samples must be nonempty")
        return

    sample_ids = set()
    durations_ms = []
    start_times, end_times = [], []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("sample_id"), str) or not row["sample_id"].strip():
            blockers.append("evidence.monotonic_stage_timestamps has invalid sample_id")
            return
        sample_id = row["sample_id"]
        start, end = row.get("start_monotonic_ns"), row.get("end_monotonic_ns")
        if sample_id in sample_ids or not _time(start) or not _time(end) or end < start:
            blockers.append("evidence.monotonic_stage_timestamps has duplicate or invalid stage time")
            return
        sample_ids.add(sample_id)
        durations_ms.append((end - start) / 1e6)
        start_times.append(start)
        end_times.append(end)

    if any(current <= previous for previous, current in zip(start_times, start_times[1:])):
        blockers.append("evidence.monotonic_stage_timestamps.samples must be strictly increasing")
    frequency = _mapping(_mapping(config.get("reference_sensors")).get("radar")).get("frequency_hz")
    period_ns = None
    if not _finite(frequency) or frequency <= 0:
        blockers.append("budget reference_sensors.radar.frequency_hz is invalid")
    else:
        period_ns = math.ceil(1e9 / frequency)
        dropped = data["input_output_drop_duplicate_out_of_order_rates"].get("drop_count")
        if _count(dropped) and any(current - previous > period_ns * (dropped + 1)
                                   for previous, current in zip(start_times, start_times[1:])):
            blockers.append("evidence.monotonic_stage_timestamps.sample interval exceeds "
                            "radar frequency and declared drops")

    age_limit = _mapping(config.get("timing_contract")).get("max_end_to_end_age_ms")
    if not _finite(age_limit) or age_limit < 0:
        blockers.append("budget timing_contract.max_end_to_end_age_ms is invalid")
    elif any(duration > age_limit for duration in durations_ms):
        blockers.append("evidence.monotonic_stage_timestamps.end_to_end_age exceeds budget")

    timing = data["p50_p95_p99_latency"]
    if timing.get("sample_count") != len(rows) or not _count(timing.get("sample_count")):
        blockers.append("evidence.p50_p95_p99_latency.sample_count differs from stage samples")
    reported = _mapping(timing.get("percentiles_ms"))
    computed = percentile_set(durations_ms)
    for name in ("p50", "p95", "p99"):
        value = reported.get(name)
        if not _finite(value) or value < 0 or not math.isclose(value, computed[name], abs_tol=1e-6):
            blockers.append("evidence.p50_p95_p99_latency.%s does not match stage samples" % name)
    p99_limit = _mapping(config.get("timing_contract")).get("max_p99_latency_ms")
    if _finite(p99_limit) and computed["p99"] > p99_limit:
        blockers.append("evidence.p50_p95_p99_latency.p99 exceeds budget")

    sync_rows = data["sensor_sync_and_pose_age"].get("samples")
    if not isinstance(sync_rows, list) or len(sync_rows) != len(rows):
        blockers.append("evidence.sensor_sync_and_pose_age.samples differs from stage samples")
    else:
        sync_ids = []
        contract = _mapping(config.get("timing_contract"))
        for row in sync_rows:
            if not isinstance(row, dict):
                blockers.append("evidence.sensor_sync_and_pose_age has invalid sample")
                return
            sample_id = row.get("sample_id")
            if not isinstance(sample_id, str) or not sample_id.strip():
                blockers.append("evidence.sensor_sync_and_pose_age.sample_id is invalid")
                return
            sync_ids.append(sample_id)
            for field, limit in (("radar_ir_delta_ms", contract.get("max_radar_ir_delta_ms")),
                                 ("pose_age_ms", contract.get("max_pose_age_ms"))):
                value = row.get(field)
                if not _finite(value) or value < 0 or (_finite(limit) and value > limit):
                    blockers.append("evidence.sensor_sync_and_pose_age.%s exceeds budget or is invalid" % field)
        if len(set(sync_ids)) != len(rows) or set(sync_ids) != sample_ids:
            blockers.append("evidence.sensor_sync_and_pose_age.sample_id differs from stage samples")

    stability = data["continuous_run_stability"]
    start, end = stability.get("start_monotonic_ns"), stability.get("end_monotonic_ns")
    expected_duration = formal.get("continuous_duration_s")
    declared_duration = _mapping(manifest.get("measurement")).get("continuous_duration_s")
    if not _time(start) or not _time(end) or end < start or not _finite(expected_duration) or (
            (end - start) / 1e9 < max(expected_duration, declared_duration)
            if _finite(declared_duration) else True):
        blockers.append("evidence.continuous_run_stability.duration is insufficient or invalid")
    else:
        if min(start_times) < start or max(end_times) > end:
            blockers.append("evidence.monotonic_stage_timestamps falls outside continuous run")
        if period_ns is not None:
            if min(start_times) > start + period_ns or max(end_times) < end - period_ns:
                blockers.append("evidence.monotonic_stage_timestamps does not cover continuous run")
    for field in ("restart_count", "unexpected_terminal_count"):
        if stability.get(field) != 0 or not _count(stability.get(field)):
            blockers.append("evidence.continuous_run_stability.%s must be zero" % field)
    return len(rows)


def _validate_counts_and_resources(config, data, sample_count, blockers):
    counts = data["input_output_drop_duplicate_out_of_order_rates"]
    fields = ("input_count", "output_count", "drop_count", "timeout_count",
              "duplicate_count", "out_of_order_count")
    if not all(_count(counts.get(field)) for field in fields) or counts["input_count"] == 0:
        blockers.append("evidence.input_output_drop_duplicate_out_of_order_rates has invalid counts")
    else:
        incoming, outgoing = counts["input_count"], counts["output_count"]
        if outgoing != sample_count or outgoing + counts["drop_count"] != incoming or (
                counts["timeout_count"] > counts["drop_count"]):
            blockers.append("evidence.input_output_drop_duplicate_out_of_order_rates counts do not close")
        contract = _mapping(config.get("timing_contract"))
        for field, count, limit in (("drop_rate", counts["drop_count"], contract.get("max_drop_rate")),
                                     ("timeout_rate", counts["timeout_count"], contract.get("max_timeout_rate"))):
            if not _finite(limit) or not 0 <= limit <= 1 or count / incoming > limit:
                blockers.append("evidence.%s exceeds budget or is invalid" % field)
        formal = _mapping(config.get("formal_measurement"))
        radar = _mapping(_mapping(config.get("reference_sensors")).get("radar"))
        frequency = radar.get("frequency_hz")
        duration = formal.get("continuous_duration_s")
        allowed_drop = contract.get("max_drop_rate")
        if all(_finite(value) for value in (frequency, duration, allowed_drop)) and (
                incoming < math.ceil(frequency * duration * (1 - allowed_drop))):
            blockers.append("evidence.input_count is insufficient for duration and radar frequency")

    resources = data["resource_and_power_measurement"].get("samples")
    if not isinstance(resources, list) or len(resources) < 2:
        blockers.append("evidence.resource_and_power_measurement.samples must have coverage")
        return
    platform = _mapping(config.get("target_airborne_platform"))
    power_limit, memory_limit = platform.get("power_w"), platform.get("memory_gb")
    if not _finite(power_limit) or power_limit <= 0 or not _finite(memory_limit) or memory_limit <= 0:
        blockers.append("budget target platform power/memory limits are not confirmed")
        return
    timestamps = []
    for row in resources:
        if not isinstance(row, dict) or not _time(row.get("monotonic_ns")):
            blockers.append("evidence.resource_and_power_measurement has invalid monotonic time")
            return
        timestamps.append(row["monotonic_ns"])
        for field in ("power_w", "rss_mb", "cpu_percent", "gpu_percent", "npu_percent", "temperature_c"):
            value = row.get(field)
            if not _finite(value) or (field != "temperature_c" and value < 0):
                blockers.append("evidence.resource_and_power_measurement.%s is invalid" % field)
            elif field == "power_w" and (value == 0 or value > power_limit):
                blockers.append("evidence.resource_and_power_measurement.power_w exceeds budget or is zero")
            elif field == "rss_mb" and value > memory_limit * 1024:
                blockers.append("evidence.resource_and_power_measurement.rss_mb exceeds platform memory")
            elif field.endswith("_percent") and value > 100:
                blockers.append("evidence.resource_and_power_measurement.%s exceeds 100" % field)
    stability = data["continuous_run_stability"]
    start, end = stability.get("start_monotonic_ns"), stability.get("end_monotonic_ns")
    if _time(start) and _time(end) and (min(timestamps) > start or max(timestamps) < end):
        blockers.append("evidence.resource_and_power_measurement does not cover continuous run")


def _validate_evidence_values(config, manifest, paths, blockers):
    speed = manifest.get("speed_mps")
    speeds = config.get("acceptance_speed_mps")
    if not isinstance(speeds, (list, tuple)):
        speeds = ()
    if not _finite(speed) or speed not in speeds:
        blockers.append("manifest.speed_mps must be one of the registered speeds")
    values = _load_evidence(manifest, paths, blockers)
    required = _mapping(config.get("validation")).get("required_evidence", ())
    if not isinstance(required, (list, tuple)) or not required:
        return
    if any(name not in values for name in required):
        return
    names = ("monotonic_stage_timestamps", "p50_p95_p99_latency", "sensor_sync_and_pose_age",
             "input_output_drop_duplicate_out_of_order_rates", "resource_and_power_measurement",
             "continuous_run_stability")
    if any(name not in values for name in names):
        blockers.append("budget validation.required_evidence lacks formal metric categories")
        return
    sample_count = _validate_sample_values(config, manifest, values, blockers)
    if sample_count is not None:
        _validate_counts_and_resources(config, values, sample_count, blockers)


def evaluate_formal_preflight(config, manifest, manifest_path=None):
    """Return a fail-closed formal evidence preflight result."""
    blockers = []
    errors = []
    if isinstance(config, dict):
        try:
            budget_result = evaluate_budget(config)
        except (AttributeError, TypeError, ValueError) as exc:
            budget_result = {
                "ready": False,
                "mode": "reference_only",
                "blockers": [],
                "errors": ["budget config is malformed: " + str(exc)],
            }
    else:
        config = {}
        budget_result = {
            "ready": False,
            "mode": "reference_only",
            "blockers": [],
            "errors": ["budget config must be a mapping"],
        }
    blockers.extend("budget: " + item for item in budget_result.get("blockers", ()))
    errors.extend("budget: " + item for item in budget_result.get("errors", ()))

    if not isinstance(manifest, dict):
        errors.append("formal manifest must be a mapping")
        return {
            "ready": False,
            "mode": "reference_only",
            "blockers": blockers,
            "errors": errors,
            "budget_gate": budget_result,
        }

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("manifest.schema_version must be " + SCHEMA_VERSION)
    if manifest.get("status") != "COMPLETE":
        blockers.append("formal manifest status is not COMPLETE")
    if type(manifest.get("exit")) is not int or manifest["exit"] != 0:
        blockers.append("formal manifest exit is not zero")
    if manifest.get("measurement_complete") is not True:
        blockers.append("formal manifest does not mark measurement_complete=true")
    _add_missing(errors, "manifest.run_id", manifest.get("run_id"))

    _validate_platform(config, manifest, blockers, errors)
    sensors = manifest.get("sensors")
    if not isinstance(sensors, dict):
        errors.append("manifest.sensors must be a mapping")
    else:
        measurement = manifest.get("measurement")
        measurement = measurement if isinstance(measurement, dict) else {}
        reference = _mapping(config.get("reference_sensors"))
        for name in ("radar", "infrared"):
            _validate_sensor(name, reference.get(name, {}), sensors.get(name), measurement,
                             blockers, errors)
    _validate_measurement(config, manifest, blockers, errors)
    paths = _validate_run_and_evidence(config, manifest, manifest_path, blockers, errors)
    _validate_evidence_values(config, manifest, paths, blockers)

    ready = not blockers and not errors
    return {
        "ready": ready,
        "mode": "formal_ready" if ready else "reference_only",
        "blockers": blockers,
        "errors": errors,
        "budget_gate": budget_result,
        "semantics": "formal_ready authorizes evidence preflight only; it is not a performance pass",
    }


def _read_yaml(path):
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("budget config must be a mapping")
    return value


def _read_manifest(path):
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("formal manifest must be a mapping")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/perf01_budget.yaml"))
    args = parser.parse_args(argv)

    try:
        config = _read_yaml(args.config)
        manifest = _read_manifest(args.manifest)
        result = evaluate_formal_preflight(config, manifest, args.manifest)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        result = {
            "ready": False,
            "mode": "reference_only",
            "blockers": [],
            "errors": [type(exc).__name__ + ": " + str(exc)],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
