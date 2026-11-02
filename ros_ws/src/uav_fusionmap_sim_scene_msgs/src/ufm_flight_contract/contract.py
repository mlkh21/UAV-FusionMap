"""Flight v2 semantics over unchanged Scene message layouts, without runtime state."""
import math

from ufm_scene_contract.contract import (domain, fields, integer, number, reason, text, vector)

PROTOCOL_VERSION = 2
STEP_NS = 4_000_000
MAX_STEPS = 10_000
CAPTURE_AFTER_STEP = 7_500
CAPTURE_STEPS = 25
WIRE_BYTES = 4096
REGISTRATION = 'jsbsim_cg_to_flight_enu_v1'
ANCHOR_M = (0., 0., .5)
MIN_Z_M = .2
MAX_ANCHOR_DISTANCE_M = 250.
QUALITY_SOURCE = 'jsbsim_scene_truth_no_covariance_v1'


def capture_step(index):
    integer(index, MAX_STEPS)
    return index > CAPTURE_AFTER_STEP and index % CAPTURE_STEPS == 0


def _version(value):
    if type(value) is not int or value != PROTOCOL_VERSION:
        raise ValueError('flight_version')


def validate_frame(value):
    fields(value, 'protocol_version state step_index registration_id angular_velocity_flu')
    _version(value['protocol_version'])
    integer(value['step_index'], MAX_STEPS)
    if value['registration_id'] != REGISTRATION:
        raise ValueError('flight_registration')
    text(value['registration_id'])
    vector(value['angular_velocity_flu'], 3)
    state = value['state']
    fields(state, 'header position orientation_xyzw linear_velocity body_frame_id velocity_frame_id state_source quality')
    h = state['header']
    fields(h, 'schema_version run_id clock_id timestamp sample_id frame_id source_type status reason')
    domain(h['run_id'], h['clock_id'])
    for key in ('schema_version', 'sample_id', 'frame_id', 'source_type', 'status'):
        text(h[key])
    integer(h['timestamp'], MAX_STEPS * STEP_NS)
    reason(h['reason'], True)
    if (h['schema_version'] != '0.1' or h['frame_id'] != 'scene_world' or
            h['source_type'] != 'simulation' or h['status'] != 'valid' or
            h['sample_id'] != 'scene.frame:%s:%d' % (h['run_id'], value['step_index']) or
            h['timestamp'] != value['step_index'] * STEP_NS):
        raise ValueError('flight_header_or_time')
    for key in ('body_frame_id', 'velocity_frame_id', 'state_source'):
        text(state[key])
    if (state['body_frame_id'], state['velocity_frame_id'], state['state_source']) != (
            'base_link', 'base_link', 'ground_truth'):
        raise ValueError('flight_state_domain')
    for key, size in (('position', 3), ('orientation_xyzw', 4), ('linear_velocity', 3)):
        vector(state[key], size)
    if abs(math.hypot(*state['orientation_xyzw']) - 1.) > .001:
        raise ValueError('flight_quaternion')
    position = state['position']
    if (position[2] <= MIN_Z_M or
            math.hypot(*(v - a for v, a in zip(position, ANCHOR_M))) > MAX_ANCHOR_DISTANCE_M):
        raise ValueError('flight_geometry_bound')
    if value['step_index'] == 0 and tuple(position) != ANCHOR_M:
        raise ValueError('flight_initial_anchor')
    quality = state['quality']
    fields(quality, 'confidence uncertainty')
    if quality['confidence'] is not None:
        raise ValueError('flight_uncalibrated_confidence')
    u = quality['uncertainty']
    fields(u, 'status kind value unit source')
    if u != dict(status='unavailable', kind='', value=None, unit='', source=QUALITY_SOURCE):
        raise ValueError('flight_uncalibrated_quality')


def validate_request(value):
    fields(value, 'frame')
    validate_frame(value['frame'])


def validate_ack(value, frame=None):
    fields(value, 'protocol_version run_id clock_id step_index measurement_timestamp sensor_kind published reason')
    _version(value['protocol_version'])
    domain(value['run_id'], value['clock_id'])
    integer(value['step_index'], MAX_STEPS)
    integer(value['measurement_timestamp'], MAX_STEPS * STEP_NS)
    if not capture_step(value['step_index']):
        raise ValueError('flight_ack_outside_capture')
    if type(value['sensor_kind']) is not int or value['sensor_kind'] not in (1, 2):
        raise ValueError('flight_ack_sensor_kind')
    if type(value['published']) is not bool:
        raise ValueError('flight_ack_boolean')
    reason(value['reason'], value['published'])
    if value['measurement_timestamp'] != value['step_index'] * STEP_NS:
        raise ValueError('flight_ack_capture_time')
    if frame is not None:
        validate_frame(frame)
        h = frame['state']['header']
        if (any(value[key] != h[key] for key in ('run_id', 'clock_id')) or
                value['step_index'] != frame['step_index']):
            raise ValueError('flight_ack_binding')


def _bound_applied(applied, wanted):
    a, b = applied['state'], wanted['state']
    if (any(applied[k] != wanted[k] for k in ('protocol_version', 'step_index', 'registration_id')) or
            any(a[k] != b[k] for k in ('header', 'body_frame_id', 'velocity_frame_id', 'state_source', 'quality'))):
        raise ValueError('flight_response_binding')
    for x, y in ((a['position'], b['position']), (a['linear_velocity'], b['linear_velocity']),
                 (applied['angular_velocity_flu'], wanted['angular_velocity_flu'])):
        if any(abs(v - w) > 1e-9 for v, w in zip(x, y)):
            raise ValueError('flight_applied_geometry')
    q, r = a['orientation_xyzw'], b['orientation_xyzw']
    if min(max(abs(v - w) for v, w in zip(q, r)), max(abs(v + w) for v, w in zip(q, r))) > 1e-12:
        raise ValueError('flight_applied_orientation')


def validate_response(value, request=None):
    fields(value, 'accepted reason applied_frame radar_timestamp infrared_timestamp')
    if type(value['accepted']) is not bool:
        raise ValueError('flight_response_boolean')
    reason(value['reason'], value['accepted'])
    applied = value['applied_frame']
    # SceneStepResponse has no outer version. A real applied frame is its v2 witness.
    if applied is None:
        raise ValueError('flight_response_requires_versioned_applied_frame')
    validate_frame(applied)
    expected = applied['step_index'] * STEP_NS if capture_step(applied['step_index']) else None
    times = [value['radar_timestamp'], value['infrared_timestamp']]
    for stamp in times:
        if stamp is not None:
            integer(stamp, MAX_STEPS * STEP_NS)
            if expected is None or stamp != expected:
                raise ValueError('flight_response_capture_time')
    if value['accepted'] and times != [expected, expected]:
        raise ValueError('flight_response_missing_capture')
    if request is not None:
        validate_request(request)
        _bound_applied(applied, request['frame'])


VALIDATORS = dict(SceneFrame=validate_frame, SceneCaptureAck=validate_ack,
                  SceneStepRequest=validate_request, SceneStepResponse=validate_response)
