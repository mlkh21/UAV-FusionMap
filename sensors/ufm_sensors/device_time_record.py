"""Auditable envelopes for decoded ARS548 and Mid-360 device records.

The envelope keeps device acquisition time separate from host receipt time.
It deliberately leaves cross-clock mapping unverified until hardware records
are available.
"""
import json

from .device_time_adapter import adapt_ars548_detection_list, adapt_mid360_custom_msg


_RECORD_SCHEMA = 'device_time_record_v1'
_RECORD_KINDS = {
    'ars548_detection_list': 'Continental ARS548',
    'mid360_custom_msg': 'Livox Mid-360',
}
_MID360_TIME_TYPES = {0: 'device_boot', 1: 'ptp_or_gptp', 2: 'gps'}
_MID360_RAW_TIME_TRANSPORTS = {
    'raw_packet',
    'ros_custom_msg_plus_raw_packet_metadata',
}


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name + ' must be a non-empty string')
    return value


def _timestamp(value, name):
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError(name + ' must be a non-negative int64 timestamp')
    return value


def _device_timestamp(value, name):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError(name + ' must be a non-negative uint64 timestamp')
    return value


def _uint(value, maximum, name):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(name + ' must be an unsigned integer')
    return value


def _identity(record):
    return {key: _text(record.get(key), key)
            for key in ('run_id', 'clock_id', 'sample_id', 'frame_id')}


def _validate_payload(record_kind, payload):
    if not isinstance(payload, dict):
        raise ValueError('device payload must be a mapping')
    if payload.get('schema_version') != 'device_time_v1':
        raise ValueError('unsupported device payload schema')
    if payload.get('device_model') != _RECORD_KINDS[record_kind]:
        raise ValueError('device model and record kind mismatch')
    for key in ('run_id', 'clock_id', 'sample_id', 'frame_id'):
        _text(payload.get(key), 'payload.' + key)
    _device_timestamp(payload.get('observation_timestamp_ns'),
                      'payload.observation_timestamp_ns')

    if record_kind == 'ars548_detection_list':
        if payload.get('device_kind') != 'radar_online_candidate':
            raise ValueError('ARS548 device kind mismatch')
        if payload.get('point_time_available') is not False:
            raise ValueError('ARS548 point time must remain unavailable')
        if payload.get('scan_start_ns') is not None or payload.get('scan_end_ns') is not None:
            raise ValueError('ARS548 scan bounds cannot be invented')
        if payload.get('time_sync_verified') is not False:
            raise ValueError('ARS548 sync verification must remain false')
        if payload.get('time_type_provenance') != 'detection_list':
            raise ValueError('ARS548 time provenance mismatch')
        if (payload.get('time_source') != 'ars548_device_timestamp_status_unmapped'
                or payload.get('time_sync_source_present') is not None
                or payload.get('point_time_semantics') != 'detection_list_timestamp_only'):
            raise ValueError('ARS548 time source or point time semantics mismatch')
        seconds = _uint(payload.get('timestamp_seconds'), 2**32 - 1,
                        'ARS548 timestamp_seconds')
        nanoseconds = _uint(payload.get('timestamp_nanoseconds'),
                            999_999_999, 'ARS548 timestamp_nanoseconds')
        _uint(payload.get('timestamp_syncstatus'), 255,
              'ARS548 timestamp_syncstatus')
        count = _uint(payload.get('detection_count'), 800,
                      'ARS548 detection_count')
        if (payload['observation_timestamp_ns'] != seconds * 1_000_000_000 + nanoseconds
                or not isinstance(payload.get('points'), list)
                or count != len(payload['points'])):
            raise ValueError('ARS548 timestamp or detection count mismatch')
        if not isinstance(payload.get('points'), list):
            raise ValueError('ARS548 points must be a list')
        for index, point in enumerate(payload['points']):
            if (not isinstance(point, dict)
                    or point.get('index') != index
                    or point.get('point_time_ns') is not None
                    or point.get('point_time_offset_ns') is not None):
                raise ValueError('ARS548 per-detection time must be unavailable')
        return

    if payload.get('device_kind') != 'lidar_training_supervision_only':
        raise ValueError('Mid-360 device kind mismatch')
    if payload.get('point_time_available') is not True:
        raise ValueError('Mid-360 point time must be available')
    if payload.get('time_sync_verified') is not False:
        raise ValueError('Mid-360 sync verification must remain false')
    provenance = payload.get('time_type_provenance')
    time_type = payload.get('time_type')
    if provenance == 'raw_packet':
        if type(time_type) is not int or time_type not in _MID360_TIME_TYPES:
            raise ValueError('Mid-360 raw time type missing or invalid')
    elif provenance == 'unavailable_in_custom_msg':
        if time_type is not None:
            raise ValueError('Mid-360 CustomMsg cannot carry a time type')
    else:
        raise ValueError('unsupported Mid-360 time type provenance')
    expected_source_present = (None if time_type is None
                               else time_type in (1, 2))
    if payload.get('time_sync_source_present') != expected_source_present:
        raise ValueError('Mid-360 sync source flag mismatch')
    expected_source = ('unspecified' if time_type is None
                       else _MID360_TIME_TYPES[time_type])
    if (payload.get('time_source') != expected_source
            or payload.get('point_time_semantics') != 'timebase_plus_offset_time_ns'):
        raise ValueError('Mid-360 time source or point time semantics mismatch')
    point_count = _uint(payload.get('point_count'), 2**32 - 1,
                        'Mid-360 point_count')
    points = payload.get('points')
    if not isinstance(points, list) or point_count != len(points):
        raise ValueError('Mid-360 points must be a list')
    prior_offset = None
    for index, point in enumerate(points):
        if not isinstance(point, dict):
            raise ValueError('Mid-360 point must be a mapping')
        offset = point.get('offset_time_ns')
        point_time = point.get('point_time_ns')
        if (type(offset) is not int or not 0 <= offset <= 2**32 - 1
                or type(point_time) is not int
                or not 0 <= point_time < 2**64
                or point.get('index') != index
                or point_time != payload['observation_timestamp_ns'] + offset):
            raise ValueError('Mid-360 point time expansion invalid')
        if prior_offset is not None and offset < prior_offset:
            raise ValueError('Mid-360 point times are unordered')
        prior_offset = offset
    expected_end = (points[-1]['point_time_ns']
                    if points else payload['observation_timestamp_ns'])
    if (payload.get('scan_start_ns') != payload['observation_timestamp_ns']
            or payload.get('scan_end_ns') != expected_end):
        raise ValueError('Mid-360 scan bounds mismatch')


