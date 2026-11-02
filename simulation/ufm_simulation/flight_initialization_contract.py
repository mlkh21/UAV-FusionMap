"""Private initialization observations. No process, ROS, simulator or control IO."""
import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import re

from .flight_contract import IC, CHANNELS, _fixed, _number, _peer, _vector, _controls
from .flight_probe_contract import fields, integer, same, text, validate_owner

PREFIX = 'sim_flight_initialization_'
PROFILE_ID = 'sim-flight-initialization-observe-v1'
CHECKPOINTS = (125, 250, 500, 1000, 1500, 2000, 2500)
TOPICS = ('estimator_selector_status', 'vehicle_imu', 'estimator_status', 'estimator_status_flags',
    'estimator_attitude', 'vehicle_attitude', 'vehicle_control_mode', 'actuator_controls_0',
    'actuator_outputs', 'vehicle_land_detected', 'estimator_selector_status')
PARAMETERS = (('SYS_AUTOSTART', 'int32', 1033), ('SYS_CTRL_ALLOC', 'int32', 0),
    ('SENS_IMU_MODE', 'int32', 0), ('EKF2_ANGERR_INIT', 'float32', .1),
    ('EKF2_MAG_TYPE', 'int32', 0), ('EKF2_HGT_MODE', 'int32', 0), ('EKF2_AID_MASK', 'int32', 1))
GEARS = ('LEFT_MLG', 'RIGHT_MLG', 'TAIL_LG')
LIMITS = dict(header_bytes=262144, record_bytes=16384, event_bytes=262144, raw_bytes=32768,
    depth=8, nodes=8192, text_bytes=128, list_items=512, stream_records=2500, query_records=128,
    stream_bytes=67108864, query_bytes=16777216, wire_bytes=16777216, wire_events=8192,
    artifact_bytes=268435456, build_wall_ns=180000000000, startup_wall_ns=60000000000,
    prepare_wall_ns=60000000000, session_wall_ns=120000000000, transaction_wall_ns=1000000000,
    client_wall_ns=200000000, group_wall_ns=400000000, agl_min_m=-.05, agl_max_m=1.,
    roll_max_deg=30., pitch_max_deg=25., horizontal_max_m=2., airspeed_max_mps=5.,
    pilot_accel_max_mps2=98.0665, pqr_max_radps=2., settled_speed_max_mps=.5,
    settled_gyro_max_radps=0.2617993877991494, settled_accel_min_mps2=7.84532,
    settled_accel_max_mps2=11.76798, status_age_us=200000, slow_age_us=1200000,
    attitude_age_us=20000, quaternion_norm_error=.001)
UNITS = dict(ecef_ft='ECEF:ft', vel_ned_ftps='NED:ft/s', vel_ned_mps='NED:m/s',
    euler_deg='NED_FRD:deg', pqr_radps='FRD:rad/s', pilot_accel_ftps2='FRD:ft/s^2',
    pilot_accel_mps2='FRD:m/s^2', compression_lbf='lbf', compression_n='N')


def profile_reference():
    return dict(schema_version=PREFIX+'fixture.v1', profile_id=PROFILE_ID, fixture_only=True,
        simulation_only=True, observation_only=True, commands_enabled=False, capture_active=False,
        ic=copy.deepcopy(IC), model=dict(airframe=1033, sys_ctrl_alloc=0, aircraft_model='Rascal110-JSBSim',
            bridge_config='configs/rascal.xml', mixer='etc/mixers-sitl/plane_sitl.main.mix',
            gear_names=list(GEARS), source_units=dict(UNITS), ft_to_m=.3048, lbf_to_n=4.4482216152605),
        actuator_channels=[dict(name=n,index=i,scale=s,property=p) for n,i,s,p in CHANNELS],
        time=dict(step_ns=4000000,max_step=2500,settled_steps=250,ready_checkpoints=[2000,2500]),
        checkpoints=list(CHECKPOINTS), topics=list(TOPICS),
        parameters=[dict(name=n,kind=k,value=v) for n,k,v in PARAMETERS], limits=dict(LIMITS))


def bounded(value):
    pending = [(value, 0, '')]
    nodes = 0
    while pending:
        item, depth, name = pending.pop()
        nodes += 1
        if nodes > 8192 or depth > 8:
            raise ValueError('initialization_structure_limit')
        if type(item) is dict:
            if len(item) > 256:
                raise ValueError('initialization_object_limit')
            for key, child in item.items():
                text(key,128)
                pending.append((child,depth+1,key))
        elif type(item) is list:
            if len(item) > 512:
                raise ValueError('initialization_list_limit')
            pending.extend((child,depth+1,name) for child in item)
        elif type(item) is str:
            cap = 32768 if name in ('stdout','stderr') else 1024 if name in (
                'executable','rootfs','socket_path','argv') else 128
            text(item,cap,raw=name in ('stdout','stderr'))
        elif item is not None and type(item) is not bool:
            _number(item)


