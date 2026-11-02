"""Private offline flight observations; no simulator, ROS or command transport."""
import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import struct

HEADER_BYTES = 262144
RECORD_BYTES = 16384
STREAM_BYTES = 67108864
STREAM_RECORDS = 12288
STEP_NS = 4000000
MAX_STEP = 10000
TEXT_BYTES = 128
CHANNELS = (
    ('rudder', 2, -1, 'fcs/rudder-cmd-norm'),
    ('aileron', 5, -1, 'fcs/aileron-cmd-norm'),
    ('elevator', 7, -1, 'fcs/elevator-cmd-norm'),
    ('throttle', 4, 1, 'fcs/throttle-cmd-norm'))
IC = dict(latitude_deg=47.458159, longitude_deg=8.548004,
    altitude_reference='AGL', altitude_m=.5, terrain_elevation_m=419.2,
    true_airspeed_mps=0., phi_theta_psi_deg=[0., 0., 90.], gamma_deg=None)


def _text(value, empty=False):
    if type(value) is not str or (not value and not empty) or len(value) > TEXT_BYTES:
        raise ValueError('flight_text')
    try:
        if len(value.encode('utf-8')) > TEXT_BYTES or any(ord(c) < 32 for c in value):
            raise ValueError('flight_text')
    except UnicodeError as exc:
        raise ValueError('flight_text_encoding') from exc


def _integer(value, maximum=2**63-1, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('flight_integer')


def _number(value):
    if type(value) not in (int, float):
        raise ValueError('flight_number')
    try:
        if not math.isfinite(value):raise ValueError('flight_nonfinite')
    except OverflowError as exc:
        raise ValueError('flight_number_overflow') from exc


def _bounded(value):
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        if nodes > 8192 or depth > 8:raise ValueError('flight_structure_limit')
        if type(item) is dict:
            if len(item) > 64:raise ValueError('flight_object_limit')
            for key, child in item.items():
                _text(key)
                pending.append((child, depth+1))
        elif type(item) is list:
            if len(item) > 512:raise ValueError('flight_list_limit')
            pending.extend((child, depth+1) for child in item)
        elif type(item) is str:_text(item, empty=True)
        elif item is not None and type(item) is not bool:_number(item)


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names.split()):
        raise ValueError('flight_fields')


def _fixed(actual, expected):
    if type(actual) is not type(expected):raise ValueError('flight_fixed_type')
    if type(expected) is dict:
        _fields(actual, ' '.join(expected))
        for key, value in expected.items():_fixed(actual[key], value)
    elif type(expected) is list:
        if len(actual) != len(expected):raise ValueError('flight_fixed_shape')
        for a, b in zip(actual, expected):_fixed(a, b)
    elif actual != expected:raise ValueError('flight_fixed_value')


def validate_ic(value):
    _bounded(value)
    _fixed(value, IC)


def validate_profile(value):
    _bounded(value)
    expected = dict(schema_version='sim_flight_fixture.v1', profile_id='sim-flight-ground-observe-v1',
        fixture_only=True, simulation_only=True, mode='px4_stabilized_sitl',
        commands_enabled=False, observation_only=True,
        model=dict(airframe=1033, sys_ctrl_alloc=0, aircraft_model='Rascal110-JSBSim',
            bridge_config='configs/rascal.xml', mixer='etc/mixers-sitl/plane_sitl.main.mix'),
        ic=IC, actuator_channels=[dict(name=n, index=i, scale=s, property=p) for n,i,s,p in CHANNELS],
        time=dict(step_ns=STEP_NS, max_step=MAX_STEP, prepare_steps=7500, capture_period_steps=25,
            bootstrap_source_steps=500, bootstrap_wall_ns=5000000000),
        state=dict(source='ground_truth', frame_id='scene_world', body_frame_id='base_link',
            registration_id='jsbsim_cg_to_flight_enu_v1', anchor_m=[0.,0.,.5]),
        command_policy=dict(allowed=[], force_arming_allowed=False),
        limits=dict(header_bytes=HEADER_BYTES, record_bytes=RECORD_BYTES, depth=8, nodes=8192,
            text_bytes=TEXT_BYTES, list_items=512, stream_records=STREAM_RECORDS, control_log_bytes=STREAM_BYTES,
            control_events=4096, wire_bytes=134217728, artifact_bytes=536870912,
            startup_wall_ns=60000000000, transaction_wall_ns=1000000000,
            first_capture_wall_ns=3000000000, case_wall_ns=240000000000))
    _fixed(value, expected)


def _vector(value, size):
    if type(value) is not list or len(value) != size:raise ValueError('flight_vector')
    for item in value:_number(item)


def _controls(value):
    _vector(value, 16)
    for i, item in enumerate(value):
        if not (0 if i == 4 else -1) <= item <= 1:raise ValueError('flight_control_range')
        if struct.unpack('<f', struct.pack('<f', item))[0] != item:
            raise ValueError('flight_control_not_float32')


