"""Strict codecs for generated ROS types, including canonical unavailable slots."""
import io
import re

from . import contract as c
from .bounds import MESSAGE_BYTES, REQUEST_BYTES, integer, number, text

ENUMS = {
    ('TerrainHeightQuality', 'status'): c.QUALITY_STATUS,
    ('TerrainQueryResult', 'status'): c.QUERY_STATUS,
    ('TerrainStatus', 'state'): c.STATES,
    ('TerrainStatus', 'last_install_outcome'): c.OUTCOMES,
}
VALIDATORS = dict(TerrainHeightQuality=c.validate_quality, TerrainContext=c.validate_context,
                  TerrainQueryRequest=c.validate_request, TerrainQueryResult=c.validate_result,
                  TerrainStatus=c.validate_status)


def _class(name):
    if name in ('TerrainQueryRequest', 'TerrainQueryResponse'):
        from uav_fusionmap_terrain_msgs import srv
        return getattr(srv, name)
    from uav_fusionmap_terrain_msgs import msg
    return getattr(msg, name)


def _zero(kind):
    match = re.fullmatch(r'(.+)\[(\d*)\]', kind)
    if match:
        base, count = match.groups()
        return [_zero(base) for _ in range(int(count) if count else 0)]
    if '/' in kind:
        return _empty(kind.split('/')[-1])
    return '' if kind == 'string' else False if kind == 'bool' else 0


def _empty(name):
    message = _class(name)()
    for field, kind in zip(message.__slots__, message._slot_types):
        setattr(message, field, _zero(kind))
    return message


def _wire_value(value, kind):
    match = re.fullmatch(r'(.+)\[(\d*)\]', kind)
    if match:
        base, count = match.groups()
        if type(value) not in (list, tuple) or len(value) != (int(count) if count else 0):
            raise ValueError('terrain_wire_array')
        return sum(_wire_value(x, base) for x in value) + (0 if count else 4)
    if '/' in kind:
        return _wire_size(value, kind.split('/')[-1])
    if kind == 'string':
        text(value, empty=True)
        return 4 + len(value.encode('utf-8'))
    if kind == 'bool':
        if type(value) is not bool:
            raise ValueError('terrain_wire_boolean')
        return 1
    if kind == 'float64':
        number(value)
        return 8
    widths = dict(uint8=8, uint16=16, uint32=32, uint64=64, int64=63)
    integer(value, widths[kind])
    return 8 if kind == 'int64' else widths[kind] // 8


def _wire_size(message, name):
    if type(message) is not _class(name):
        raise ValueError('terrain_wire_type')
    return sum(_wire_value(getattr(message, f), k) for f, k in zip(message.__slots__, message._slot_types))


def _raw(message):
    result = {}
    for field, kind in zip(message.__slots__, message._slot_types):
        value = getattr(message, field)
        result[field] = _raw(value) if '/' in kind else list(value) if '[' in kind else value
    return result


def _encode(name, value):
    message = _empty(name)
    for field, kind in zip(message.__slots__, message._slot_types):
        if field.endswith('_available'):
            setattr(message, field, value[field[:-10]] is not None)
            continue
        item = value[field]
        if item is None:
            continue
        enum = ENUMS.get((name, field))
        if enum is not None:
            item = enum[item]
        elif '/' in kind:
            item = _encode(kind.split('/')[-1], item)
        elif '[' in kind:
            item = list(item)
        setattr(message, field, item)
    return message


def _decode(name, message):
    result = {}
    for field, kind in zip(message.__slots__, message._slot_types):
        if field.endswith('_available'):
            continue
        value = getattr(message, field)
        flag = field + '_available'
        if flag in message.__slots__ and not getattr(message, flag):
            expected = _zero(kind)
            if '/' in kind:
                if _raw(value) != _raw(expected):
                    raise ValueError('terrain_absent_context_slots')
            elif value != expected and not ('[' in kind and list(value) == expected):
                raise ValueError('terrain_absent_numeric_slots')
            result[field] = None
            continue
        enum = ENUMS.get((name, field))
        if enum is not None:
            reverse = {v: k for k, v in enum.items()}
            if value not in reverse:
                raise ValueError('terrain_wire_enum')
            value = reverse[value]
        elif '/' in kind:
            value = _decode(kind.split('/')[-1], value)
        elif '[' in kind:
            value = list(value)
        result[field] = value
    if name == 'TerrainHeightQuality' and result['status'] == 'unavailable':
        if result['value'] != [0, 0]:
            raise ValueError('terrain_absent_quality_slots')
        result['value'] = None
    return result


def to_ros(name, value):
    """Validate a logical object before encoding a real generated ROS message."""
    VALIDATORS[name](value)
    message = _encode(name, value)
    if _wire_size(message, name) > (REQUEST_BYTES if name == 'TerrainQueryRequest' else MESSAGE_BYTES):
        raise ValueError('terrain_wire_byte_limit')
    return message


def from_ros(name, message, **bindings):
    try:
        if _wire_size(message, name) > (REQUEST_BYTES if name == 'TerrainQueryRequest' else MESSAGE_BYTES):
            raise ValueError('terrain_wire_byte_limit')
        value = _decode(name, message)
        VALIDATORS[name](value, **bindings)
    except (AttributeError, TypeError, KeyError, OverflowError) as exc:
        raise ValueError('terrain_malformed_wire_fields') from exc
    return value


def serialize(name, value):
    message, buffer = to_ros(name, value), io.BytesIO()
    message.serialize(buffer)
    return buffer.getvalue()


def deserialize(name, payload, **bindings):
    """Bound bytes before genpy allocation; reject trailing/noncanonical bool bytes."""
    limit = REQUEST_BYTES if name == 'TerrainQueryRequest' else MESSAGE_BYTES
    if type(payload) is not bytes or len(payload) > limit:
        raise ValueError('terrain_wire_input_limit')
    try:
        message = _class(name)().deserialize(payload)
    except Exception as exc:
        raise ValueError('terrain_wire_decode') from exc
    value = from_ros(name, message, **bindings)
    buffer = io.BytesIO()
    message.serialize(buffer)
    if buffer.getvalue() != payload:
        raise ValueError('terrain_wire_noncanonical')
    return value


def to_ros_response(value):
    message = _class('TerrainQueryResponse')()
    message.result = to_ros('TerrainQueryResult', value)
    return message


def from_ros_response(message, **bindings):
    if type(message) is not _class('TerrainQueryResponse'):
        raise ValueError('terrain_response_type')
    return from_ros('TerrainQueryResult', message.result, **bindings)
