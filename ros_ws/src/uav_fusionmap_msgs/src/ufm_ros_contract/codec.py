"""AircraftState逻辑字典与ROS消息往返；时间不经浮点转换。"""
import math
from numbers import Real

from uav_fusionmap_msgs.msg import AircraftState

SOURCE = {'simulation': 0, 'measured': 1, 'fixture': 2, 'model': 3, 'derived': 4}
STATUS = {'valid': 0, 'degraded': 1, 'unavailable': 2}
STATE_SOURCE = {'ground_truth': 0, 'estimated': 1}
UNCERTAINTY = {'unavailable': 0, 'available': 1}
HEADER_TEXT = ('schema_version', 'clock_id', 'run_id', 'sample_id', 'frame_id', 'reason')


def _text(value, name, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(name + '必须为有效字符串')
    return value


def _encode(value, mapping, name):
    if not isinstance(value, str) or value not in mapping:
        raise ValueError(name + '枚举未知')
    return mapping[value]


def _decode(value, mapping, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(name + '枚举类型错误')
    for key, number in mapping.items():
        if value == number:
            return key
    raise ValueError(name + '枚举未知')


def _vector(value, size, name, finite=True):
    if not isinstance(value, (list, tuple)) or (size is not None and len(value) != size):
        raise ValueError(name + '维度错误')
    if any(isinstance(v, bool) or not isinstance(v, Real) for v in value):
        raise ValueError(name + '必须为数值数组')
    result = [float(v) for v in value]
    if finite and not all(math.isfinite(v) for v in result):
        raise ValueError(name + '含非有限数')
    return result


def to_ros_state(state):
    """验证逻辑契约并编码；失败抛ValueError，不修正采样时间或姿态。"""
    try:
        return _to_ros_state(state)
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('AircraftState字段缺失或类型错误: ' + str(exc)) from exc


def _to_ros_state(state):
    msg = AircraftState()
    header = state['header']
    for key in HEADER_TEXT:
        setattr(msg.header, key, _text(header[key], key, allow_empty=(key == 'reason')))
    if header['schema_version'] != '0.1':
        raise ValueError('schema_version不支持')
    timestamp = header['timestamp']
    if type(timestamp) is not int or not 0 <= timestamp <= 2**63 - 1:
        raise ValueError('timestamp必须为非负int64纳秒')
    msg.header.timestamp = timestamp
    msg.header.source_type = _encode(header['source_type'], SOURCE, 'source_type')
    msg.header.status = _encode(header['status'], STATUS, 'status')
    if header['status'] != 'valid' and not header['reason'].strip():
        raise ValueError('非valid状态必须给出reason')
    geometry_valid = header['status'] != 'unavailable'
    msg.position = _vector(state['position'], 3, 'position', geometry_valid)
    msg.orientation_xyzw = _vector(state['orientation_xyzw'], 4, 'orientation_xyzw', geometry_valid)
    msg.linear_velocity = _vector(state['linear_velocity'], 3, 'linear_velocity', geometry_valid)
    if geometry_valid and abs(math.hypot(*msg.orientation_xyzw) - 1.0) > 0.001:
        raise ValueError('orientation_xyzw不是容差内单位四元数')
    msg.body_frame_id = _text(state['body_frame_id'], 'body_frame_id')
    msg.velocity_frame_id = _text(state['velocity_frame_id'], 'velocity_frame_id')
    msg.state_source = _encode(state['state_source'], STATE_SOURCE, 'state_source')
    quality = state['quality']
    confidence = quality['confidence']
    msg.quality.confidence_available = confidence is not None
    if confidence is None:
        msg.quality.confidence = 0.0  # 无效槽位；有效性只看标志。
    else:
        if isinstance(confidence, bool) or not isinstance(confidence, Real) or not 0 <= confidence <= 1:
            raise ValueError('confidence必须为[0,1]有限值或None')
        msg.quality.confidence = float(confidence)
    uncertainty = quality['uncertainty']
    out = msg.quality.uncertainty
    out.status = _encode(uncertainty['status'], UNCERTAINTY, 'uncertainty.status')
    for key in ('kind', 'unit', 'source'):
        setattr(out, key, _text(uncertainty[key], 'uncertainty.' + key,
                                allow_empty=uncertainty['status'] == 'unavailable'))
    if uncertainty['status'] == 'unavailable':
        if uncertainty['value'] is not None:
            raise ValueError('不可用uncertainty逻辑值必须为None')
        out.value = []
    else:
        # 本步没有已验收的available质量编码，拒绝未经实现的含义。
        raise ValueError('SIM-01A尚未启用available uncertainty')
    return msg


def from_ros_state(msg):
    """解码并再次按相同契约验证，恢复显式None语义。"""
    try:
        header = {key: getattr(msg.header, key) for key in HEADER_TEXT}
        header.update(timestamp=msg.header.timestamp,
                      source_type=_decode(msg.header.source_type, SOURCE, 'source_type'),
                      status=_decode(msg.header.status, STATUS, 'status'))
        quality = msg.quality
        if type(quality.confidence_available) is not bool:
            raise ValueError('confidence_available必须为bool')
        uncertainty = quality.uncertainty
        uncertainty_status = _decode(uncertainty.status, UNCERTAINTY, 'uncertainty.status')
        if uncertainty_status == 'unavailable' and len(uncertainty.value) != 0:
            raise ValueError('不可用uncertainty的ROS数组必须为空')
        state = dict(header=header, position=list(msg.position),
                     orientation_xyzw=list(msg.orientation_xyzw),
                     linear_velocity=list(msg.linear_velocity),
                     body_frame_id=msg.body_frame_id, velocity_frame_id=msg.velocity_frame_id,
                     state_source=_decode(msg.state_source, STATE_SOURCE, 'state_source'),
                     quality=dict(confidence=quality.confidence if quality.confidence_available else None,
                                  uncertainty=dict(status=uncertainty_status, kind=uncertainty.kind,
                                                   value=None if uncertainty_status == 'unavailable' else list(uncertainty.value),
                                                   unit=uncertainty.unit, source=uncertainty.source)))
        to_ros_state(state)
        return state
    except (TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('AircraftState消息类型错误: ' + str(exc)) from exc
