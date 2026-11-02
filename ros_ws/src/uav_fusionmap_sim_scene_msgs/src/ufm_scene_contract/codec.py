"""Strict generated-message adapters with bounded scanning before genpy decoding."""
import io
import math
import re
import struct

from . import contract as c

SCALARS = dict(uint8='B', bool='B', int64='q', uint64='Q', float32='f', float64='d')


def _class(name):
    if '/' in name:
        package, name = name.split('/')
        if package == 'uav_fusionmap_msgs':
            from uav_fusionmap_msgs import msg
            return getattr(msg, name)
        if package != 'uav_fusionmap_sim_scene_msgs':
            raise ValueError('scene_wire_package')
    if name in ('SceneStepRequest', 'SceneStepResponse'):
        from uav_fusionmap_sim_scene_msgs import srv
        return getattr(srv, name)
    from uav_fusionmap_sim_scene_msgs import msg
    return getattr(msg, name)


def _zero(kind):
    match = re.fullmatch(r'(.+)\[(\d*)\]', kind)
    if match:
        base, count = match.groups()
        return [_zero(base) for _ in range(int(count) if count else 0)]
    if '/' in kind:
        return _empty(kind)
    return '' if kind == 'string' else False if kind == 'bool' else 0


def _empty(name):
    result = _class(name)()
    for field, kind in zip(result.__slots__, result._slot_types):
        setattr(result, field, _zero(kind))
    return result


def _wire_check(kind, value, field=''):
    match = re.fullmatch(r'(.+)\[(\d*)\]', kind)
    if match:
        base, count = match.groups()
        size = int(count) if count else 0
        if type(value) not in (list, tuple) or len(value) != size:
            raise ValueError('scene_wire_array')
        return (0 if count else 4) + sum(_wire_check(base, item, field) for item in value)
    if '/' in kind or kind in c.VALIDATORS:
        if type(value) is not _class(kind):
            raise ValueError('scene_wire_message_type')
        return sum(_wire_check(t, getattr(value, f), f) for f, t in zip(value.__slots__, value._slot_types))
    if kind == 'string':
        c.text(value, empty=True, limit=256 if field == 'reason' else 128)
        return 4 + len(value.encode('utf-8'))
    if kind == 'bool':
        if type(value) is not bool:
            raise ValueError('scene_wire_boolean')
    elif kind in ('float32', 'float64'):
        c.number(value)
        if kind == 'float32' and abs(value) > 3.4028234663852886e38:
            raise ValueError('scene_wire_float32_range')
    else:
        c.integer(value, dict(uint8=255, int64=2**63 - 1, uint64=2**64 - 1)[kind])
    return struct.calcsize('<' + SCALARS[kind])


def _encode_frame(value):
    from ufm_ros_contract.codec import to_ros_state
    result = _empty('SceneFrame')
    result.protocol_version = value['protocol_version']
    result.state = to_ros_state(value['state'])
    result.step_index = value['step_index']
    result.registration_id = value['registration_id']
    result.angular_velocity_flu = list(value['angular_velocity_flu'])
    return result


def _decode_frame(message):
    from ufm_ros_contract.codec import from_ros_state
    # The legacy decoder intentionally ignores confidence's absent numeric slot.
    if not message.state.quality.confidence_available and (message.state.quality.confidence != 0 or
            math.copysign(1., message.state.quality.confidence) < 0):
        raise ValueError('scene_absent_confidence_slot')
    return dict(protocol_version=message.protocol_version, state=from_ros_state(message.state),
        step_index=message.step_index, registration_id=message.registration_id,
        angular_velocity_flu=list(message.angular_velocity_flu))


def to_ros(name, value, **bindings):
    if name not in c.VALIDATORS:
        raise ValueError('scene_message_kind')
    c.VALIDATORS[name](value, **bindings)
    if name == 'SceneFrame':
        result = _encode_frame(value)
    elif name == 'SceneStepRequest':
        result = _empty(name)
        result.frame = _encode_frame(value['frame'])
    elif name == 'SceneCaptureAck':
        result = _empty(name)
        for key, item in value.items():
            setattr(result, key, item)
    else:
        result = _empty(name)
        result.accepted, result.reason = value['accepted'], value['reason']
        result.has_applied_frame = value['applied_frame'] is not None
        if result.has_applied_frame:
            result.applied_frame = _encode_frame(value['applied_frame'])
        for prefix in ('radar', 'infrared'):
            stamp = value[prefix + '_timestamp']
            setattr(result, prefix + '_captured', stamp is not None)
            setattr(result, prefix + '_timestamp', 0 if stamp is None else stamp)
    if _wire_check(name, result) > c.WIRE_BYTES:
        raise ValueError('scene_wire_size')
    return result


