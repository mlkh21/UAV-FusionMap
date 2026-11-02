"""感知消费SensorBundle的组合契约；不重新配对或读取传感器私有状态。"""
import math


FORBIDDEN_INPUT_KEYS = frozenset({
    'lidar', 'training_lidar', 'target', 'occupancy_target', 'observed_mask',
    'supervision', 'lidar_points', 'lidar_voxels',
})


def reject_training_fields(value):
    """Online inputs never carry training supervision, including nested metadata."""
    if isinstance(value, dict):
        if FORBIDDEN_INPUT_KEYS.intersection(value):
            raise ValueError('online input contains training-only fields')
        for child in value.values():
            reject_training_fields(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            reject_training_fields(child)


def validate_transform(matrix):
    """available的刚体变换必须包含正旋转，不能通过反射改变占据位置。"""
    if len(matrix) != 16 or any(not math.isfinite(value) for value in matrix):
        raise ValueError('transform must be finite 4x4')
    if any(abs(a-b) > 1e-9 for a, b in zip(matrix[12:], (0, 0, 0, 1))):
        raise ValueError('transform must be homogeneous')
    for row in range(3):
        for col in range(3):
            dot = sum(matrix[4*row+k] * matrix[4*col+k] for k in range(3))
            if abs(dot - (1.0 if row == col else 0.0)) > 1e-6:
                raise ValueError('transform rotation must be orthonormal')
    determinant = (matrix[0]*(matrix[5]*matrix[10] - matrix[6]*matrix[9]) -
                   matrix[1]*(matrix[4]*matrix[10] - matrix[6]*matrix[8]) +
                   matrix[2]*(matrix[4]*matrix[9] - matrix[5]*matrix[8]))
    if abs(determinant - 1) > 1e-6:
        raise ValueError('transform must be a proper rotation')


def validate_context(bundle):
    """只有外层身份和上下文可信时，节点才可借其发出unavailable。"""
    header, context = bundle['header'], bundle['context']
    if (header['schema_version'] != '0.1' or
            any(not isinstance(header[key], str) or not header[key].strip()
                for key in ('run_id', 'clock_id', 'sample_id')) or
            type(header['timestamp']) is not int or not 0 <= header['timestamp'] < 2**63 or
            header['frame_id'] != 'radar' or header['source_type'] != 'derived'):
        raise ValueError('invalid bundle identity or reference frame')
    if (context['source_frame_id'] != header['frame_id'] or
            context['mapping_frame_id'] != 'odom' or
            context['reference_timestamp'] != header['timestamp'] or
            context['clock_id'] != header['clock_id'] or
            not isinstance(context['calibration_id'], str) or
            not context['calibration_id'].strip()):
        raise ValueError('bundle context frame, time or calibration mismatch')
    for key in ('T_mapping_source', 'T_mapping_body'):
        status = context[key + '_status']
        if status == 'available':
            validate_transform(context[key])
        elif status != 'unavailable':
            raise ValueError('unknown transform status')


def validate_bundle(bundle, max_delta_ns=5_000_000, max_pose_age_ns=10_000_000):
    """校验已声明的内部关系；调用者先用validate_context划分错误出口。"""
    header = bundle['header']
    for key, frame in (('radar', 'radar'), ('infrared', 'thermal_optical'), ('state', 'odom')):
        inner = bundle[key]['header']
        if any(inner[field] != header[field] for field in ('run_id', 'clock_id')):
            raise ValueError(key + ' run or clock mismatch')
        if inner['frame_id'] != frame:
            raise ValueError(key + ' frame mismatch')
        if header['status'] == 'valid' and inner['status'] != 'valid':
            raise ValueError(key + ' unavailable in valid bundle')
    radar_time = bundle['radar']['header']['timestamp']
    delta = abs(bundle['infrared']['header']['timestamp'] - radar_time)
    age = radar_time - bundle['state']['header']['timestamp']
    if radar_time != header['timestamp']:
        raise ValueError('bundle timestamp must use radar reference')
    if delta != bundle['radar_ir_delta_ns'] or delta > max_delta_ns:
        raise ValueError('radar infrared delta mismatch or exceeded')
    if age != bundle['pose_age_ns'] or not 0 <= age <= max_pose_age_ns:
        raise ValueError('pose age mismatch or exceeded')
    if (bundle['state']['body_frame_id'] != 'base_link' or
            bundle['context']['state_source'] != bundle['state']['state_source']):
        raise ValueError('state context mismatch')
    calibration = bundle['calibration_id']
    if (not calibration or calibration != bundle['context']['calibration_id'] or
            calibration != bundle['infrared']['camera_info']['calibration_id']):
        raise ValueError('bundle calibration references differ')