def identity(value):
    text(value['run_id'],120)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',value['run_id']) or value['clock_id'] != 'sim:'+value['run_id']:
        raise ValueError('initialization_identity')


def gate(value):
    if value['binding_status'] != 'unverified' or value['control_gate_accepted'] is not False:
        raise ValueError('initialization_control_gate')


def check_budget(now_ns, session_started_ns, initial_wall_ns=None, **usage):
    """Pure guard for callers before spawn, after persistence and before next/Run."""
    integer(now_ns); integer(session_started_ns)
    if not 0 <= now_ns-session_started_ns <= LIMITS['session_wall_ns']:
        raise ValueError('initialization_session_deadline')
    if initial_wall_ns is not None:
        integer(initial_wall_ns)
        if initial_wall_ns < session_started_ns or not 0 <= now_ns-initial_wall_ns <= LIMITS['prepare_wall_ns']:
            raise ValueError('initialization_prepare_deadline')
    allowed = ('build_wall_ns','startup_wall_ns','stream_bytes','query_bytes','wire_bytes',
        'wire_events','artifact_bytes','stream_records','query_records')
    if not set(usage) <= set(allowed):
        raise ValueError('initialization_budget_fields')
    for name,value in usage.items():
        integer(value,LIMITS[name])


def validate_profile(value):
    bounded(value)
    _fixed(value,profile_reference())


def plan(run_id):
    identity(dict(run_id=run_id,clock_id='sim:'+run_id))
    items = [(125,'parameter',name) for name,_,_ in PARAMETERS]
    items += [(step,'topic',topic) for step in CHECKPOINTS for topic in TOPICS]
    return [dict(schema_version=PREFIX+'query.v1',run_id=run_id,clock_id='sim:'+run_id,
        checkpoint=step,query_index=i+1,kind=kind,name=name) for i,(step,kind,name) in enumerate(items)]


def validate_query(value):
    bounded(value)
    fields(value,'schema_version run_id clock_id checkpoint query_index kind name')
    identity(value)
    integer(value['checkpoint'],2500,1)
    integer(value['query_index'],84,1)
    if not same(value,plan(value['run_id'])[value['query_index']-1]):
        raise ValueError('initialization_query_plan')


def argv_for(binary_dir, query):
    validate_query(query)
    base = Path(binary_dir)
    if query['kind'] == 'parameter':
        return [str(base/'px4-param'),'--instance','0','show',query['name']]
    return [str(base/'px4-listener'),'--instance','0',query['name'],'-n','1']


def _time(value, step):
    _number(value)
    if abs(Fraction(value)*1000000000-step*4000000) > 1:
        raise ValueError('initialization_source_time')


def validate_kinematics(value):
    fields(value,'sim_time_s agl_m asl_m geodetic_altitude_m terrain_m ecef_ft vel_ned_ftps '
        'vel_ned_mps euler_deg pqr_radps pilot_accel_ftps2 pilot_accel_mps2 true_airspeed_mps')
    vectors = ('ecef_ft','vel_ned_ftps','vel_ned_mps','euler_deg','pqr_radps',
        'pilot_accel_ftps2','pilot_accel_mps2')
    for name in vectors:
        _vector(value[name],3)
    for name in set(value)-set(vectors):
        _number(value[name])
    if value['sim_time_s'] < 0 or value['true_airspeed_mps'] < 0:
        raise ValueError('initialization_negative_physics')
    for raw,si in (('vel_ned_ftps','vel_ned_mps'),('pilot_accel_ftps2','pilot_accel_mps2')):
        if any(abs(x*.3048-y)>1e-9 for x,y in zip(value[raw],value[si])):
            raise ValueError('initialization_unit_conversion')


def validate_ground(value):
    if type(value) is not list or len(value) != 3:
        raise ValueError('initialization_gear_count')
    for name,item in zip(GEARS,value):
        fields(item,'name wow compression_lbf compression_n')
        if item['name'] != name or type(item['wow']) is not bool:
            raise ValueError('initialization_gear_identity')
        _number(item['compression_lbf']); _number(item['compression_n'])
        if abs(item['compression_lbf']*4.4482216152605-item['compression_n']) > 1e-9:
            raise ValueError('initialization_force_conversion')


