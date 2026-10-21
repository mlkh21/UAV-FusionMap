"""Device-specific time contracts for ARS548 and Livox Mid-360.

This module adapts decoded device records only. It does not estimate a
cross-device clock offset and does not publish an online SensorBundle.
"""
import math


_MID360_TIME_TYPES = {
    0: ('device_boot', False),
    1: ('ptp_or_gptp', True),
    2: ('gps', True),
}


def _uint(value, maximum, name):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(name + ' must be an unsigned integer')
    return value


def _optional_uint8(value, name):
    if value is None:
        return None
    return _uint(value, 255, name)


def _identity(identity):
    if not isinstance(identity, dict):
        raise ValueError('device acquisition identity required')
    required = ('run_id', 'clock_id', 'sample_id', 'frame_id')
    if any(not isinstance(identity.get(key), str) or not identity[key].strip()
           for key in required):
        raise ValueError('device acquisition identity incomplete')
    return {key: identity[key] for key in required}


def _record(value, name):
    if isinstance(value, dict):
        return value
    slots = getattr(type(value), '__slots__', ())
    if slots:
        return {key: getattr(value, key) for key in slots}
    raise ValueError(name + ' must be a mapping or slotted ROS message')


def adapt_mid360_custom_msg(frame, identity, packet_time_type=None):
    """Expand CustomMsg times; packet_time_type requires raw-driver metadata."""
    identity = _identity(identity)
    frame = _record(frame, 'Mid-360 CustomMsg')
    timebase = _uint(frame.get('timebase'), 2**64 - 1, 'timebase')
    if packet_time_type is not None:
        packet_time_type = _uint(packet_time_type, 2, 'packet_time_type')
        if packet_time_type not in _MID360_TIME_TYPES:
            raise ValueError('unsupported Mid-360 timestamp type')
    points = frame.get('points')
    point_num = _uint(frame.get('point_num'), 2**32 - 1, 'point_num')
    if not isinstance(points, list) or point_num != len(points):
        raise ValueError('Mid-360 point count mismatch')

    time_source, sync_source_present = (_MID360_TIME_TYPES[packet_time_type]
                                        if packet_time_type is not None
                                        else ('unspecified', None))
    output_points = []
    prior_offset = None
    for index, point in enumerate(points):
        point = _record(point, 'Mid-360 point')
        offset = _uint(point.get('offset_time'), 2**32 - 1, 'offset_time')
        if prior_offset is not None and offset < prior_offset:
            raise ValueError('Mid-360 point offsets must be ordered')
        if any(not isinstance(point.get(axis), (int, float))
               or isinstance(point.get(axis), bool)
               or not math.isfinite(point[axis]) for axis in ('x', 'y', 'z')):
            raise ValueError('Mid-360 point coordinates invalid')
        point_time = timebase + offset
        if point_time > 2**64 - 1:
            raise ValueError('Mid-360 point timestamp overflow')
        output_points.append(dict(
            index=index,
            point_time_ns=point_time,
            offset_time_ns=offset,
            x=float(point['x']),
            y=float(point['y']),
            z=float(point['z']),
            reflectivity=_optional_uint8(point.get('reflectivity'),
                                         'reflectivity'),
            tag=_optional_uint8(point.get('tag'), 'tag'),
            line=_optional_uint8(point.get('line'), 'line'),
        ))
        prior_offset = offset

    end_time = output_points[-1]['point_time_ns'] if output_points else timebase
    return dict(
        schema_version='device_time_v1',
        device_model='Livox Mid-360',
        device_kind='lidar_training_supervision_only',
        run_id=identity['run_id'],
        clock_id=identity['clock_id'],
        sample_id=identity['sample_id'],
        frame_id=identity['frame_id'],
        observation_timestamp_ns=timebase,
        scan_start_ns=timebase,
        scan_end_ns=end_time,
        point_count=point_num,
        point_time_available=True,
        point_time_semantics='timebase_plus_offset_time_ns',
        time_type=packet_time_type,
        time_type_provenance=('raw_packet' if packet_time_type is not None
                              else 'unavailable_in_custom_msg'),
        time_source=time_source,
        time_sync_source_present=sync_source_present,
        time_sync_verified=False,
        points=output_points,
    )


def adapt_ars548_detection_list(message, identity):
    """Adapt an ARS548 DetectionList without inventing per-detection time."""
    identity = _identity(identity)
    message = _record(message, 'ARS548 DetectionList')
    seconds = _uint(message.get('timestamp_seconds'), 2**32 - 1,
                    'timestamp_seconds')
    nanoseconds = _uint(message.get('timestamp_nanoseconds'), 2**32 - 1,
                        'timestamp_nanoseconds')
    if nanoseconds >= 1_000_000_000:
        raise ValueError('ARS548 timestamp nanoseconds out of range')
    sync_status = _uint(message.get('timestamp_syncstatus'), 255,
                        'timestamp_syncstatus')
    detections = message.get('list_detections')
    count = _uint(message.get('list_numofdetections'), 800,
                  'list_numofdetections')
    if not isinstance(detections, list) or count > len(detections):
        raise ValueError('ARS548 detection count mismatch')

    timestamp = seconds * 1_000_000_000 + nanoseconds
    output_points = []
    for index, detection in enumerate(detections[:count]):
        detection = _record(detection, 'ARS548 detection')
        output_points.append(dict(
            index=index,
            detection=dict(detection),
            point_time_ns=None,
            point_time_offset_ns=None,
        ))

    return dict(
        schema_version='device_time_v1',
        device_model='Continental ARS548',
        device_kind='radar_online_candidate',
        run_id=identity['run_id'],
        clock_id=identity['clock_id'],
        sample_id=identity['sample_id'],
        frame_id=identity['frame_id'],
        observation_timestamp_ns=timestamp,
        scan_start_ns=None,
        scan_end_ns=None,
        point_time_available=False,
        point_time_semantics='detection_list_timestamp_only',
        timestamp_seconds=seconds,
        timestamp_nanoseconds=nanoseconds,
        timestamp_syncstatus=sync_status,
        detection_count=count,
        time_source='ars548_device_timestamp_status_unmapped',
        time_sync_source_present=None,
        time_type_provenance='detection_list',
        time_sync_verified=False,
        points=output_points,
    )
