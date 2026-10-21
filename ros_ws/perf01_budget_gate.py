"""PERF-01预算配置的只读预检；不执行ROS、不修改配置或运行产物。"""

import argparse
import json
from pathlib import Path

import yaml


REQUIRED_SPEEDS = (35.0, 50.0, 70.0)
REQUIRED_PERCENTILES = ('p50', 'p95', 'p99')


def evaluate_budget(config):
    """区分工程参考预算与可执行正式验收配置，缺项时保持fail-closed。"""
    blockers = []
    errors = []
    if tuple(config.get('acceptance_speed_mps', ())) != REQUIRED_SPEEDS:
        errors.append('acceptance_speed_mps must be [35.0, 50.0, 70.0]')

    platform = config.get('target_airborne_platform', {})
    if platform.get('status') != 'confirmed_selected_platform':
        blockers.append('target airborne platform is not confirmed')
    for field in ('model', 'power_mode', 'measurement_method'):
        if not platform.get(field):
            errors.append('target_airborne_platform.%s is required' % field)

    contract = config.get('timing_contract', {})
    if tuple(contract.get('percentiles', ())) != REQUIRED_PERCENTILES:
        errors.append('timing_contract.percentiles must be [p50, p95, p99]')
    for field in ('max_radar_ir_delta_ms', 'max_pose_age_ms', 'max_p99_latency_ms'):
        value = contract.get(field)
        if not isinstance(value, (int, float)) or value < 0:
            errors.append('timing_contract.%s must be nonnegative' % field)
    if contract.get('max_radar_ir_delta_ms') != 5.0:
        errors.append('max_radar_ir_delta_ms must remain 5.0')
    if contract.get('max_p99_latency_ms') != 20.0:
        errors.append('max_p99_latency_ms must remain 20.0')

    formal = config.get('formal_measurement', {})
    if formal.get('status') != 'confirmed':
        blockers.append('formal measurement status is not confirmed')
    for field in ('target_platform_id', 'start_endpoint', 'end_endpoint',
                  'sampling_clock_source', 'clock_domain_mapping', 'continuous_duration_s'):
        if formal.get(field) in (None, ''):
            blockers.append('formal_measurement.%s is missing' % field)
    if formal.get('continuous_duration_s') is not None and formal['continuous_duration_s'] <= 0:
        errors.append('formal_measurement.continuous_duration_s must be positive')

    radar = config.get('reference_sensors', {}).get('radar', {})
    infrared = config.get('reference_sensors', {}).get('infrared', {})
    if radar.get('frequency_hz') is None or radar.get('timestamp_error_ms') is None:
        blockers.append('Radar frequency and timestamp error are not bound to a selected configuration')
    if infrared.get('status') != 'confirmed_selected_sensor':
        blockers.append('infrared sensor and timing configuration are not confirmed')
    if infrared.get('timestamp_error_ms') is None:
        blockers.append('infrared timestamp error is missing')

    ready = not blockers and not errors
    return dict(mode='formal_ready' if ready else 'reference_only', ready=ready,
                blockers=blockers, errors=errors,
                semantics='reference_only is not a performance pass and cannot authorize a formal 20 ms claim')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', nargs='?', default='configs/perf01_budget.yaml', type=Path)
    parser.add_argument('--require-formal', action='store_true',
                        help='return nonzero unless the formal measurement inputs are confirmed')
    args = parser.parse_args()
    result = evaluate_budget(yaml.safe_load(args.config.read_text()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ready'] or not args.require_formal else 1


if __name__ == '__main__':
    raise SystemExit(main())