def from_ros(name, message, **bindings):
    try:
        if _wire_check(name, message) > c.WIRE_BYTES:
            raise ValueError('scene_wire_size')
        if name == 'SceneFrame':
            value = _decode_frame(message)
        elif name == 'SceneStepRequest':
            value = dict(frame=_decode_frame(message.frame))
        elif name == 'SceneCaptureAck':
            value = {key: getattr(message, key) for key in message.__slots__}
        else:
            if not message.has_applied_frame:
                actual, empty = io.BytesIO(), io.BytesIO()
                message.applied_frame.serialize(actual)
                _empty('SceneFrame').serialize(empty)
                if actual.getvalue() != empty.getvalue():
                    raise ValueError('scene_absent_frame_slots')
            value = dict(accepted=message.accepted, reason=message.reason,
                         applied_frame=_decode_frame(message.applied_frame) if message.has_applied_frame else None)
            for prefix in ('radar', 'infrared'):
                stamp = getattr(message, prefix + '_timestamp')
                flag = getattr(message, prefix + '_captured')
                if not flag and stamp != 0:
                    raise ValueError('scene_absent_capture_slot')
                value[prefix + '_timestamp'] = stamp if flag else None
        c.VALIDATORS[name](value, **bindings)
        return value
    except (AttributeError, TypeError, KeyError, OverflowError) as exc:
        raise ValueError('scene_wire_fields') from exc


def serialize(name, value, **bindings):
    stream = io.BytesIO()
    to_ros(name, value, **bindings).serialize(stream)
    return stream.getvalue()


def _scan(kind, raw, offset, field=''):
    """Reject oversized strings/arrays, noncanonical bools and tails before allocation."""
    match = re.fullmatch(r'(.+)\[(\d*)\]', kind)
    if match:
        base, count = match.groups()
        if count:
            size = int(count)
        else:
            size = struct.unpack_from('<I', raw, offset)[0]
            offset += 4
            if size != 0:  # This profile has unavailable uncertainty, so its value array is empty.
                raise ValueError('scene_wire_variable_array')
        for _ in range(size):
            offset = _scan(base, raw, offset, field)
        return offset
    if '/' in kind or kind in c.VALIDATORS:
        cls = _class(kind)
        for name, slot in zip(cls.__slots__, cls._slot_types):
            offset = _scan(slot, raw, offset, name)
        return offset
    if kind == 'string':
        size = struct.unpack_from('<I', raw, offset)[0]
        limit = 256 if field == 'reason' else 128
        if size > limit or offset + 4 + size > len(raw):
            raise ValueError('scene_wire_text_length')
        c.text(raw[offset + 4:offset + 4 + size].decode('utf-8'), empty=True, limit=limit)
        return offset + 4 + size
    item = struct.unpack_from('<' + SCALARS[kind], raw, offset)[0]
    if kind == 'bool':
        if item not in (0, 1):
            raise ValueError('scene_wire_boolean_byte')
    elif kind in ('float32', 'float64'):
        c.number(item)
    elif item < 0:
        raise ValueError('scene_wire_negative_integer')
    return offset + struct.calcsize('<' + SCALARS[kind])


def deserialize(name, payload, **bindings):
    if name not in c.VALIDATORS or type(payload) is not bytes or len(payload) > c.WIRE_BYTES:
        raise ValueError('scene_wire_input_limit')
    try:
        if _scan(name, payload, 0) != len(payload):
            raise ValueError('scene_wire_trailing_bytes')
        message = _class(name)().deserialize(payload)
    except (struct.error, UnicodeError) as exc:
        raise ValueError('scene_wire_truncated_or_encoding') from exc
    value = from_ros(name, message, **bindings)
    stream = io.BytesIO()
    message.serialize(stream)
    if stream.getvalue() != payload:
        raise ValueError('scene_wire_noncanonical')
    return value