def validate_step(value):
    validate_step_fields(value, PREFIX+'step.v1', PROFILE_ID, 2500)


def validate_step_fields(value, schema_version, profile_id, max_steps):
    """Shared physical fields; each caller owns its exact envelope and source bound."""
    bounded(value)
    fields(value,'schema_version run_id clock_id profile_id step_index source_step hil_sensor_time_us '
        'has_actuator actuator reason properties fdm wall kinematics_before kinematics_after '
        'ground_before ground_after binding_status control_gate_accepted')
    if value['schema_version'] != schema_version or value['profile_id'] != profile_id:
        raise ValueError('initialization_step_version')
    identity(value); gate(value)
    integer(value['step_index'],max_steps,1); integer(value['source_step'],max_steps-1)
    if value['source_step'] != value['step_index']-1:
        raise ValueError('initialization_step_order')
    integer(value['hil_sensor_time_us'],2**64-1)
    if value['hil_sensor_time_us'] != value['source_step']*4000:
        raise ValueError('initialization_hil_time')
    for name in ('before','after'):
        validate_kinematics(value['kinematics_'+name]); validate_ground(value['ground_'+name])
    props,fdm,wall = value['properties'],value['fdm'],value['wall']
    fields(props,'before requested after')
    for name in ('before','after'):
        _vector(props[name],4)
        if any(props[name]):
            raise ValueError('initialization_nonzero_property')
    fields(wall,'hil_sent_ns actuator_received_ns properties_applied_ns fdm_finished_ns')
    for name in ('hil_sent_ns','fdm_finished_ns'):
        integer(wall[name])
    if not 0 <= wall['fdm_finished_ns']-wall['hil_sent_ns'] <= 1000000000:
        raise ValueError('initialization_transaction_time')
    if type(value['has_actuator']) is not bool:
        raise ValueError('initialization_actuator_presence')
    if value['has_actuator']:
        actuator = value['actuator']
        fields(actuator,'receive_sequence peer time_usec flags mode armed controls')
        _peer(actuator['peer']); _controls(actuator['controls'])
        integer(actuator['receive_sequence'],2**64-1,1); integer(actuator['time_usec'],2**64-1)
        integer(actuator['flags'],1); integer(actuator['mode'],255)
        if actuator['mode'] != 1 or actuator['armed'] is not False or any(actuator['controls']):
            raise ValueError('initialization_armed_or_nonzero')
        _vector(props['requested'],4)
        if any(props['requested']) or value['reason'] != '':
            raise ValueError('initialization_requested_properties')
        for name in ('actuator_received_ns','properties_applied_ns'):
            integer(wall[name])
        if not wall['hil_sent_ns'] <= wall['actuator_received_ns'] <= wall['properties_applied_ns'] <= wall['fdm_finished_ns']:
            raise ValueError('initialization_wall_order')
    elif (value['actuator'] is not None or props['requested'] is not None
            or wall['actuator_received_ns'] is not None or wall['properties_applied_ns'] is not None
            or value['reason'] != 'preparation_no_actuator'):
        raise ValueError('initialization_missing_slots')
    fields(fdm,'ran result sim_time_before_s sim_time_after_s hil_sensor')
    sensor = fdm['hil_sensor']
    fields(sensor,'time_usec accel_mps2 gyro_radps')
    integer(sensor['time_usec'],2**64-1)
    if sensor['time_usec'] != value['hil_sensor_time_us']:
        raise ValueError('initialization_sensor_time')
    _vector(sensor['accel_mps2'],3); _vector(sensor['gyro_radps'],3)
    _time(fdm['sim_time_before_s'],value['source_step'])
    if type(fdm['ran']) is not bool:
        raise ValueError('initialization_ran_type')
    if fdm['ran']:
        if type(fdm['result']) is not bool:
            raise ValueError('initialization_result_type')
        if fdm['result']:
            _time(fdm['sim_time_after_s'],value['step_index'])
        else:
            _number(fdm['sim_time_after_s'])
            if min(abs(fdm['sim_time_after_s']-s*.004) for s in (value['source_step'],value['step_index'])) > 1e-9:
                raise ValueError('initialization_failed_time')
    elif fdm['result'] is not None or not same(value['kinematics_before'],value['kinematics_after']) or not same(value['ground_before'],value['ground_after']):
        raise ValueError('initialization_not_run_slots')
    _number(fdm['sim_time_after_s'])
    if not fdm['ran'] and fdm['sim_time_after_s'] != fdm['sim_time_before_s']:
        raise ValueError('initialization_not_run_time')
    for name in ('before','after'):
        if value['kinematics_'+name]['sim_time_s'] != fdm['sim_time_'+name+'_s']:
            raise ValueError('initialization_kinematics_time')


