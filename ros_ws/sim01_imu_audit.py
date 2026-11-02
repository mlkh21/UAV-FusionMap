"""Pure audit for the live PX4 HIGHRES_IMU to ROS IMU path."""
import math


def _finite_vector(value, name, errors):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        errors.append(name + ' must have three values')
        return False
    if not all(isinstance(item, (int, float)) and math.isfinite(item) for item in value):
        errors.append(name + ' contains a non-finite value')
        return False
    return True


def _monotonic(samples, name, errors):
    timestamps = [sample['header']['timestamp'] for sample in samples]
    if any(not isinstance(value, int) for value in timestamps):
        errors.append(name + ' timestamp is not an integer')
    if any(right <= left for left, right in zip(timestamps, timestamps[1:])):
        errors.append(name + ' timestamps are not strictly increasing')


def audit_imu_samples(raw, source, adapted, clocks, run_id, min_samples=300):
    """Return a fail-closed report; ``raw`` is independently decoded MAVLink data."""
    errors = []
    valid_source = [sample for sample in source.values()
                    if sample['header']['status'] == 'valid']
    valid_adapted = [sample for sample in adapted.values()
                     if sample['header']['status'] == 'valid']
    if len(valid_source) < min_samples or len(valid_adapted) < min_samples:
        errors.append('insufficient live IMU samples')
    _monotonic(valid_source, 'source IMU', errors)
    _monotonic(valid_adapted, 'adapted IMU', errors)
    if any(right <= left for left, right in zip(clocks, clocks[1:])):
        errors.append('clock timestamps are not strictly increasing')
    clock_set = set(clocks)
    raw_matches = source_matches = adapted_matches = 0
    source_values = [[], [], []]
    gyro_values = [[], [], []]
    for sample in valid_source:
        header = sample['header']
        if (header['run_id'] != run_id or header['clock_id'] != 'sim:' + run_id or
                header['frame_id'] != 'body_frd' or header['source_type'] != 'simulation' or
                sample['acceleration_type'] != 'specific_force' or
                sample['calibration_id'] != '' or header['timestamp'] not in clock_set):
            errors.append('source IMU metadata or clock mismatch')
        if sample['acceleration_covariance'] is not None or sample['angular_velocity_covariance'] is not None:
            errors.append('source IMU covariance is not explicitly unavailable')
        accel_ok = _finite_vector(sample['linear_acceleration'], 'source acceleration', errors)
        gyro_ok = _finite_vector(sample['angular_velocity'], 'source angular velocity', errors)
        if accel_ok:
            for values, item in zip(source_values, sample['linear_acceleration']):
                values.append(item)
        if gyro_ok:
            for values, item in zip(gyro_values, sample['angular_velocity']):
                values.append(item)
        raw_value = raw.get(header['sample_id'])
        if raw_value is None:
            continue
        raw_matches += 1
        if (raw_value['timestamp'] != header['timestamp'] or
                any(abs(lhs - rhs) > 1e-6 for lhs, rhs in zip(
                    raw_value['linear_acceleration'], sample['linear_acceleration'])) or
                any(abs(lhs - rhs) > 1e-6 for lhs, rhs in zip(
                    raw_value['angular_velocity'], sample['angular_velocity']))):
            errors.append('raw HIGHRES_IMU to source value mismatch')
        else:
            source_matches += 1
    for sample in valid_adapted:
        header = sample['header']
        if (header['run_id'] != run_id or header['clock_id'] != 'sim:' + run_id or
                header['frame_id'] != 'imu' or header['source_type'] != 'derived' or
                sample['acceleration_type'] != 'specific_force' or
                sample['calibration_id'] != 'sim_pilot_virtual_flu_v1'):
            errors.append('adapted IMU metadata mismatch')
        if sample['acceleration_covariance'] is not None or sample['angular_velocity_covariance'] is not None:
            errors.append('adapted IMU covariance is not explicitly unavailable')
        _finite_vector(sample['linear_acceleration'], 'adapted acceleration', errors)
        _finite_vector(sample['angular_velocity'], 'adapted angular velocity', errors)
        prefix = 'sensors.imu:'
        source_id = header['sample_id'][len(prefix):] if header['sample_id'].startswith(prefix) else ''
        original = source.get(source_id)
        if original is None or original['header']['status'] != 'valid':
            errors.append('adapted IMU has no valid source identity')
            continue
        adapted_matches += 1
        expected_accel = [original['linear_acceleration'][0], -original['linear_acceleration'][1],
                          -original['linear_acceleration'][2]]
        expected_gyro = [original['angular_velocity'][0], -original['angular_velocity'][1],
                         -original['angular_velocity'][2]]
        if (header['timestamp'] != original['header']['timestamp'] or
                any(abs(lhs - rhs) > 1e-6 for lhs, rhs in zip(sample['linear_acceleration'], expected_accel)) or
                any(abs(lhs - rhs) > 1e-6 for lhs, rhs in zip(sample['angular_velocity'], expected_gyro))):
            errors.append('source to adapted IMU axis/value mismatch')
    if raw_matches < min_samples or source_matches < min_samples or adapted_matches < min_samples:
        errors.append('insufficient independently matched IMU samples')
    return {
        'passed': not errors,
        'errors': errors,
        'raw_samples': len(raw),
        'source_samples': len(valid_source),
        'adapted_samples': len(valid_adapted),
        'raw_source_matches': raw_matches,
        'source_value_matches': source_matches,
        'adapted_source_matches': adapted_matches,
        'acceleration_axes': [{'min': min(values), 'max': max(values),
                               'mean': sum(values) / len(values)} for values in source_values] if all(source_values) else None,
        'angular_velocity_axes': [{'min': min(values), 'max': max(values),
                                   'mean': sum(values) / len(values)} for values in gyro_values] if all(gyro_values) else None,
    }
