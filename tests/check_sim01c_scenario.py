#!/usr/bin/env python
"""SIM-01C 在线观察器与离线产物审计。

在线：``check_sim01c_scenario.py RUN RUN_ID C-F0``
离线：在监督器清理完成后以相同参数加 ``--offline``。
倍速单run：``... RUN RUN_ID SPEED-half|nominal|double --offline``。
倍速矩阵：``... SUITE MATRIX_ID SPEED-MATRIX --offline``。

检查器不修改业务状态机。F6 是方案明确的 sensors-only fixture，因此在线
检查器在该场景兼作最小 ``AircraftState + /clock`` 故障注入器。
"""
from collections import Counter
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import threading
import time


PYTHON = '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python'
SOURCE = '/uav/sim/state'
SENSOR = '/uav/sensors/state'
CLOCK = '/clock'
DIAGNOSTIC = '/uav/diagnostics'
LEVELS = {0: 'OK', 1: 'WARN', 2: 'ERROR', 3: 'STALE'}
SPEED_CASES = {
    'half': ('SPEED_05', .5),
    'nominal': ('SPEED_1', 1.),
    'double': ('SPEED_2', 2.),
}
SPEED_MATRIX_PLAN = (
    ('A', 1, 'SPEED_05', .5), ('A', 2, 'SPEED_1', 1.),
    ('A', 3, 'SPEED_2', 2.), ('B', 1, 'SPEED_2', 2.),
    ('B', 2, 'SPEED_1', 1.), ('B', 3, 'SPEED_05', .5),
    ('C', 1, 'SPEED_1', 1.), ('C', 2, 'SPEED_05', .5),
    ('C', 3, 'SPEED_2', 2.))


def fail(errors, message):
    if message not in errors:
        errors.append(message)


def read_json(path, errors, required=True):
    path = Path(path)
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError('top level must be an object')
        return value
    except (OSError, ValueError) as exc:
        if required:
            fail(errors, path.name + ': ' + str(exc))
        return {}


def read_lines(path, errors, required=True):
    path = Path(path)
    try:
        with path.open() as stream:
            result = [json.loads(line) for line in stream if line.strip()]
        if any(not isinstance(row, dict) for row in result):
            raise ValueError('every line must be an object')
        return result
    except (OSError, ValueError) as exc:
        if required:
            fail(errors, path.name + ': ' + str(exc))
        return []


def file_identity(path, errors=None, label='file'):
    """返回冻结文件身份；哈希只用于证明同一候选，不替代行为测试。"""
    errors = [] if errors is None else errors
    try:
        resolved = Path(path).resolve(strict=True)
        stat = resolved.stat()
        digest = hashlib.sha256()
        with resolved.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return dict(path=str(resolved), size=stat.st_size, mtime_ns=stat.st_mtime_ns,
                    sha256=digest.hexdigest())
    except OSError as exc:
        fail(errors, 'speed matrix: %s identity unavailable: %s' % (label, exc))
        return {}


def write_json_exclusive(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def load_config(root, config=None):
    import yaml
    path = Path(config or root / 'configs/sim01c_scenarios.yaml').resolve()
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict) or value.get('schema_version') != '0.1':
        raise ValueError('SIM-01C配置缺失或版本不支持')
    return path, value


def scenario_key(value):
    value = value.upper()
    if value.startswith('C-'):
        value = value[2:]
    if value not in {'F%d' % i for i in range(8)}:
        raise ValueError('scenario must be C-F0..C-F7')
    return value


def _header(row):
    state = row.get('state')
    return state.get('header', {}) if isinstance(state, dict) else {}


def _state_rows(rows, topic, status=None):
    result = [row for row in rows if row.get('topic') == topic and isinstance(row.get('state'), dict)]
    if status is not None:
        result = [row for row in result if _header(row).get('status') == status]
    return result


def _terminal_rows(rows, topic):
    return [row for row in _state_rows(rows, topic)
            if _header(row).get('status') == 'unavailable' and
            str(_header(row).get('reason', '')).startswith('terminal:')]


def _diagnostic_rows(rows, name=None, message=None, level=None):
    result = [row for row in rows if row.get('topic') == DIAGNOSTIC]
    if name is not None:
        result = [row for row in result if row.get('name') == name]
    if message is not None:
        result = [row for row in result if row.get('message') == message]
    if level is not None:
        result = [row for row in result if row.get('level') == level]
    return result


def _int(value):
    if isinstance(value, bool):
        raise ValueError('boolean is not an integer counter')
    return int(value)


def _validate_sequences(rows, errors):
    if any(row.get('event_seq') != index for index, row in enumerate(rows, 1)):
        fail(errors, 'observations: event_seq is not consecutive')
    receipts = [row.get('receipt_monotonic_ns') for row in rows]
    if any(type(value) is not int or value < 0 for value in receipts):
        fail(errors, 'observations: invalid monotonic receipt')
    elif any(b < a for a, b in zip(receipts, receipts[1:])):
        fail(errors, 'observations: receipt order regressed')


def _validate_diagnostics(rows, spec, scenario, run_id, errors):
    allowed = spec.get('allowed_diagnostics', {})
    for row in _diagnostic_rows(rows):
        name, message = row.get('name'), row.get('message')
        level_name = LEVELS.get(row.get('level'))
        levels = allowed.get(name, {}).get(message)
        if not isinstance(levels, list) or level_name not in levels:
            fail(errors, '%s: unexpected diagnostic %r/%r/%r' %
                 (scenario, name, message, level_name))
        values = row.get('values')
        if not isinstance(values, dict):
            fail(errors, scenario + ': diagnostic values missing')
        elif values.get('python') != PYTHON:
            fail(errors, scenario + ': diagnostic interpreter mismatch')
        if row.get('hardware_id') != run_id:
            fail(errors, scenario + ': diagnostic run identity mismatch')
    # pending_timeout 只是 F1 的已知因果事件；其他场景即使配置被误改也不宽放。
    pending = _diagnostic_rows(rows, message='pending_timeout')
    if pending and scenario != 'F1':
        fail(errors, scenario + ': pending_timeout is only allowed in F1')


def _validate_header(header, run_id, source, errors):
    prefix = 'source' if source else 'sensors'
    expected_type = 'simulation' if source else 'derived'
    expected_frame = 'world_ned' if source else 'odom'
    if (header.get('schema_version') != '0.1' or header.get('run_id') != run_id or
            header.get('clock_id') != 'sim:' + run_id or header.get('source_type') != expected_type or
            header.get('frame_id') != expected_frame):
        fail(errors, prefix + ': terminal schema/run/clock/frame identity mismatch')
    if type(header.get('timestamp')) is not int or header.get('timestamp', -1) < 0:
        fail(errors, prefix + ': terminal timestamp is not a nonnegative integer')


def _driver_time(driver_rows, terminal_receipt, kind):
    candidates = []
    for row in driver_rows:
        receipt = row.get('publish_end_monotonic_ns', row.get('receipt_monotonic_ns'))
        if type(receipt) is not int or receipt > terminal_receipt:
            continue
        message = str(row.get('msg_type', '')).upper()
        action = str(row.get('action', '')).lower()
        if kind == 'imu' and ('HIGHRES_IMU' in message or message == 'IMU') and 'regress' not in action:
            candidates.append(receipt)
        elif kind == 'odometry' and 'ODOMETRY' in message and 'reset' not in action:
            candidates.append(receipt)
        elif kind == 'regression' and 'regress' in action:
            candidates.append(receipt)
        elif kind == 'reset' and ('inject_estimator_reset' in action or
                                  ('reset' in action and 'change' in action)):
            candidates.append(receipt)
    return max(candidates) if candidates else None


