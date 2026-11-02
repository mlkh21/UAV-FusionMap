"""Bounded logical objects; no ROS imports, simulator or runtime state machine."""
import math
import re

STEP_NS = 4_000_000
CAPTURE_STEPS = 25
WIRE_BYTES = 4096
REGISTRATION = 'jsbsim_cg_to_scene_enu_v1'
QUALITY_SOURCE = 'jsbsim_scene_truth_no_covariance_v1'


def fields(value, names):
    expected = names.split()
    if type(value) is not dict or len(value) != len(expected) or set(value) != set(expected):
        raise ValueError('scene_fields')


def text(value, empty=False, limit=128):
    if type(value) is not str or len(value) > limit:
        raise ValueError('scene_text_type_or_limit')
    try:
        if len(value.encode('utf-8')) > limit:
            raise ValueError('scene_text_bytes')
    except UnicodeError as exc:
        raise ValueError('scene_text_encoding') from exc
    if not empty and not value.strip() or '\0' in value:
        raise ValueError('scene_text_identity')


def integer(value, maximum=2**63 - 1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('scene_integer_range_or_type')


def number(value):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError('scene_finite_number')


def vector(value, size):
    if type(value) is not list or len(value) != size:
        raise ValueError('scene_vector_shape')
    for item in value:
        number(item)


def reason(value, success):
    text(value, empty=True, limit=256)
    if (success and value != '' or not success and not value or
            value and re.fullmatch('[a-z][a-z0-9_]*', value) is None):
        raise ValueError('scene_reason')


def domain(run_id, clock_id):
    text(run_id)
    text(clock_id)
    if clock_id != 'sim:' + run_id:
        raise ValueError('scene_clock_domain')


def capture_step(index):
    return index > 0 and index % CAPTURE_STEPS == 0


def validate_frame(value):
    fields(value, 'protocol_version state step_index registration_id angular_velocity_flu')
    if type(value['protocol_version']) is not int or value['protocol_version'] != 1:
        raise ValueError('scene_version')
    integer(value['step_index'], (2**63 - 1) // STEP_NS)
    text(value['registration_id'])
    if value['registration_id'] != REGISTRATION:
        raise ValueError('scene_registration')
    vector(value['angular_velocity_flu'], 3)
    state = value['state']
    fields(state, 'header position orientation_xyzw linear_velocity body_frame_id velocity_frame_id state_source quality')
    h = state['header']
    fields(h, 'schema_version run_id clock_id timestamp sample_id frame_id source_type status reason')
    domain(h['run_id'], h['clock_id'])
    for key in ('schema_version', 'sample_id', 'frame_id', 'source_type', 'status'):
        text(h[key])
    integer(h['timestamp'])
    reason(h['reason'], True)
    if (h['schema_version'] != '0.1' or h['frame_id'] != 'scene_world' or
            h['source_type'] != 'simulation' or h['status'] != 'valid' or
            h['sample_id'] != 'scene.frame:%s:%d' % (h['run_id'], value['step_index']) or
            h['timestamp'] != value['step_index'] * STEP_NS):
        raise ValueError('scene_header_or_time')
    for key in ('body_frame_id', 'velocity_frame_id', 'state_source'):
        text(state[key])
    if (state['body_frame_id'], state['velocity_frame_id'], state['state_source']) != (
            'base_link', 'base_link', 'ground_truth'):
        raise ValueError('scene_state_domain')
    for key, size in (('position', 3), ('orientation_xyzw', 4), ('linear_velocity', 3)):
        vector(state[key], size)
    if abs(math.hypot(*state['orientation_xyzw']) - 1.) > .001:
        raise ValueError('scene_quaternion')
    quality = state['quality']
    fields(quality, 'confidence uncertainty')
    if quality['confidence'] is not None:
        raise ValueError('scene_uncalibrated_confidence')
    u = quality['uncertainty']
    fields(u, 'status kind value unit source')
    if u != dict(status='unavailable', kind='', value=None, unit='', source=QUALITY_SOURCE):
        raise ValueError('scene_uncalibrated_quality')


def validate_request(value):
    fields(value, 'frame')
    validate_frame(value['frame'])


def validate_ack(value, frame=None):
    fields(value, 'protocol_version run_id clock_id step_index measurement_timestamp sensor_kind published reason')
    if type(value['protocol_version']) is not int or value['protocol_version'] != 1:
        raise ValueError('scene_version')
    domain(value['run_id'], value['clock_id'])
    integer(value['step_index'], (2**63 - 1) // STEP_NS)
    integer(value['measurement_timestamp'])
    if value['step_index'] == 0 or type(value['sensor_kind']) is not int or value['sensor_kind'] not in (1, 2):
        raise ValueError('scene_ack_kind_or_step')
    if type(value['published']) is not bool:
        raise ValueError('scene_ack_boolean')
    reason(value['reason'], value['published'])
    if value['published'] and (not capture_step(value['step_index']) or
            value['measurement_timestamp'] != value['step_index'] * STEP_NS):
        raise ValueError('scene_ack_capture_time')
    if frame is not None:
        validate_frame(frame)
        h = frame['state']['header']
        if any(value[key] != h[key] for key in ('run_id', 'clock_id')) or value['step_index'] != frame['step_index']:
            raise ValueError('scene_ack_binding')


def _bound_applied(applied, wanted):
    a, b = applied['state'], wanted['state']
    if (any(applied[k] != wanted[k] for k in ('protocol_version', 'step_index', 'registration_id')) or
            any(a[k] != b[k] for k in ('header', 'body_frame_id', 'velocity_frame_id', 'state_source', 'quality'))):
        raise ValueError('scene_response_binding')
    for x, y in ((a['position'], b['position']), (a['linear_velocity'], b['linear_velocity']),
                 (applied['angular_velocity_flu'], wanted['angular_velocity_flu'])):
        if any(abs(v - w) > 1e-9 for v, w in zip(x, y)):
            raise ValueError('scene_applied_geometry')
    q, r = a['orientation_xyzw'], b['orientation_xyzw']
    if min(max(abs(v - w) for v, w in zip(q, r)), max(abs(v + w) for v, w in zip(q, r))) > 1e-12:
        raise ValueError('scene_applied_orientation')


def validate_response(value, request=None):
    fields(value, 'accepted reason applied_frame radar_timestamp infrared_timestamp')
    if type(value['accepted']) is not bool:
        raise ValueError('scene_response_boolean')
    reason(value['reason'], value['accepted'])
    applied = value['applied_frame']
    times = [value['radar_timestamp'], value['infrared_timestamp']]
    for stamp in times:
        if stamp is not None:
            integer(stamp)
    if applied is None:
        if value['accepted'] or any(stamp is not None for stamp in times):
            raise ValueError('scene_missing_applied_frame')
    else:
        validate_frame(applied)
        if value['accepted']:
            expected = applied['step_index'] * STEP_NS if capture_step(applied['step_index']) else None
            if times != [expected, expected]:
                raise ValueError('scene_response_capture_time')
    if request is not None:
        validate_request(request)
        if applied is not None:
            _bound_applied(applied, request['frame'])


VALIDATORS = dict(SceneFrame=validate_frame, SceneCaptureAck=validate_ack,
                  SceneStepRequest=validate_request, SceneStepResponse=validate_response)