def validate_device_time_record(record):
    """Validate one JSON-ready device record without estimating clock mapping."""
    if not isinstance(record, dict):
        raise ValueError('device time record must be a mapping')
    if record.get('schema_version') != _RECORD_SCHEMA:
        raise ValueError('unsupported device time record schema')
    record_kind = record.get('record_kind')
    if record_kind not in _RECORD_KINDS:
        raise ValueError('unsupported device time record kind')
    identity = _identity(record)
    if record.get('device_model') != _RECORD_KINDS[record_kind]:
        raise ValueError('device model and record kind mismatch')
    if record.get('record_source') != 'decoded_device_record':
        raise ValueError('unsupported device record source')
    _text(record.get('transport'), 'transport')
    _timestamp(record.get('receive_timestamp_ns'), 'receive_timestamp_ns')
    _text(record.get('receive_clock_id'), 'receive_clock_id')
    if record.get('time_mapping_status') != 'unmapped':
        raise ValueError('device clock mapping must remain unmapped')
    for key in ('time_mapping_offset_ns', 'time_mapping_drift_ppb',
                'time_sync_error_bound_ns'):
        if record.get(key) is not None:
            raise ValueError(key + ' requires a separately verified clock mapping')

    payload = record.get('payload')
    _validate_payload(record_kind, payload)
    for key in ('run_id', 'clock_id', 'sample_id', 'frame_id'):
        if identity[key] != payload[key]:
            raise ValueError('record and payload identity mismatch')
    if record.get('device_timestamp_ns') != payload['observation_timestamp_ns']:
        raise ValueError('device timestamp does not match payload')
    if record.get('time_sync_verified') is not False:
        raise ValueError('clock synchronization must remain unverified')
    if (record_kind == 'mid360_custom_msg'
            and payload['time_type_provenance'] == 'raw_packet'
            and record['transport'] not in _MID360_RAW_TIME_TRANSPORTS):
        raise ValueError('raw Mid-360 time type needs raw packet provenance')
    try:
        json.dumps(record, allow_nan=False, separators=(',', ':'))
    except (TypeError, ValueError) as error:
        raise ValueError('device time record is not finite JSON data') from error
    return True


def _wrap(record_kind, payload, receive_timestamp_ns, receive_clock_id, transport):
    _validate_payload(record_kind, payload)
    record = dict(
        schema_version=_RECORD_SCHEMA,
        record_kind=record_kind,
        record_source='decoded_device_record',
        device_model=payload['device_model'],
        run_id=payload['run_id'],
        clock_id=payload['clock_id'],
        sample_id=payload['sample_id'],
        frame_id=payload['frame_id'],
        device_timestamp_ns=payload['observation_timestamp_ns'],
        receive_timestamp_ns=receive_timestamp_ns,
        receive_clock_id=receive_clock_id,
        transport=transport,
        time_mapping_status='unmapped',
        time_mapping_offset_ns=None,
        time_mapping_drift_ppb=None,
        time_sync_error_bound_ns=None,
        time_sync_verified=False,
        payload=payload,
    )
    validate_device_time_record(record)
    return record


def make_ars548_record(message, identity, receive_timestamp_ns,
                       receive_clock_id, transport='ros_detection_list'):
    """Build an ARS548 record with separate device and host timestamps."""
    return _wrap('ars548_detection_list',
                 adapt_ars548_detection_list(message, identity),
                 receive_timestamp_ns, receive_clock_id, transport)


def make_mid360_record(frame, identity, receive_timestamp_ns,
                       receive_clock_id, packet_time_type=None,
                       transport='ros_custom_msg'):
    """Build a Mid-360 record; raw time type requires explicit provenance."""
    payload = adapt_mid360_custom_msg(frame, identity, packet_time_type)
    return _wrap('mid360_custom_msg', payload, receive_timestamp_ns,
                 receive_clock_id, transport)


def validate_device_time_stream(records):
    """Validate a single-device stream; allow packet reordering, reject identity reuse."""
    if not isinstance(records, list) or not records:
        raise ValueError('device time stream must be a non-empty list')
    seen = set()
    first = None
    for record in records:
        validate_device_time_record(record)
        identity = (record['record_kind'], record['device_model'],
                    record['run_id'], record['clock_id'], record['receive_clock_id'],
                    record['frame_id'])
        if first is None:
            first = identity
        elif identity != first:
            raise ValueError('device time stream mixes device or clock identities')
        if record['sample_id'] in seen:
            raise ValueError('device time stream contains duplicate sample_id')
        seen.add(record['sample_id'])
    return True
