"""Bounded strict JSON used by public terrain objects and recording schemas."""
import json
import math
import re

TEXT_BYTES = 16384
REQUEST_BYTES = 16384
MESSAGE_BYTES = 65536
RECORDING_BYTES = 4 * 1024 * 1024


def fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError('terrain_fields')


def text(value, empty=False, limit=TEXT_BYTES):
    if type(value) is not str or len(value) > limit:
        raise ValueError('terrain_text_limit_or_type')
    try:
        if len(value.encode('utf-8')) > limit:
            raise ValueError('terrain_text_bytes')
    except UnicodeError as exc:
        raise ValueError('terrain_text_encoding') from exc
    if not empty and not value.strip():
        raise ValueError('terrain_empty_identity')


def reason(value):
    text(value, empty=True, limit=128)
    if value and not re.fullmatch('[a-z][a-z0-9_]*', value):
        raise ValueError('terrain_reason_code')


def integer(value, bits=63):
    if type(value) is not int or not 0 <= value < 2**bits:
        raise ValueError('terrain_integer_range_or_type')


def number(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('terrain_nonfinite_or_number_type')


def array(value, length, check=number):
    if type(value) is not list or len(value) != length:
        raise ValueError('terrain_array_shape')
    for item in value:
        check(item)


def interval(value):
    array(value, 2, integer)
    if value[0] >= value[1]:
        raise ValueError('terrain_interval_order')


def bounded_json(value, limit):
    # Check depth, container counts and text before the encoder allocates chunks.
    remaining = [max(8192, min(524288, limit // 4))]

    def walk(item, depth):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 16:
            raise ValueError('terrain_structure_limit')
        if type(item) is dict:
            if len(item) > 128:
                raise ValueError('terrain_object_limit')
            for key, child in item.items():
                text(key)
                walk(child, depth + 1)
        elif type(item) is list:
            if len(item) > 64:
                raise ValueError('terrain_list_limit')
            for child in item:
                walk(child, depth + 1)
        elif type(item) is str:
            text(item, empty=True)
        elif type(item) is int:
            number(item)
        elif type(item) is float:
            number(item)
        elif item is not None and type(item) is not bool:
            raise ValueError('terrain_json_type')

    walk(value, 0)
    chunks, size = [], 0
    for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False,
                                  separators=(',', ':'), sort_keys=True).iterencode(value):
        encoded = chunk.encode('utf-8')
        size += len(encoded)
        if size > limit:
            raise ValueError('terrain_json_byte_limit')
        chunks.append(encoded)
    return b''.join(chunks)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('terrain_duplicate_key')
        result[key] = value
    return result


def _constant(_):
    raise ValueError('terrain_nonfinite_json')


def decode_json(payload, limit):
    if type(payload) is not bytes or len(payload) > limit:
        raise ValueError('terrain_json_input_limit')
    try:
        result = json.loads(payload.decode('utf-8'), object_pairs_hook=_pairs,
                            parse_constant=_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError('terrain_json_encoding') from exc
    bounded_json(result, limit)
    return result


def read_json(path, limit):
    with open(path, 'rb') as stream:
        payload = stream.read(limit + 1)
    return decode_json(payload, limit)