def validate_header(value):
    bounded(value)
    fields(value,'schema_version run_id clock_id profile peer initial_wall_ns initial_properties initial_kinematics initial_ground')
    if value['schema_version'] != PREFIX+'recording.v1':
        raise ValueError('initialization_recording_version')
    identity(value); validate_profile(value['profile']); _peer(value['peer'])
    integer(value['initial_wall_ns']); _vector(value['initial_properties'],4)
    if any(value['initial_properties']):
        raise ValueError('initialization_initial_properties')
    validate_kinematics(value['initial_kinematics']); validate_ground(value['initial_ground'])
    initial = value['initial_kinematics']
    if (initial['sim_time_s'] != 0 or abs(initial['agl_m']-.5)>1e-6
            or abs(initial['terrain_m']-419.2)>1e-6 or initial['true_airspeed_mps'] != 0
            or any(abs(a-b)>1e-9 for a,b in zip(initial['euler_deg'],(0,0,90)))):
        raise ValueError('initialization_initial_readback')


def norm(vector):
    return math.hypot(*vector)


def _safe(value, initial):
    # ECEF displacement is projected onto the initial geodetic horizontal plane.
    delta = [(a-b)*.3048 for a,b in zip(value['ecef_ft'],initial['ecef_ft'])]
    lat,lon = math.radians(IC['latitude_deg']),math.radians(IC['longitude_deg'])
    north = -math.sin(lat)*math.cos(lon)*delta[0]-math.sin(lat)*math.sin(lon)*delta[1]+math.cos(lat)*delta[2]
    east = -math.sin(lon)*delta[0]+math.cos(lon)*delta[1]
    return (-.05 <= value['agl_m'] <= 1 and abs(value['euler_deg'][0]) <= 30
        and abs(value['euler_deg'][1]) <= 25 and math.hypot(north,east) <= 2
        and value['true_airspeed_mps'] <= 5 and norm(value['pilot_accel_mps2']) <= 98.0665
        and norm(value['pqr_radps']) <= 2)


def validate_steps(header, records):
    """Bounded stream audit; retain only seven checkpoint contexts, never the whole stream."""
    total = len(dumps('header',header))+1
    initial = header['initial_kinematics']
    previous = copy.deepcopy(initial); ground = copy.deepcopy(header['initial_ground'])
    wall = header['initial_wall_ns']
    seen = False
    last_receive = last_actuator = count = successes = observed = settled = 0
    terminal = unsafe = False
    checkpoints = {}
    output_steps = []
    for record in records:
        if terminal or count >= 2500:
            raise ValueError('initialization_after_terminal_or_limit')
        raw = dumps('step',record)
        total += len(raw)+1
        if total > 67108864:
            raise ValueError('initialization_recording_bytes')
        if any(record[k] != header[k] for k in ('run_id','clock_id')) or record['step_index'] != count+1:
            raise ValueError('initialization_stream_identity_order')
        if not same(record['kinematics_before'],previous) or not same(record['ground_before'],ground):
            raise ValueError('initialization_physics_discontinuity')
        timing,fdm = record['wall'],record['fdm']
        if str(count) in checkpoints:
            checkpoints[str(count)]['next_hil_sent_ns'] = timing['hil_sent_ns']
        if timing['hil_sent_ns'] < wall or timing['fdm_finished_ns']-header['initial_wall_ns'] > 60000000000:
            raise ValueError('initialization_prepare_deadline')
        if not _safe(record['kinematics_before'],initial) and fdm['ran']:
            raise ValueError('initialization_unsafe_before_run')
        if record['has_actuator']:
            actuator = record['actuator']
            if (actuator['peer'] != header['peer'] or actuator['receive_sequence'] != last_receive+1
                    or (seen and actuator['time_usec'] <= last_actuator)):
                raise ValueError('initialization_actuator_sequence_peer')
            seen = True; last_receive = actuator['receive_sequence']; last_actuator = actuator['time_usec']
            observed += 1
            if record['step_index'] > 2000 and fdm['result'] is True:
                output_steps.append(record['step_index'])
        elif seen and fdm['ran']:
            raise ValueError('initialization_missing_after_first')
        count += 1
        successes += int(fdm['result'] is True)
        previous = copy.deepcopy(record['kinematics_after']); ground = copy.deepcopy(record['ground_after'])
        wall = timing['fdm_finished_ns']
        unsafe = not _safe(previous,initial)
        terminal = fdm['result'] is not True or unsafe
        sensor = fdm['hil_sensor']
        stable = (fdm['result'] is True and not unsafe and any(g['wow'] for g in ground)
            and 0 <= previous['agl_m'] <= 1 and norm(previous['vel_ned_mps']) <= .5
            and norm(previous['pqr_radps']) <= math.radians(15)
            and 7.84532 <= norm(sensor['accel_mps2']) <= 11.76798)
        settled = settled+1 if stable else 0
        if count in CHECKPOINTS and fdm['result'] is True:
            checkpoints[str(count)] = dict(input_settled=settled>=250,last_hil_us=record['hil_sensor_time_us'],
                wall_ns=wall,fdm_time_s=fdm['sim_time_after_s'])
    if not count:
        raise ValueError('initialization_empty_stream')
    return dict(records=count,fdm_successes=successes,actuator_observations=observed,
        missing_actuators=count-observed,last_receive_sequence=last_receive,last_step=count,
        terminal=terminal,unsafe=unsafe,bytes=total,checkpoints=checkpoints,
        input_settled=all(checkpoints.get(str(s),{}).get('input_settled',False) for s in (2000,2500)),
        output_chain_observed=len(output_steps)>=2,binding_status='unverified',control_gate_accepted=False)