def map_controls(controls):
    """Convert an observed vector to requested properties, without applying it."""
    _controls(controls)
    return [scale*controls[index] for _,index,scale,_ in CHANNELS]


def capture_step(index):
    _integer(index, MAX_STEP)
    return index > 7500 and index % 25 == 0


def _identity(value):
    _text(value['run_id']);_text(value['clock_id'])
    if value['clock_id'] != 'sim:'+value['run_id']:raise ValueError('flight_clock_identity')


def _peer(value):
    _fields(value, 'address port system_id component_id')
    if value['address'] != '127.0.0.1':raise ValueError('flight_peer_address')
    _integer(value['port'], 65535, 1024)
    for name in ('system_id','component_id'):
        _integer(value[name], 255, 1)
        if value[name] != 1:raise ValueError('flight_peer_identity')


def validate_record(value):
    _bounded(value)
    _fields(value, 'schema_version run_id clock_id step_index source_step hil_sensor_time_us '
        'has_actuator actuator binding_status reason properties fdm wall')
    if value['schema_version'] != 'sim_flight_actuator_record.v1':raise ValueError('flight_record_version')
    _identity(value)
    _integer(value['step_index'], MAX_STEP, 1);_integer(value['source_step'], MAX_STEP-1)
    if value['source_step'] != value['step_index']-1:raise ValueError('flight_source_step')
    _integer(value['hil_sensor_time_us'], 2**64-1)
    if type(value['has_actuator']) is not bool:raise ValueError('flight_presence_flag')
    if value['binding_status'] != 'unverified':raise ValueError('flight_binding_not_measured')
    props, fdm, wall = value['properties'], value['fdm'], value['wall']
    _fields(props, 'before requested after')
    for key in ('before','after'):
        _vector(props[key], 4)
        if any(not (-1 if i<3 else 0) <= p <= 1 for i,p in enumerate(props[key])):
            raise ValueError('flight_property_range')
    _fields(wall, 'hil_sent_ns actuator_received_ns properties_applied_ns fdm_finished_ns')
    _integer(wall['hil_sent_ns']);_integer(wall['fdm_finished_ns'])
    if wall['fdm_finished_ns'] < wall['hil_sent_ns']:raise ValueError('flight_wall_order')
    if value['has_actuator']:
        a = value['actuator']
        _fields(a, 'receive_sequence peer time_usec flags mode armed controls')
        _integer(a['receive_sequence'], 2**64-1, 1);_peer(a['peer'])
        _integer(a['time_usec'], 2**64-1);_integer(a['flags'], 2**64-1);_integer(a['mode'], 255)
        if a['flags'] not in (0,1) or a['mode'] not in (1,129):raise ValueError('flight_actuator_flags_or_mode')
        if type(a['armed']) is not bool or a['armed'] != bool(a['mode'] & 128):
            raise ValueError('flight_armed_flag')
        requested = map_controls(a['controls'])
        if not a['armed'] and any(a['controls']):raise ValueError('flight_disarmed_nonzero')
        _vector(props['requested'], 4)
        if props['requested'] != requested or any(abs(a-b)>1e-6 for a,b in zip(props['after'], requested)):
            raise ValueError('flight_property_readback')
        for key in ('actuator_received_ns','properties_applied_ns'):_integer(wall[key])
        if not wall['hil_sent_ns'] <= wall['actuator_received_ns'] <= wall['properties_applied_ns'] <= wall['fdm_finished_ns']:
            raise ValueError('flight_wall_order')
        if value['reason'] != '':raise ValueError('flight_present_reason')
    elif (value['actuator'] is not None or props['requested'] is not None or
            wall['actuator_received_ns'] is not None or wall['properties_applied_ns'] is not None or
            value['reason'] != 'actuator_not_received' or props['before'] != props['after']):
        raise ValueError('flight_missing_slots')
    _fields(fdm, 'ran result sim_time_before_s sim_time_after_s')
    if type(fdm['ran']) is not bool:raise ValueError('flight_fdm_ran_flag')
    for key in ('sim_time_before_s','sim_time_after_s'):
        _number(fdm[key])
        if fdm[key] < 0:raise ValueError('flight_negative_fdm_time')
    before, after = (Fraction(fdm[k])*1000000000 for k in ('sim_time_before_s','sim_time_after_s'))
    if abs(before-value['source_step']*STEP_NS)>1:raise ValueError('flight_fdm_before_time')
    if fdm['ran']:
        if type(fdm['result']) is not bool:raise ValueError('flight_fdm_result')
        if fdm['result']:
            if abs(after-value['step_index']*STEP_NS)>1 or abs(after-before-STEP_NS)>1:
                raise ValueError('flight_fdm_step_time')
        elif min(abs(after-before),abs(after-value['step_index']*STEP_NS))>1:
            raise ValueError('flight_failed_fdm_time')
    elif fdm['result'] is not None or after != before:
        raise ValueError('flight_fdm_not_run_slots')