def _validate_window(delta_ns, window, name, errors):
    if type(delta_ns) is not int:
        fail(errors, name + ': timing evidence missing')
        return
    try:
        low, high = [float(value) for value in window]
    except (TypeError, ValueError):
        fail(errors, name + ': invalid configured window')
        return
    seconds = delta_ns / 1e9
    if not low <= seconds <= high:
        fail(errors, '%s: %.6fs outside [%.6f, %.6f]' % (name, seconds, low, high))


def validate_observations(rows, run_id, scenario, spec, driver_rows=None,
                          previous_rows=None, source_start_ns=None):
    """Validate normalized observed events without trusting process exit status."""
    errors = []
    driver_rows = driver_rows or []
    previous_rows = previous_rows or []
    expected = spec.get('expected', {})
    _validate_sequences(rows, errors)
    _validate_diagnostics(rows, spec, scenario, run_id, errors)

    source_terms = _terminal_rows(rows, SOURCE)
    sensor_terms = _terminal_rows(rows, SENSOR)
    if len(source_terms) != expected.get('source_terminal_count'):
        fail(errors, scenario + ': source terminal count mismatch')
    if len(sensor_terms) != expected.get('sensors_terminal_count'):
        fail(errors, scenario + ': sensors terminal count mismatch')

    if expected.get('terminal_code') and source_terms and sensor_terms:
        code = expected['terminal_code']
        reason = 'terminal:' + code
        source_h, sensor_h = _header(source_terms[0]), _header(sensor_terms[0])
        _validate_header(source_h, run_id, True, errors)
        _validate_header(sensor_h, run_id, False, errors)
        expected_source_id = 'sim.terminal:%s:%d' % (code, source_h.get('timestamp', 0)//1000)
        if (source_h.get('reason') != reason or sensor_h.get('reason') != reason or
                source_h.get('sample_id') != expected_source_id or
                sensor_h.get('sample_id') != 'sensors.state:' + expected_source_id or
                sensor_h.get('timestamp') != source_h.get('timestamp')):
            fail(errors, scenario + ': terminal reason/identity/timestamp propagation mismatch')
        # 不用不同话题callback的receipt顺序推断发布因果；只核对业务clock内容。
        clocks = [row.get('timestamp') for row in rows if row.get('topic') == CLOCK and
                  type(row.get('timestamp')) is int]
        if expected.get('terminal_timestamp_equals_last_clock'):
            if not clocks or source_h.get('timestamp') != max(clocks):
                fail(errors, scenario + ': terminal timestamp differs from final observed clock')
        if 'terminal_timestamp_ns' in expected and source_h.get('timestamp') != int(expected['terminal_timestamp_ns']):
            fail(errors, scenario + ': terminal timestamp differs from configured value')
        for topic, terminal in ((SOURCE, source_terms[0]), (SENSOR, sensor_terms[0])):
            later_valid = [row for row in _state_rows(rows, topic, 'valid')
                           if row.get('event_seq', 0) > terminal.get('event_seq', -1)]
            if len(later_valid) > expected.get('max_post_terminal_valid', 0):
                fail(errors, scenario + ': valid output observed after ' + topic + ' terminal')
        terminal_receipt = source_terms[0].get('receipt_monotonic_ns')
        if not _diagnostic_rows(rows, 'simulation/state_clock', code, 2):
            fail(errors, scenario + ': first exact source fault ERROR was not observed')
        if scenario == 'F0':
            # 内部_start不外显，首个PREPARING callback receipt仅为冻结方案中的代理。
            preparing = _diagnostic_rows(rows, 'simulation/state_clock', 'timeline:PREPARING')
            start = preparing[0].get('receipt_monotonic_ns') if preparing else None
            _validate_window(terminal_receipt-start if type(start) is int else None,
                             expected.get(
                                 'terminal_window_from_first_preparing_diagnostic_receipt_proxy_wall_s'),
                             'F0 PREPARING receipt proxy', errors)
            # 节点发现receipt不是SourceTimeline内部_start，但比周期诊断更接近节点启动，
            # 用第二个独立代理守住生产配置60秒；缺失该证据不能把F0判为通过。
            _validate_window(terminal_receipt-source_start_ns
                             if type(source_start_ns) is int else None,
                             expected.get(
                                 'terminal_window_from_source_node_lookup_receipt_proxy_wall_s'),
                             'F0 source node lookup receipt proxy', errors)
        elif scenario in ('F1', 'F3'):
            start = _driver_time(driver_rows, terminal_receipt, 'imu')
            _validate_window(terminal_receipt-start if type(start) is int else None,
                             expected.get(
                                 'terminal_window_from_last_valid_imu_driver_publish_receipt_proxy_wall_s'),
                             scenario + ' IMU driver receipt proxy', errors)
        elif scenario == 'F2':
            start = _driver_time(driver_rows, terminal_receipt, 'odometry')
            _validate_window(terminal_receipt-start if type(start) is int else None,
                             expected.get(
                                 'terminal_window_from_last_valid_odometry_driver_publish_receipt_proxy_wall_s'),
                             'F2 ODOMETRY driver receipt proxy', errors)
        elif scenario in ('F4', 'F5'):
            start = _driver_time(driver_rows, terminal_receipt,
                                 'regression' if scenario == 'F4' else 'reset')
            limit = expected.get('terminal_max_from_injection_wall_s')
            if type(start) is not int or terminal_receipt < start or terminal_receipt-start > float(limit)*1e9:
                fail(errors, scenario + ': immediate fault exceeded injection deadline or lacks evidence')

    if scenario == 'F1':
        # 诊断行可重复并携带累计counter，只要求真实观察到，精确数量由封存audit核对。
        if not _diagnostic_rows(rows, 'simulation/state_clock', 'pending_timeout'):
            fail(errors, 'F1: expected causal pending_timeout was not observed')
        stalls = [row for row in driver_rows if row.get('action') == 'stall_imu']
        last_imu = max((row.get('time_usec', -1) for row in driver_rows
                        if row.get('msg_type') == 'HIGHRES_IMU' and
                        'regress' not in str(row.get('action', '')).lower()), default=-1)
        if expected.get('clock_advances_while_imu_stopped') is False and stalls and any(
                row.get('timestamp', -1) > last_imu * 1000 for row in rows
                if row.get('topic') == CLOCK):
            fail(errors, 'F1: clock advanced beyond last valid IMU timestamp')
    if scenario == 'F2' and expected.get('clock_advances_until_terminal'):
        last_odometry = max((row.get('time_usec', -1) for row in driver_rows
                             if row.get('msg_type') == 'ODOMETRY' and
                             'reset' not in str(row.get('action', '')).lower()), default=-1)
        if not any(row.get('topic') == CLOCK and
                   row.get('timestamp', -1) > last_odometry * 1000 for row in rows):
            fail(errors, 'F2: clock did not advance after last valid ODOMETRY')
    if scenario == 'F3' and source_terms:
        terminal_receipt = source_terms[0]['receipt_monotonic_ns']
        recovery = [row for row in driver_rows
                    if type(row.get('publish_end_monotonic_ns', row.get('receipt_monotonic_ns'))) is int and
                    row.get('publish_end_monotonic_ns', row.get('receipt_monotonic_ns')) > terminal_receipt and
                    row.get('msg_type')]
        if not recovery:
            fail(errors, 'F3: no post-terminal recovery injection evidence')
    if scenario == 'F5':
        reset_rows = [row for row in driver_rows
                      if str(row.get('action', '')).lower() == 'inject_estimator_reset' or
                      ('reset' in str(row.get('action', '')).lower() and
                       'change' in str(row.get('action', '')).lower())]
        reset_ns = {row.get('time_usec')*1000 for row in reset_rows if type(row.get('time_usec')) is int}
        if any(_header(row).get('timestamp') in reset_ns for row in _state_rows(rows, SOURCE, 'valid')):
            fail(errors, 'F5: reset sample was published as valid')

    if scenario == 'F6':
        errors_rows = _diagnostic_rows(rows, 'sensors/state_adapter',
                                       expected.get('local_error_code'), 2)
        if not errors_rows:
            fail(errors, 'F6: clock_regression ERROR was not observed')
        elif any(_int(row.get('values', {}).get('clock_regression', 0)) < 1 for row in errors_rows):
            fail(errors, 'F6: ERROR lacks clock_regression counter evidence')
        first_error_seq = errors_rows[0].get('event_seq', -1) if errors_rows else -1
        if any(row.get('event_seq', 0) > first_error_seq for row in _state_rows(rows, SENSOR, 'valid')):
            fail(errors, 'F6: adapted valid output observed after clock regression')
        # 先形成未来pending再回退clock；locked/pending=0以进程关闭后的audit为准。
        clocks_before = [row.get('timestamp') for row in rows
                         if row.get('topic') == CLOCK and
                         row.get('event_seq', 0) < first_error_seq and
                         type(row.get('timestamp')) is int]
        future_source = [row for row in _state_rows(rows, SOURCE, 'valid')
                         if clocks_before and _header(row).get('timestamp', -1) > max(clocks_before) and
                         row.get('event_seq', 0) < first_error_seq]
        if not future_source:
            fail(errors, 'F6: future source state did not form pending before regression')

    if scenario == 'F7':
        source_valid = _state_rows(rows, SOURCE, 'valid')
        sensor_valid = _state_rows(rows, SENSOR, 'valid')
        if min(len(source_valid), len(sensor_valid)) < expected.get('min_new_run_valid_count', 1):
            fail(errors, 'F7: new run did not become valid')
        for row in source_valid + sensor_valid:
            h = _header(row)
            if h.get('run_id') != run_id or h.get('clock_id') != 'sim:' + run_id:
                fail(errors, 'F7: old run/clock identity reappeared')
        old_terminals = {(_header(row).get('run_id'), _header(row).get('sample_id')) for row in
                         _terminal_rows(previous_rows, SOURCE) + _terminal_rows(previous_rows, SENSOR)}
        if any((_header(row).get('run_id'), _header(row).get('sample_id')) in old_terminals for row in
               _terminal_rows(rows, SOURCE) + _terminal_rows(rows, SENSOR)):
            fail(errors, 'F7: predecessor terminal identity reappeared')
        previous_valid = {(_header(row).get('run_id'), _header(row).get('sample_id'))
                          for row in _state_rows(previous_rows, SOURCE, 'valid') +
                          _state_rows(previous_rows, SENSOR, 'valid')}
        current_valid = {(_header(row).get('run_id'), _header(row).get('sample_id'))
                         for row in source_valid + sensor_valid}
        if previous_valid & current_valid:
            fail(errors, 'F7: predecessor composite valid identity reappeared')
        previous_runs = {_header(row).get('run_id') for row in previous_rows if _header(row)}
        previous_clocks = {_header(row).get('clock_id') for row in previous_rows if _header(row)}
        if run_id in previous_runs or 'sim:' + run_id in previous_clocks:
            fail(errors, 'F7: run_id/clock_id is not distinct from predecessor')
    return errors


def evaluate_speed_measurement(measurement, case, speed_spec, expected_run_id=None):
    """复算runner共同窗口，并分开报告测量完整性与倍率门槛。"""
    errors = []
    complete = measurement.get('measurement_complete') is True
    actual = None
    factor_passed = False
    try:
        if not complete:
            raise ValueError('measurement_complete is not true')
        if measurement.get('schema_version') != '0.1':
            fail(errors, 'speed: result schema_version mismatch')
        if expected_run_id is not None and measurement.get('run_id') != expected_run_id:
            fail(errors, 'speed: result run_id mismatch')
        endpoints = measurement['endpoints']
        first_clock, last_clock = endpoints['c0_ns'], endpoints['c1_ns']
        first_wall = endpoints['c0_receipt_monotonic_ns']
        last_wall = endpoints['c1_receipt_monotonic_ns']
        if any(type(value) is not int for value in
               (first_clock, last_clock, first_wall, last_wall)):
            raise ValueError('measurement endpoints must be integers')
        source_span, wall_span = last_clock-first_clock, last_wall-first_wall
        if source_span < int(speed_spec['measurement_min_source_span_ns']) or wall_span <= 0:
            raise ValueError('measurement window is too short or reversed')
        if 'warmup_source_span_ns' in speed_spec:
            first_valid = endpoints.get('first_valid_source_ns')
            warmup_target = endpoints.get('warmup_target_ns')
            warmup_span = int(speed_spec['warmup_source_span_ns'])
            if type(first_valid) is not int or type(warmup_target) is not int:
                fail(errors, 'speed: warmup target evidence missing')
            elif warmup_target != first_valid + warmup_span:
                fail(errors, 'speed: warmup target differs from first valid source plus frozen span')
            if measurement.get('warmup_source_span_ns') != warmup_span:
                fail(errors, 'speed: warmup source span differs from frozen config')
            if type(warmup_target) is int and first_clock < warmup_target:
                fail(errors, 'speed: measurement c0 precedes warmup target')
            selection_rule = speed_spec.get('matrix', {}).get('selection_rule')
            if not isinstance(selection_rule, str) or not selection_rule or \
                    endpoints.get('selection_rule') != selection_rule:
                fail(errors, 'speed: automatic endpoint selection rule mismatch')
        actual = source_span / wall_span
        reported = measurement.get('actual_factor')
        if isinstance(reported, bool) or not isinstance(reported, (int, float)) or \
                not math.isfinite(reported):
            raise ValueError('actual_factor missing/nonfinite')
        if not math.isclose(actual, reported, rel_tol=1e-9, abs_tol=1e-12):
            fail(errors, 'speed: reported actual_factor differs from endpoints')
        requested = float(case['requested_factor'])
        if not math.isclose(float(measurement.get('requested_factor')), requested,
                            rel_tol=0., abs_tol=0.):
            fail(errors, 'speed: requested_factor differs from frozen case')
        tolerance = float(speed_spec['tolerance_fraction'])
        factor_passed = requested*(1-tolerance) <= actual <= requested*(1+tolerance)
        if measurement.get('factor_passed') is not factor_passed:
            fail(errors, 'speed: claimed factor_passed differs from recomputed gate')
        if speed_spec.get('static_unarmed_required') and measurement.get('armed') is not False:
            fail(errors, 'speed: static/unarmed evidence missing')
        if speed_spec.get('static_unarmed_required') and measurement.get('static_unarmed') is not True:
            fail(errors, 'speed: static_unarmed gate not sealed')
        if speed_spec.get('strict_clock_increase_required') and \
                measurement.get('strict_clock_increase') is not True:
            fail(errors, 'speed: strict clock increase evidence missing')
        if measurement.get('terminal_count') != int(speed_spec.get('terminal_count', 0)):
            fail(errors, 'speed: terminal count mismatch')
        source_count = measurement.get('measurement_source_states')
        adapted_count = measurement.get('measurement_adapted_states')
        if type(source_count) is not int or source_count <= 0 or adapted_count != source_count or \
                measurement.get('window_identity_complete') is not True:
            fail(errors, 'speed: measurement-window source/adapted identity is incomplete')
        if measurement.get('timestamp_identity_basis') != \
                'measurement_window_sample_id_time_usec_with_raw_overlap':
            fail(errors, 'speed: timestamp identity basis mismatch')
        raw_matches = measurement.get('raw_odometry_timestamp_matches')
        raw_counts = measurement.get('raw_counts')
        if type(raw_matches) is not int or raw_matches <= 0 or not isinstance(raw_counts, dict) or \
                _int(raw_counts.get('0', 0)) <= 0 or _int(raw_counts.get('331', 0)) <= 0:
            fail(errors, 'speed: real MAVLink heartbeat/ODOMETRY overlap evidence missing')
        allowed_rewrite = speed_spec.get('source_timestamp_rewrite_allowed', False)
        if measurement.get('timestamp_rewrite_detected') is not allowed_rewrite:
            fail(errors, 'speed: source timestamp rewrite evidence mismatch')
        reported_errors = measurement.get('errors')
        if not isinstance(reported_errors, list):
            fail(errors, 'speed: observer errors field is invalid')
        elif reported_errors:
            fail(errors, 'speed: observer reported errors: ' + '; '.join(map(str, reported_errors)))
        expected_python = PYTHON
        if measurement.get('observer_python') != expected_python or measurement.get('node_pythons') != {
                'simulation/state_clock': expected_python,
                'sensors/state_adapter': expected_python}:
            fail(errors, 'speed: observer/node Conda identity mismatch')
        if measurement.get('measurement_source_span_ns') != source_span or \
                measurement.get('measurement_wall_span_ns') != wall_span:
            fail(errors, 'speed: sealed span summary differs from endpoints')
        for key in ('clock_receipt_hz', 'source_receipt_hz', 'source_sim_time_hz'):
            value = measurement.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or \
                    not math.isfinite(value) or value <= 0:
                fail(errors, 'speed: invalid frequency metric ' + key)
        for key in ('measurement_clock_samples', 'max_source_interval_ns',
                    'max_source_receipt_interval_ns'):
            value = measurement.get(key)
            if type(value) is not int or value <= 0:
                fail(errors, 'speed: invalid interval/count metric ' + key)
        cpu = measurement.get('cpu_environment')
        if not isinstance(cpu, dict) or not isinstance(cpu.get('model'), str) or \
                type(cpu.get('logical_count')) is not int or cpu.get('logical_count') <= 0 or \
                not isinstance(cpu.get('affinity'), list) or not cpu.get('affinity') or \
                any(type(value) is not int for value in cpu.get('affinity', [])):
            fail(errors, 'speed: CPU environment evidence is incomplete')
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
        fail(errors, 'speed: invalid measurement ' + str(exc))
    return dict(measurement_complete=complete, factor_passed=factor_passed,
                actual_factor=actual, passed=complete and factor_passed and not errors,
                errors=errors)


def validate_speed_measurement(measurement, case, speed_spec):
    """兼容纯函数调用者；详细分类使用evaluate_speed_measurement。"""
    result = evaluate_speed_measurement(measurement, case, speed_spec)
    errors = list(result['errors'])
    if result['measurement_complete'] and not result['factor_passed'] and not errors:
        errors.append('speed: actual_factor outside requested +/- tolerance')
    return errors


def _speed_case_name(scenario):
    matches = [name for name, (candidate, _) in SPEED_CASES.items()
               if candidate == str(scenario).upper()]
    return matches[0] if len(matches) == 1 else None


def _validate_speed_endpoint_selection(measurement, rows, speed_spec, errors):
    """用原始观察序列证明预热及两个端点均由冻结规则首个命中。"""
    if 'warmup_source_span_ns' not in speed_spec:
        return
    endpoints = measurement.get('endpoints')
    if not isinstance(endpoints, dict):
        fail(errors, 'speed: automatic endpoint evidence missing')
        return
    first_valid = endpoints.get('first_valid_source_ns')
    warmup_target = endpoints.get('warmup_target_ns')
    c0, c1 = endpoints.get('c0_ns'), endpoints.get('c1_ns')
    source_valid = [row.get('timestamp_ns') for row in rows
                    if row.get('event') == 'state' and row.get('channel') == 'source' and
                    row.get('status') == 'valid' and type(row.get('timestamp_ns')) is int]
    clocks = [row.get('timestamp_ns') for row in rows
              if row.get('event') == 'clock' and type(row.get('timestamp_ns')) is int]
    if not source_valid or source_valid[0] != first_valid:
        fail(errors, 'speed: first valid source endpoint identity mismatch')
    if not clocks or type(warmup_target) is not int or type(c0) is not int or type(c1) is not int:
        fail(errors, 'speed: automatic endpoint observation evidence incomplete')
        return
    first_c0 = next((value for value in clocks if value >= warmup_target), None)
    if first_c0 != c0:
        fail(errors, 'speed: automatic c0 is not the first clock at/after warmup target')
    measurement_span = int(speed_spec['measurement_min_source_span_ns'])
    first_c1 = next((value for value in clocks if value >= c0 + measurement_span), None)
    if first_c1 != c1:
        fail(errors, 'speed: automatic c1 is not the first clock completing measurement span')


def _validate_frozen_identity(actual, expected, label, errors, check_file=False):
    required = {'path', 'size', 'mtime_ns', 'sha256'}
    if not isinstance(actual, dict) or set(actual) != required:
        fail(errors, 'speed matrix: %s identity fields missing' % label)
        return
    if actual != expected:
        fail(errors, 'speed matrix: %s identity drift' % label)
    if check_file and actual == expected:
        current = file_identity(actual.get('path'), errors, label)
        if current != actual:
            fail(errors, 'speed matrix: %s no longer matches frozen file' % label)


def validate_speed_run_artifacts(run, run_id, case_name, config,
                                 expected_matrix_entry=None, frozen=None):
    """审计单个倍速run；旧SIM-01C配置不强制SIM-SPEED-01新增字段。"""
    run = Path(run).resolve()
    errors = []
    speed_spec = config.get('speed_smoke', {})
    case = speed_spec.get('cases', {}).get(case_name)
    if case is None:
        return dict(passed=False, errors=['unknown speed case'], case=case_name,
                    measurement_complete=False, factor_passed=False, actual_factor=None)
    expected_scenario = SPEED_CASES.get(case_name, (None, None))[0]
    measurement = read_json(run / 'speed-result.json', errors)
    evaluated = evaluate_speed_measurement(measurement, case, speed_spec, run_id)
    errors.extend(evaluated['errors'])
    observations = read_lines(run / 'speed-observations.jsonl', errors,
                              required='warmup_source_span_ns' in speed_spec)
    _validate_speed_endpoint_selection(measurement, observations, speed_spec, errors)
    manifest = read_json(run / 'manifest.json', errors)
    cleanup = read_json(run / 'cleanup-audit.json', errors)
    if manifest.get('run_id') != run_id or manifest.get('scenario') != expected_scenario:
        fail(errors, 'speed: manifest run/scenario mismatch')
    if manifest.get('python') != PYTHON or manifest.get('streams_configured') is not True:
        fail(errors, 'speed: supervisor interpreter/stream configuration missing')
    if manifest.get('errors'):
        fail(errors, 'speed: supervisor reported infrastructure errors')
    if manifest.get('armed_commands') is not False:
        fail(errors, 'speed: manifest does not prove absence of arm/control commands')
    stream_commands = {item.get('name'): item for item in manifest.get('commands', [])
                       if item.get('name') in ('stream-HIGHRES_IMU', 'stream-ODOMETRY')}
    if set(stream_commands) != {'stream-HIGHRES_IMU', 'stream-ODOMETRY'} or \
            any(item.get('exit') != 0 for item in stream_commands.values()):
        fail(errors, 'speed: PX4 telemetry stream commands not sealed successful')
    requested_text = str(case['requested_factor'])
    process_commands = {item.get('name'): item for item in manifest.get('commands', [])
                        if item.get('name') in ('bridge', 'px4')}
    if set(process_commands) != {'bridge', 'px4'} or any(
            item.get('environment_overrides', {}).get('PX4_SIM_SPEED_FACTOR') != requested_text
            for item in process_commands.values()):
        fail(errors, 'speed: requested factor did not reach both bridge and PX4')
    audit = manifest.get('python_process_audit', {})
    resolved_python = str(Path(PYTHON).resolve())
    if audit.get('passed') is not True or audit.get('expected') != resolved_python or any(
            item.get('executable') != resolved_python for item in audit.get('processes', [])):
        fail(errors, 'speed: supervisor Conda descendant audit failed')
    if cleanup.get('passed') is not True or cleanup.get('forced') or \
            cleanup.get('remaining_audited_python_pids') or not cleanup.get('ports') or any(
                item.get('free') is not True for item in cleanup.get('ports', [])):
        fail(errors, 'speed: cleanup/port release evidence failed')

    if expected_matrix_entry is not None:
        if manifest.get('speed_matrix') != expected_matrix_entry:
            fail(errors, 'speed matrix: per-run matrix identity mismatch')
        if manifest.get('phase') != 'COMPLETE' or manifest.get('exit') != 0 or \
                manifest.get('acceptance_failures'):
            fail(errors, 'speed matrix: run is not a sealed GREEN result')
        if manifest.get('run') != str(run):
            fail(errors, 'speed matrix: per-run path identity mismatch')
        if not isinstance(frozen, dict):
            fail(errors, 'speed matrix: frozen suite identity missing')
        else:
            for manifest_key, frozen_key, label in (
                    ('bridge_binary', 'candidate_binary', 'candidate binary'),
                    ('tool_identity', 'tool_identity', 'tool'),
                    ('config_identity', 'config_identity', 'config')):
                _validate_frozen_identity(manifest.get(manifest_key), frozen.get(frozen_key),
                                          label, errors)
            if manifest.get('boot_id') != frozen.get('boot_id'):
                fail(errors, 'speed matrix: boot_id drift')
            bridge = process_commands.get('bridge', {})
            args = bridge.get('args')
            expected_binary = frozen.get('candidate_binary', {}).get('path')
            if not isinstance(args, list) or not args or \
                    str(Path(args[0]).resolve()) != expected_binary:
                fail(errors, 'speed matrix: bridge command did not execute frozen candidate')
    if evaluated['measurement_complete'] and not evaluated['factor_passed'] and \
            not evaluated['errors']:
        fail(errors, 'speed: actual_factor outside requested +/- tolerance')
    return dict(passed=evaluated['passed'] and not errors, errors=errors, case=case_name,
                measurement_complete=evaluated['measurement_complete'],
                factor_passed=evaluated['factor_passed'],
                actual_factor=evaluated['actual_factor'])


def _canonical_matrix_plan(matrix_id):
    return [dict(matrix_id=matrix_id, global_index=index, batch=batch,
                 batch_index=batch_index, scenario=scenario, requested_factor=factor)
            for index, (batch, batch_index, scenario, factor)
            in enumerate(SPEED_MATRIX_PLAN, 1)]


def validate_speed_matrix(suite, config):
    """整批核对预注册九run，拒绝缺项、乱序、替换和冻结身份漂移。"""
    suite = Path(suite).resolve()
    errors = []
    matrix = read_json(suite / 'speed-matrix-manifest.json', errors)
    suite_manifest = read_json(suite / 'suite-manifest.json', errors)
    speed_spec = config.get('speed_smoke', {})
    cases = speed_spec.get('cases', {})
    if set(cases) != {'half', 'nominal', 'double'}:
        fail(errors, 'speed matrix: cases must be exactly half/nominal/double')
    for case_name, (_, factor) in SPEED_CASES.items():
        try:
            configured = float(cases[case_name]['requested_factor'])
        except (KeyError, TypeError, ValueError):
            configured = None
        if configured != factor:
            fail(errors, 'speed matrix: %s requested factor mismatch' % case_name)
    matrix_id = matrix.get('matrix_id')
    expected_plan = _canonical_matrix_plan(matrix_id)
    config_plan = speed_spec.get('matrix', {}).get('planned_runs')
    expected_config_plan = [{key: value for key, value in item.items() if key != 'matrix_id'}
                            for item in expected_plan]
    if config_plan != expected_config_plan:
        fail(errors, 'speed matrix: config planned sequence differs from frozen nine runs')
    planned = matrix.get('planned_runs')
    actual = matrix.get('actual_runs')
    if planned != expected_plan:
        fail(errors, 'speed matrix: planned sequence is not the preregistered nine runs')
    if not isinstance(actual, list) or len(actual) != 9:
        fail(errors, 'speed matrix: actual sequence must contain exactly nine runs')
        actual = actual if isinstance(actual, list) else []
    if matrix.get('schema_version') != '0.1' or not isinstance(matrix_id, str) or not matrix_id:
        fail(errors, 'speed matrix: manifest schema/matrix_id invalid')
    if matrix.get('errors') or matrix.get('phase') != 'COMPLETE' or matrix.get('exit') != 0:
        fail(errors, 'speed matrix: batch is not sealed COMPLETE without errors')

    frozen = {key: matrix.get(key) for key in
              ('candidate_binary', 'tool_identity', 'config_identity', 'boot_id')}
    for key, label in (('candidate_binary', 'candidate binary'),
                       ('tool_identity', 'tool'), ('config_identity', 'config')):
        _validate_frozen_identity(frozen[key], frozen[key], label, errors, check_file=True)
    if not isinstance(frozen['boot_id'], str) or not frozen['boot_id']:
        fail(errors, 'speed matrix: boot_id missing')
    suite_speed = suite_manifest.get('speed_matrix', {})
    if suite_manifest.get('suite_run_id') != matrix.get('suite_run_id') or \
            suite_speed.get('matrix_id') != matrix_id or \
            suite_speed.get('planned_runs') != planned or \
            str(Path(suite_speed.get('manifest', '')).resolve()) != \
            str((suite / 'speed-matrix-manifest.json').resolve()):
        fail(errors, 'speed matrix: suite manifest identity/plan mismatch')
    if suite_manifest.get('bridge_binary') != frozen['candidate_binary']:
        fail(errors, 'speed matrix: suite candidate binary identity mismatch')
    for key, label in (('tool_identity', 'tool'), ('config_identity', 'config')):
        if suite_manifest.get(key) != frozen[key]:
            fail(errors, 'speed matrix: suite %s identity mismatch' % label)
    if suite_manifest.get('boot_id') != frozen['boot_id']:
        fail(errors, 'speed matrix: suite boot_id mismatch')
    if suite_manifest.get('phase') != 'COMPLETE' or suite_manifest.get('exit') != 0:
        fail(errors, 'speed matrix: suite manifest is not COMPLETE')
    expected_suite_results = [
        {key: item.get(key) for key in ('scenario', 'run', 'run_id', 'phase', 'exit')}
        for item in actual]
    if suite_manifest.get('results') != expected_suite_results:
        fail(errors, 'speed matrix: suite actual result sequence mismatch')

    run_paths, run_ids = set(), set()
    for index, expected in enumerate(expected_plan):
        if index >= len(actual):
            break
        item = actual[index]
        identity = {key: item.get(key) for key in expected}
        if identity != expected or item.get('phase') != 'COMPLETE' or item.get('exit') != 0:
            fail(errors, 'speed matrix: actual sequence/run identity mismatch at index %d' % (index+1))
        run_value, run_id = item.get('run'), item.get('run_id')
        try:
            run = Path(run_value).resolve()
        except TypeError:
            fail(errors, 'speed matrix: run identity/path missing at index %d' % (index+1))
            continue
        if run.parent != suite or not run.name.endswith('-m%02d' % (index+1)) or \
                str(run) in run_paths or not isinstance(run_id, str) or not run_id or run_id in run_ids:
            fail(errors, 'speed matrix: run identity/path is not unique/frozen at index %d' % (index+1))
        run_paths.add(str(run))
        run_ids.add(run_id)
        case_name = _speed_case_name(expected['scenario'])
        result = validate_speed_run_artifacts(run, run_id, case_name, config, expected, frozen)
        errors.extend('run %02d: %s' % (index+1, error) for error in result['errors'])
        scenario_result = read_json(run / 'scenario-result.json', errors)
        if scenario_result.get('passed') is not True or scenario_result.get('errors') or \
                scenario_result.get('case') != case_name or \
                scenario_result.get('measurement_complete') is not True or \
                scenario_result.get('factor_passed') is not True:
            fail(errors, 'speed matrix: sealed scenario result is not GREEN at index %d' % (index+1))
    return dict(passed=not errors, errors=errors, matrix_id=matrix_id,
                planned_runs=len(planned) if isinstance(planned, list) else 0,
                actual_runs=len(actual))


def _audit_rows(run, name, observed_rows, topic, errors, required=True):
    rows = read_lines(run / name, errors, required=required)
    marker = read_json(run / (name + '.closed.json'), errors, required=required)
    if not required and not rows and not marker:
        return {}, []
    if marker.get('passed') is not True or marker.get('records') != len(rows):
        fail(errors, name + ': audit is not successfully sealed')
    if marker.get('python') != PYTHON:
        fail(errors, name + ': sealed interpreter mismatch')
    if any(row.get('seq') != index for index, row in enumerate(rows, 1)):
        fail(errors, name + ': seq is not consecutive')
    counts = Counter(row.get('topic') for row in rows)
    if marker.get('topic_counts') != dict(counts):
        fail(errors, name + ': sealed topic counts mismatch')
    audit_identity = [(row.get('timestamp'), row.get('sample_id')) for row in rows
                      if row.get('topic') == topic]
    observed_identity = [(_header(row).get('timestamp'), _header(row).get('sample_id'))
                         for row in observed_rows if row.get('topic') == topic]
    if audit_identity != observed_identity:
        fail(errors, name + ': observer/audit ordered identity mismatch')
    return marker, rows


def _validate_cleanup(cleanup, manifest, trigger, spec, scenario, errors):
    if cleanup.get('passed') is not True or cleanup.get('forced'):
        fail(errors, scenario + ': cleanup failed or used forced signal')
    if cleanup.get('remaining_audited_python_pids'):
        fail(errors, scenario + ': audited Python PID remains')
    ports = cleanup.get('ports')
    if not isinstance(ports, list) or not ports or any(item.get('free') is not True for item in ports):
        fail(errors, scenario + ': port release was not proven')
    start = manifest.get('cleanup_start_monotonic_ns')
    receipt = trigger.get('receipt_monotonic_ns')
    if type(start) is not int or type(receipt) is not int or start < receipt:
        fail(errors, scenario + ': cleanup was not causally triggered by observation')
    if scenario == 'F6' and type(start) is int and type(receipt) is int:
        limit = float(spec['expected']['cleanup_start_max_from_error_wall_s'])*1e9
        if start-receipt > limit:
            fail(errors, 'F6: cleanup did not start within ERROR deadline')


def validate_artifacts(run, run_id, scenario, config, previous_run=None):
    run = Path(run).resolve()
    errors = []
    spec = config['scenarios'][scenario]
    manifest = read_json(run / 'manifest.json', errors)
    rows = read_lines(run / 'scenario-observations.jsonl', errors)
    trigger = read_json(run / 'supervisor-trigger.json', errors)
    cleanup = read_json(run / 'cleanup-audit.json', errors)
    driver_rows = read_lines(run / 'driver-events.jsonl', errors, required=scenario != 'F6')
    driver_result = read_json(run / 'driver-result.json', errors, required=scenario != 'F6')
    previous_rows = []
    if scenario == 'F7':
        if previous_run is None:
            fail(errors, 'F7: predecessor run is required')
        else:
            previous_rows = read_lines(Path(previous_run) / 'scenario-observations.jsonl', errors)
    source_start = manifest.get('source_start_monotonic_ns')
    errors.extend(validate_observations(rows, run_id, scenario, spec, driver_rows,
                                       previous_rows, source_start))

    expected_terminal = spec['expected'].get('terminal_code')
    if manifest.get('run_id') != run_id or scenario_key(str(manifest.get('scenario', ''))) != scenario:
        fail(errors, scenario + ': manifest run/scenario mismatch')
    if manifest.get('errors'):
        fail(errors, scenario + ': supervisor reported errors')
    if manifest.get('checker_exit') != 0:
        fail(errors, scenario + ': online checker did not exit successfully')
    if scenario != 'F6' and manifest.get('driver_exit') != 0:
        fail(errors, scenario + ': fault driver did not exit successfully')
    if scenario != 'F6' and (driver_result.get('passed') is not True or
                             driver_result.get('run_id') != run_id or
                             scenario_key(str(driver_result.get('scenario', ''))) != scenario or
                             driver_result.get('python') != PYTHON):
        fail(errors, scenario + ': fault driver result is incomplete or has wrong identity')
    if expected_terminal and manifest.get('expected_reason') not in (expected_terminal,
                                                                     'terminal:' + expected_terminal):
        fail(errors, scenario + ': manifest expected reason mismatch')
    embedded_trigger = manifest.get('supervisor_trigger')
    if (trigger.get('passed') is not True or trigger.get('observed') is not True or
            trigger.get('scenario') not in (scenario, 'C-' + scenario) or
            trigger.get('run_id') != run_id):
        fail(errors, scenario + ': valid supervisor trigger missing')
    if not isinstance(embedded_trigger, dict) or embedded_trigger.get('observed') is not True or \
            embedded_trigger.get('receipt_monotonic_ns') != trigger.get('receipt_monotonic_ns'):
        fail(errors, scenario + ': manifest did not preserve checker trigger')
    _validate_cleanup(cleanup, manifest, trigger, spec, scenario, errors)

    audit_names = manifest.get('audit_files', {})
    source_name = audit_names.get('source', 'source-audit.jsonl')
    sensor_name = audit_names.get('sensors', 'sensor-audit.jsonl')
    source_marker, _ = _audit_rows(run, source_name, rows, SOURCE, errors, required=scenario != 'F6')
    sensor_marker, _ = _audit_rows(run, sensor_name, rows, SENSOR, errors)
    expected = spec['expected']
    if scenario != 'F6':
        expected_phase = 'ACTIVE' if scenario == 'F7' else 'FAULT'
        if source_marker.get('phase') != expected_phase:
            fail(errors, scenario + ': source audit phase mismatch')
        counters = source_marker.get('counters', {})
        if expected_terminal and _int(counters.get(expected_terminal, 0)) != expected.get(
                'source_fault_diagnostic_count', 1):
            fail(errors, scenario + ': source fault counter mismatch')
        if scenario == 'F1' and _int(counters.get('pending_timeout', 0)) < 1:
            fail(errors, 'F1: sealed source audit lacks pending_timeout counter')
        if scenario != 'F1' and _int(counters.get('pending_timeout', 0)):
            fail(errors, scenario + ': unexpected sealed pending_timeout counter')
    if sensor_marker.get('locked') is not expected.get('gate_locked'):
        fail(errors, scenario + ': sealed gate lock state mismatch')
    if sensor_marker.get('pending_count') != expected.get('pending_count', 0):
        fail(errors, scenario + ': sealed pending queue is not empty')
    sensor_counters = sensor_marker.get('counters', {})
    if _int(sensor_counters.get('published_terminal', 0)) != expected.get('sensors_terminal_count'):
        fail(errors, scenario + ': sealed sensors terminal counter mismatch')
    if scenario == 'F6' and _int(sensor_counters.get('clock_regression', 0)) != expected.get(
            'local_error_diagnostic_count'):
        fail(errors, 'F6: sealed clock_regression counter mismatch')
    if scenario == 'F6':
        if _int(sensor_counters.get('accepted_states', -1)) != expected.get('accepted_states'):
            fail(errors, 'F6: sealed audit does not prove both states were consumed')
        if _int(sensor_counters.get('published_states', -1)) != expected.get('published_states'):
            fail(errors, 'F6: sealed audit does not prove future state remained pending')
    python_audit = manifest.get('python_process_audit', {})
    resolved_python = str(Path(PYTHON).resolve())
    if python_audit.get('passed') is not True or python_audit.get('expected') != resolved_python or \
            any(item.get('executable') != resolved_python
                for item in python_audit.get('processes', [])):
        fail(errors, scenario + ': Conda descendant audit failed')
    return dict(passed=not errors, errors=errors, scenario='C-' + scenario, run_id=run_id,
                source_terminals=len(_terminal_rows(rows, SOURCE)),
                sensors_terminals=len(_terminal_rows(rows, SENSOR)), observations=len(rows))


class OnlineObserver:
    def __init__(self, run, run_id, scenario, spec, previous_run=None):
        self.run, self.run_id, self.scenario = Path(run), run_id, scenario
        self.spec, self.previous_run = spec, previous_run
        self.rows, self.lock = [], threading.RLock()
        self.stream = (self.run / 'scenario-observations.jsonl').open('x')
        self.subscribers = []

    def _record(self, row):
        with self.lock:
            row = dict(row, event_seq=len(self.rows)+1, receipt_monotonic_ns=time.monotonic_ns())
            self.rows.append(row)
            self.stream.write(json.dumps(row, separators=(',', ':')) + '\n')
            self.stream.flush()

    def start(self):
        import rospy
        from diagnostic_msgs.msg import DiagnosticArray
        from rosgraph_msgs.msg import Clock
        from uav_fusionmap_msgs.msg import AircraftState
        from ufm_ros_contract import from_ros_state

        self.subscribers = [
            rospy.Subscriber(CLOCK, Clock,
                             lambda msg: self._record(dict(topic=CLOCK, timestamp=msg.clock.to_nsec())),
                             queue_size=1000),
            rospy.Subscriber(SOURCE, AircraftState,
                             lambda msg: self._record(dict(topic=SOURCE, state=from_ros_state(msg))),
                             queue_size=1000),
            rospy.Subscriber(SENSOR, AircraftState,
                             lambda msg: self._record(dict(topic=SENSOR, state=from_ros_state(msg))),
                             queue_size=1000),
            rospy.Subscriber(DIAGNOSTIC, DiagnosticArray, self._diagnostic, queue_size=1000)]

    def _diagnostic(self, message):
        for item in message.status:
            self._record(dict(topic=DIAGNOSTIC, name=item.name, level=item.level,
                              message=item.message, hardware_id=item.hardware_id,
                              values={value.key: value.value for value in item.values}))

    def _f6_inject(self):
        import rospy
        from rosgraph_msgs.msg import Clock
        from uav_fusionmap_msgs.msg import AircraftState
        from ufm_ros_contract import to_ros_state
        state_pub = rospy.Publisher(SOURCE, AircraftState, queue_size=10)
        clock_pub = rospy.Publisher(CLOCK, Clock, queue_size=10)
        deadline = time.monotonic() + 5.
        while time.monotonic() < deadline and not rospy.is_shutdown():
            # checker和state_adapter必须都真正连接fixture publisher。
            if state_pub.get_num_connections() >= 2 and clock_pub.get_num_connections() >= 2:
                break
            time.sleep(.02)
        else:
            raise RuntimeError('F6 fixture publisher connections not ready')

        deadline = time.monotonic() + 5.
        ready_path = self.run / 'sensor-audit.jsonl.ready.json'
        while time.monotonic() < deadline and not rospy.is_shutdown():
            if ready_path.exists():
                break
            time.sleep(.02)
        else:
            raise RuntimeError('F6 sensor publication audit is not ready')

        def state(ns):
            quality = {'confidence': None, 'uncertainty': {
                'status': 'unavailable', 'value': None, 'kind': 'pose_covariance',
                'unit': 'mixed', 'source': 'PX4 TODO'}}
            return {'header': {'schema_version': '0.1', 'run_id': self.run_id,
                               'clock_id': 'sim:' + self.run_id, 'timestamp': ns,
                               'sample_id': 'sim.odometry:1:1:%d' % (ns//1000),
                               'frame_id': 'world_ned', 'source_type': 'simulation',
                               'status': 'valid', 'reason': ''},
                    'position': [0., 0., 0.], 'orientation_xyzw': [0., 0., 0., 1.],
                    'linear_velocity': [0., 0., 0.], 'body_frame_id': 'body_frd',
                    'velocity_frame_id': 'body_frd', 'state_source': 'estimated',
                    'quality': quality}

        def clock(ns):
            return Clock(clock=rospy.Time(ns//1_000_000_000, ns % 1_000_000_000))
        # fixture publisher连接和audit就绪后，再等checker真实收到adapter周期诊断，
        # 作为节点发布通道已工作的证据；最终state是否被consume/pending仍以封存counter判定。
        deadline = time.monotonic() + 2.5
        while time.monotonic() < deadline:
            with self.lock:
                adapter_ready = bool(_diagnostic_rows(
                    self.rows, 'sensors/state_adapter', 'clock_gate'))
            if adapter_ready:
                break
            time.sleep(.02)
        else:
            raise RuntimeError('F6 state_adapter diagnostic channel not observed')
        baseline_ns = 10_000_000_000
        state_pub.publish(to_ros_state(state(baseline_ns)))
        time.sleep(.03)
        clock_pub.publish(clock(baseline_ns))
        deadline = time.monotonic() + 1.
        while time.monotonic() < deadline:
            with self.lock:
                if _state_rows(self.rows, SENSOR, 'valid'):
                    break
            time.sleep(.02)
        else:
            raise RuntimeError('F6 gate did not publish initial valid state')
        future_ns = baseline_ns + 2_000_000_000
        state_pub.publish(to_ros_state(state(future_ns)))
        deadline = time.monotonic() + .5
        while time.monotonic() < deadline:
            with self.lock:
                if any(_header(row).get('timestamp') == future_ns
                       for row in _state_rows(self.rows, SOURCE, 'valid')):
                    break
            time.sleep(.02)
        else:
            raise RuntimeError('F6 future source state was not observed before regression')
        clock_pub.publish(clock(baseline_ns - 1_000_000_000))

    def run_until_trigger(self):
        import rospy
        self.start()
        if self.scenario == 'F6':
            self._f6_inject()
        cutoff = time.monotonic() + float(self.spec['wall_safety_cutoff_s'])
        drain_ns = int(float(self.spec.get('terminal_drain_s', .5))*1e9)
        trigger_receipt = None
        while time.monotonic() < cutoff and not rospy.is_shutdown():
            with self.lock:
                source_terms = _terminal_rows(self.rows, SOURCE)
                sensor_terms = _terminal_rows(self.rows, SENSOR)
                if self.scenario == 'F6':
                    matches = _diagnostic_rows(self.rows, 'sensors/state_adapter', 'clock_regression', 2)
                    if matches:
                        trigger_receipt = matches[0]['receipt_monotonic_ns']
                        # 立即交给监督器收尾，保证ERROR后0.5秒内开始清理；最终locked/pending
                        # 状态由PublicationAudit close标记核对。
                        completed = True
                    else:
                        completed = False
                elif self.scenario == 'F7':
                    minimum = self.spec['expected']['min_new_run_valid_count']
                    valid = min(len(_state_rows(self.rows, SOURCE, 'valid')),
                                len(_state_rows(self.rows, SENSOR, 'valid')))
                    completed = valid >= minimum
                    if completed:
                        receipts = [row['receipt_monotonic_ns'] for row in
                                    _state_rows(self.rows, SOURCE, 'valid') + _state_rows(self.rows, SENSOR, 'valid')]
                        trigger_receipt = max(receipts)
                else:
                    completed = len(source_terms) == 1 and len(sensor_terms) == 1
                    if completed:
                        trigger_receipt = max(source_terms[0]['receipt_monotonic_ns'],
                                              sensor_terms[0]['receipt_monotonic_ns'])
                        now_ns = time.monotonic_ns()
                        if self.scenario == 'F3':
                            driver = read_lines(self.run / 'driver-events.jsonl', [], required=False)
                            recovery = [row for row in driver
                                        if row.get('publish_end_monotonic_ns', 0) >
                                        source_terms[0]['receipt_monotonic_ns']]
                            completed = bool(recovery) and now_ns >= trigger_receipt + drain_ns
                        else:
                            completed = now_ns >= trigger_receipt + drain_ns
                # driver-result只表示完整执行了注入计划；必须在它封存后才触发监督器清理，
                # 否则F1/F2/F3/F7会把仍在发送的driver误判为失败。
                if completed and self.scenario != 'F6':
                    driver_result = read_json(self.run / 'driver-result.json', [], required=False)
                    completed = (driver_result.get('passed') is True and
                                 driver_result.get('run_id') == self.run_id and
                                 scenario_key(str(driver_result.get('scenario', ''))) == self.scenario)
            if completed:
                break
            time.sleep(.02)
        else:
            raise RuntimeError('expected SIM-01C observation not reached before safety cutoff')
        driver = read_lines(self.run / 'driver-events.jsonl', [], required=False)
        previous = read_lines(Path(self.previous_run) / 'scenario-observations.jsonl', [], required=False) \
            if self.previous_run else []
        manifest = read_json(self.run / 'manifest.json', [], required=False)
        errors = validate_observations(
            list(self.rows), self.run_id, self.scenario, self.spec, driver, previous,
            manifest.get('source_start_monotonic_ns'))
        if errors:
            raise RuntimeError('; '.join(errors))
        trigger = dict(passed=True, observed=True, scenario='C-' + self.scenario,
                       run_id=self.run_id, receipt_monotonic_ns=trigger_receipt,
                       written_monotonic_ns=time.monotonic_ns(), kind='expected_fault_observed'
                       if self.scenario != 'F7' else 'new_run_valid_observed')
        write_json_exclusive(self.run / 'supervisor-trigger.json', trigger)
        return trigger

    def close(self):
        for subscriber in self.subscribers:
            subscriber.unregister()
        self.stream.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('scenario')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--previous-run', type=Path)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    _, config = load_config(root, args.config)

    if args.scenario.upper() == 'SPEED-MATRIX':
        if not args.offline:
            parser.error('speed matrix validation is offline-only')
        result = validate_speed_matrix(args.run, config)
        (args.run / 'speed-matrix-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        return 0 if result['passed'] else 1

    if args.scenario.upper().startswith('SPEED-'):
        if not args.offline:
            parser.error('speed measurement is offline-only')
        case_name = args.scenario.split('-', 1)[1].lower()
        result = validate_speed_run_artifacts(args.run, args.run_id, case_name, config)
        (args.run / 'scenario-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        return 0 if result['passed'] else 1

    scenario = scenario_key(args.scenario)
    if scenario not in config.get('scenarios', {}):
        parser.error('scenario missing from config')
    if sys.executable != PYTHON:
        raise RuntimeError('checker must use configured Conda Python: ' + sys.executable)
    if args.offline:
        result = validate_artifacts(args.run, args.run_id, scenario, config, args.previous_run)
        (args.run / 'scenario-result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        return 0 if result['passed'] else 1

    import rospy
    rospy.init_node('sim01c_checker')
    spec = dict(config['scenarios'][scenario])
    spec['terminal_drain_s'] = config['safety']['terminal_drain_s']
    observer = OnlineObserver(args.run, args.run_id, scenario, spec, args.previous_run)
    try:
        trigger = observer.run_until_trigger()
        print(json.dumps(trigger), flush=True)
        return 0
    finally:
        observer.close()


if __name__ == '__main__':
    sys.exit(main())