def validate_terminal(value):
    bounded(value)
    fields(value,'schema_version run_id clock_id profile_id last_step reason wall_ns binding_status control_gate_accepted')
    identity(value); gate(value)
    if value['schema_version'] != PREFIX+'terminal.v1' or value['profile_id'] != PROFILE_ID:
        raise ValueError('initialization_terminal_version')
    integer(value['last_step'],2500); integer(value['wall_ns'])
    if value['reason'] not in ('window_complete','not_ready_at_limit','requested_stop',
            'peer_closed','transaction_timeout','budget_exceeded','unsafe_state','fdm_failed','invalid_input'):
        raise ValueError('initialization_terminal_reason')
    if value['reason'] in ('window_complete','not_ready_at_limit') and value['last_step'] != 2500:
        raise ValueError('initialization_terminal_limit')


def _validate(kind, value, layouts=None, binary_dir=None):
    validators = dict(profile=validate_profile,header=validate_header,step=validate_step,
        query=validate_query,terminal=validate_terminal)
    if kind == 'observation':
        from .flight_initialization_observation import validate_event
        validate_event(value,layouts,binary_dir)
    elif kind in validators:
        validators[kind](value)
    else:
        raise ValueError('initialization_kind')


def _limit(kind):
    return 16384 if kind == 'step' else 262144


def dumps(kind, value, layouts=None, binary_dir=None):
    _validate(kind,value,layouts,binary_dir)
    raw = json.dumps(value,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
    if len(raw) > _limit(kind):
        raise ValueError('initialization_json_bytes')
    return raw


def loads(kind, raw, layouts=None, binary_dir=None):
    if type(raw) is not bytes or len(raw) > _limit(kind):
        raise ValueError('initialization_json_bytes')
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result:
                raise ValueError('initialization_duplicate_key')
            result[key] = value
        return result
    def bad(_):
        raise ValueError('initialization_nonfinite_json')
    def number(token):
        if len(token) > 21:
            raise ValueError('initialization_integer_text')
        return int(token)
    try:
        value = json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=bad,parse_int=number)
    except (UnicodeError,RecursionError) as exc:
        raise ValueError('initialization_json_encoding') from exc
    _validate(kind,value,layouts,binary_dir)
    return value


def load_profile(path):
    with Path(path).open('rb') as stream:
        return loads('profile',stream.read(262145))


def load_recording(path):
    with Path(path).open('rb') as stream:
        first = stream.readline(262145)
        if not first.endswith(b'\n'):
            raise ValueError('initialization_header_line')
        header = loads('header',first)
        total = len(first)
        def records():
            nonlocal total
            for count in range(2501):
                raw = stream.readline(16385)
                if not raw:
                    return
                total += len(raw)
                if count >= 2500 or total > 67108864 or not raw.endswith(b'\n'):
                    raise ValueError('initialization_stream_bound')
                yield loads('step',raw)
        result = validate_steps(header,records())
        result['source_bytes'] = total
        return result