def validate_header(value):
    _bounded(value)
    _fields(value, 'schema_version run_id clock_id profile peer initial_properties initial_wall_ns')
    if value['schema_version'] != 'sim_flight_recording.v1':raise ValueError('flight_recording_version')
    _identity(value);validate_profile(value['profile']);_peer(value['peer'])
    _vector(value['initial_properties'],4)
    if any(value['initial_properties']):raise ValueError('flight_initial_properties')
    _integer(value['initial_wall_ns'])


def _validate(kind, value):
    validators = dict(profile=validate_profile, ic=validate_ic, record=validate_record, header=validate_header)
    if kind not in validators:raise ValueError('flight_kind')
    validators[kind](value)


def loads(kind, raw):
    limit = RECORD_BYTES if kind == 'record' else HEADER_BYTES
    if type(raw) is not bytes or len(raw)>limit:raise ValueError('flight_json_bytes')
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:raise ValueError('flight_duplicate_key')
            result[key] = value
        return result
    def nonfinite(_):raise ValueError('flight_json_nonfinite')
    def integer(raw):
        if len(raw)>21:raise ValueError('flight_json_integer_limit')
        return int(raw)
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite, parse_int=integer)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('flight_json_encoding_or_depth') from exc
    _validate(kind,value)
    return value


def dumps(kind, value):
    _validate(kind,value)
    raw = json.dumps(value, separators=(',',':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw)>(RECORD_BYTES if kind=='record' else HEADER_BYTES):raise ValueError('flight_json_bytes')
    return raw


def load_profile(path):
    with Path(path).open('rb') as stream:return loads('profile',stream.read(HEADER_BYTES+1))


def validate_recording(header, records):
    """Stream validation only. Unverified timing can never become control-gate evidence."""
    total = len(dumps('header',header))+1
    header = copy.deepcopy(header)
    previous_properties = copy.deepcopy(header['initial_properties'])
    previous_time = 0.
    previous_wall = header['initial_wall_ns']
    last_receive = 0
    seen = False
    terminal = False
    last_hil = last_actuator_time = None
    summary = dict(records=0, actuator_observations=0, missing_actuators=0, fdm_successes=0,
        last_step=0, last_receive_sequence=0, control_gate_accepted=False)
    for record in records:
        if terminal:raise ValueError('flight_record_after_terminal')
        if summary['records'] >= STREAM_RECORDS:raise ValueError('flight_record_count_limit')
        raw = dumps('record',record)
        if total+len(raw)+1>STREAM_BYTES:raise ValueError('flight_recording_byte_limit')
        if (any(record[k]!=header[k] for k in ('run_id','clock_id')) or
                record['step_index']!=summary['last_step']+1):raise ValueError('flight_recording_identity_or_order')
        props, fdm, wall = record['properties'],record['fdm'],record['wall']
        if props['before']!=previous_properties or fdm['sim_time_before_s']!=previous_time:
            raise ValueError('flight_recording_discontinuity')
        if wall['hil_sent_ns']<previous_wall:raise ValueError('flight_recording_wall_order')
        if last_hil is not None and record['hil_sensor_time_us']<=last_hil:
            raise ValueError('flight_recording_hil_time_order')
        if record['has_actuator']:
            a = record['actuator']
            if a['peer']!=header['peer'] or a['receive_sequence']<=last_receive:
                raise ValueError('flight_recording_peer_or_sequence')
            if a['armed']:raise ValueError('flight_observation_only_armed')
            if last_actuator_time is not None and a['time_usec']<=last_actuator_time:
                raise ValueError('flight_recording_actuator_time_order')
            last_actuator_time=a['time_usec']
            seen = True;last_receive = a['receive_sequence']
            summary['actuator_observations']+=1
        else:
            if fdm['ran'] and (seen or record['step_index']>500 or
                    wall['fdm_finished_ns']-header['initial_wall_ns']>5000000000):
                raise ValueError('flight_missing_after_bootstrap')
            summary['missing_actuators']+=1
        terminal = not fdm['ran'] or not fdm['result']
        summary['fdm_successes']+=int(fdm['result'] is True)
        summary['records']+=1;summary['last_step']=record['step_index']
        total+=len(raw)+1
        last_hil=record['hil_sensor_time_us']
        previous_properties,previous_time,previous_wall=list(props['after']),fdm['sim_time_after_s'],wall['fdm_finished_ns']
    if not summary['records']:raise ValueError('flight_empty_recording')
    summary.update(last_receive_sequence=last_receive,bytes=total,terminal=terminal)
    return summary


def load_recording(path):
    with Path(path).open('rb') as stream:
        raw_header = stream.readline(HEADER_BYTES+1)
        header = loads('header',raw_header)
        total = [len(raw_header)]
        def records():
            count = 0
            while True:
                raw = stream.readline(RECORD_BYTES+1)
                if not raw:return
                total[0]+=len(raw);count+=1
                if count>STREAM_RECORDS or total[0]>STREAM_BYTES:raise ValueError('flight_recording_limit')
                yield loads('record',raw)
        result=validate_recording(header,records())
        result['source_bytes']=total[0]
        return result
