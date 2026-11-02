"""Private selector observations and offline composition; no daemon or control IO."""
import json
from pathlib import Path
import re

from . import flight_initialization_contract as physical
from . import flight_initialization_observation as original
from .flight_contract import _fixed
from .flight_probe_contract import fields, integer, same, text, validate_owner, _native_field
from .flight_probe_diagnostic import _block
from .flight_probe_quality import _status_block, verify_sources as verify_quality

PREFIX = 'sim_flight_initialization_selector_'
PROFILE_ID = 'sim-flight-initialization-selector-observe-v1'
TOPICS = ('sensors_status_imu', *physical.TOPICS, 'sensors_status_imu')
PHYSICAL_FILES = dict(header='header.json', steps='diagnostics/steps.jsonl',
    terminal='diagnostics/terminal.json', wire='diagnostics/wire.jsonl')
SELECTOR_SOURCES = ('src/modules/ekf2/EKF2Selector.cpp', 'src/modules/ekf2/EKF2Selector.hpp',
    'src/modules/sensors/voted_sensors_update.cpp', 'src/modules/sensors/voted_sensors_update.h',
    'msg/estimator_selector_status.msg', 'msg/sensors_status_imu.msg')
ARRAYS = ('combined_test_ratio', 'relative_test_ratio',
    'accumulated_gyro_error', 'accumulated_accel_error')


def profile_reference():
    return dict(schema_version=PREFIX+'fixture.v1', profile_id=PROFILE_ID, fixture_only=True,
        simulation_only=True, observation_only=True, commands_enabled=False, capture_active=False,
        physical_profile=physical.profile_reference(), checkpoints=list(physical.CHECKPOINTS),
        topics=list(TOPICS), parameters=[dict(name=n,kind=k,value=v) for n,k,v in physical.PARAMETERS],
        limits=dict(physical.LIMITS))


def validate_profile(value):
    physical.bounded(value)
    _fixed(value, profile_reference())


def validate_header(value):
    physical.bounded(value)
    fields(value, 'schema_version run_id clock_id profile physical_files binding_status control_gate_accepted')
    physical.identity(value); physical.gate(value)
    if value['schema_version'] != PREFIX+'recording.v1':
        raise ValueError('selector_recording_version')
    validate_profile(value['profile'])
    _fixed(value['physical_files'], PHYSICAL_FILES)


def plan(run_id):
    physical.identity(dict(run_id=run_id, clock_id='sim:'+run_id))
    items = [(125, 'parameter', name) for name,_,_ in physical.PARAMETERS]
    items += [(step, 'topic', name) for step in physical.CHECKPOINTS for name in TOPICS]
    return [dict(schema_version=PREFIX+'query.v1', run_id=run_id, clock_id='sim:'+run_id,
        checkpoint=step, query_index=i+1, kind=kind, name=name)
        for i,(step,kind,name) in enumerate(items)]


def validate_query(value):
    physical.bounded(value)
    fields(value, 'schema_version run_id clock_id checkpoint query_index kind name')
    physical.identity(value)
    integer(value['checkpoint'], 2500, 1); integer(value['query_index'], 98, 1)
    if not same(value, plan(value['run_id'])[value['query_index']-1]):
        raise ValueError('selector_query_plan')


def argv_for(binary_dir, query):
    validate_query(query)
    if query['kind'] == 'parameter':
        return [str(Path(binary_dir)/'px4-param'), '--instance', '0', 'show', query['name']]
    return [str(Path(binary_dir)/'px4-listener'), '--instance', '0', query['name'], '-n', '1']


def layouts_from_texts(messages, frozen):
    if not same(messages, frozen) or 'sensors_status_imu' not in messages:
        raise ValueError('selector_native_sources_changed')
    old = {k:v for k,v in messages.items() if k != 'sensors_status_imu'}
    layouts = original.layouts_from_texts(old, old)
    layout = {}
    for raw in messages['sensors_status_imu'].splitlines():
        raw = raw.split('#',1)[0].strip()
        if not raw:
            continue
        match = re.fullmatch(r'(uint64|uint32|uint8|float32|bool)(?:\[([0-9]+)\])? ([a-z][a-z0-9_]*)', raw)
        if not match or match[3] in layout:
            raise ValueError('selector_imu_layout')
        layout[match[3]] = (match[1], int(match[2]) if match[2] else 1)
    expected = dict(timestamp=('uint64',1))
    for family, unit in (('accel','m_s_s'), ('gyro','rad_s')):
        expected.update({family+'_device_id_primary':('uint32',1), family+'_device_ids':('uint32',4),
            family+'_inconsistency_'+unit:('float32',4), family+'_healthy':('bool',4),
            family+'_priority':('uint8',4)})
    if layout != expected:
        raise ValueError('selector_imu_layout')
    layouts['sensors_status_imu'] = layout
    return layouts


def verify_sources(sources, messages, quality_sources, baseline):
    """Named preflight consumer of frozen layout and producer semantics, without hashes."""
    if set(sources) != set(SELECTOR_SOURCES) or not same(sources, baseline['selector_sources']):
        raise ValueError('selector_producer_source_changed')
    layouts = layouts_from_texts(messages, baseline['native_messages'])
    old = {k:v for k,v in messages.items() if k not in ('sensors_status_imu','vehicle_land_detected')}
    verify_quality(quality_sources, old, dict(native_messages=old,
        source_regions=baseline['quality_source_regions']))
    return layouts


def _tokens(lines, topic, layout):
    if not lines or lines[0] != ' '+topic:
        raise ValueError('selector_native_body')
    tokens = {}
    for line in lines[1:]:
        match = re.fullmatch(r'    ([a-z][a-z0-9_]*): (.+)', line)
        if not match or match[1] not in layout or match[1] in tokens:
            raise ValueError('selector_native_fields')
        tokens[match[1]] = match[2]
    if set(tokens) != set(layout):
        raise ValueError('selector_native_incomplete')
    return tokens


def _selector_block(lines, layout, instance):
    if not lines:
        return dict(instance=instance, state='payload_unavailable', fields=None, unavailable_fields=[])
    tokens = _tokens(lines, 'estimator_selector_status', layout)
    values = {name:_native_field(raw, name, *layout[name])
        for name,raw in tokens.items() if name not in ARRAYS}
    available, primary = values['instances_available'], values['primary_instance']
    if not 1 <= available <= 9 or not 0 <= primary < available:
        raise ValueError('selector_instance_range')
    if any(values['healthy'][available:]):
        raise ValueError('selector_unseen_healthy')
    unavailable = []
    for name in ARRAYS:
        size = 9 if name in ARRAYS[:2] else 4
        if layout[name] != ('float32',size):
            raise ValueError('selector_array_layout')
        raw = tokens[name]
        if not raw.startswith('[') or not raw.endswith(']'):
            raise ValueError('selector_array_text')
        elements = raw[1:-1].split(', ')
        if len(elements) != size:
            raise ValueError('selector_array_size')
        result = []
        for i,token in enumerate(elements):
            estimator = name in ARRAYS[:2]
            if token == 'nan':
                if estimator and i < available:
                    raise ValueError('selector_seen_nan')
                result.append(None)
                unavailable.append(dict(field=name, index=i, native_token='nan',
                    reason='native_estimator_slot_not_seen' if estimator else 'native_imu_slot_unavailable'))
            else:
                value = _native_field(token, name, 'float32', 1)
                if (estimator and i >= available) or (name=='combined_test_ratio' and value<=0):
                    raise ValueError('selector_ratio_value')
                if not estimator and value < 0:
                    raise ValueError('selector_negative_error')
                result.append(value)
        values[name] = result
    return dict(instance=instance, state='payload_quality_unavailable' if unavailable else 'payload',
        fields=values, unavailable_fields=unavailable)


def _imu_block(lines, layout, instance):
    item = _block(lines, 'sensors_status_imu', layout, instance)
    item['unavailable_fields'] = []
    value = item['fields']
    if value is None:
        return item
    for family,unit in (('accel','m_s_s'), ('gyro','rad_s')):
        ids = value[family+'_device_ids']
        populated = [i for i in ids if i != 0]
        if len(populated) != len(set(populated)):
            raise ValueError('selector_duplicate_imu_id')
        for i,device in enumerate(ids):
            inconsistency = value[family+'_inconsistency_'+unit][i]
            if inconsistency < 0:
                raise ValueError('selector_negative_inconsistency')
            if device==0 and (inconsistency!=0 or value[family+'_healthy'][i]
                    or value[family+'_priority'][i]!=0):
                raise ValueError('selector_empty_imu_slot')
    return item


def _parameter(query, lines):
    name,kind,expected = next(p for p in physical.PARAMETERS if p[0]==query['name'])
    token = r'-?[0-9]{1,11}' if kind=='int32' else r'-?[0-9]{1,40}\.[0-9]{4}'
    if len(lines)!=3 or lines[0]!='Symbols: x = used, + = saved, * = unsaved':
        raise ValueError('selector_parameter_text')
    match = re.fullmatch(r'[ x] [ +*] '+re.escape(name)+r' \[-?[0-9]+,[0-9]+\] : ('+token+')', lines[1])
    if not match or not re.fullmatch(r' [0-9]+/[0-9]+ parameters used\.', lines[2]):
        raise ValueError('selector_parameter_text')
    value = _native_field(match[1], name, kind, 1)
    if not same(value, expected):
        raise ValueError('selector_parameter_mismatch')
    return dict(state='payload', reason='', instances=[], parameter=dict(kind=kind, value=value))


def parse_native(query, stdout, stderr, returncode, layouts):
    validate_query(query)
    return parse_native_payload(query['kind'], query['name'], stdout, stderr, returncode, layouts)


def parse_native_payload(kind, name, stdout, stderr, returncode, layouts):
    """Parse a whitelisted native payload without rewriting any query identity or time."""
    if ((kind == 'topic' and name not in TOPICS) or
            (kind == 'parameter' and name not in [p[0] for p in physical.PARAMETERS]) or
            kind not in ('topic', 'parameter')):
        raise ValueError('selector_payload_kind_or_name')
    query = dict(kind=kind, name=name)
    text(stdout, 32768, raw=True); text(stderr, 32768, raw=True); integer(returncode,255,-255)
    if returncode or stderr or len(stdout.encode())+len(stderr.encode())>32768:
        raise ValueError('selector_client_error')
    if any(ord(c)<32 and c!='\n' for c in stdout):
        raise ValueError('selector_native_control')
    lines = [line for line in stdout.split('\n') if line]
    if query['kind']=='parameter':
        return _parameter(query, lines)
    if lines==['never published']:
        return dict(state='not_published', reason='native_not_published', instances=[], parameter=None)
    topic = query['name']
    def block(body, instance):
        if topic=='estimator_selector_status':
            return _selector_block(body, layouts[topic], instance)
        if topic=='sensors_status_imu':
            return _imu_block(body, layouts[topic], instance)
        if topic=='estimator_status':
            return _status_block(body, layouts[topic], instance)
        item = _block(body, topic, layouts[topic], instance)
        item['unavailable_fields'] = []
        return item
    if not lines:
        raise ValueError('selector_native_empty')
    if lines[0]=='TOPIC: '+topic:
        instances = [block(lines[1:], None)]
    else:
        # These two topics have one producer; a multi-instance title is contradictory.
        if topic in ('estimator_selector_status','sensors_status_imu'):
            raise ValueError('selector_single_producer')
        header = re.fullmatch(r'TOPIC: '+re.escape(topic)+r' ([2-9]) instances', lines[0])
        if not header:
            raise ValueError('selector_native_header')
        blocks = []
        for line in lines[1:]:
            marker = re.fullmatch(r'Instance ([0-8]):', line)
            if marker:
                blocks.append((int(marker[1]), []))
            elif blocks:
                blocks[-1][1].append(line)
            else:
                raise ValueError('selector_native_instance')
        ids = [i for i,_ in blocks]
        if len(ids)!=int(header[1]) or ids!=sorted(set(ids)):
            raise ValueError('selector_native_instance')
        instances = [block(body,i) for i,body in blocks]
    states = {i['state'] for i in instances}
    if 'payload_unavailable' in states:
        state,reason = 'payload_unavailable','native_payload_unavailable'
    elif 'payload_quality_unavailable' in states:
        state,reason = 'payload_quality_unavailable','native_optional_quality_unavailable'
    else:
        state,reason = 'payload',''
    return dict(state=state, reason=reason, instances=instances, parameter=None)


def validate_event(value, layouts, binary_dir):
    physical.bounded(value)
    fields(value, 'schema_version query argv owner_before owner_after last_hil_us fdm_time_s '
        'wall_start_ns wall_end_ns returncode stdout stderr observation binding_status control_gate_accepted')
    if value['schema_version']!=PREFIX+'observation.v1':
        raise ValueError('selector_event_version')
    query = value['query']
    validate_query(query); physical.gate(value)
    if not same(value['argv'], argv_for(binary_dir, query)):
        raise ValueError('selector_argv')
    for name in ('owner_before','owner_after'):
        validate_owner(value[name], binary_dir, query['run_id'])
    if not same(value['owner_before'],value['owner_after']):
        raise ValueError('selector_owner_changed')
    integer(value['last_hil_us'],2**64-1)
    if value['last_hil_us']!=(query['checkpoint']-1)*4000:
        raise ValueError('selector_event_hil')
    physical._time(value['fdm_time_s'], query['checkpoint'])
    for name in ('wall_start_ns','wall_end_ns'):
        integer(value[name])
    if not 0<=value['wall_end_ns']-value['wall_start_ns']<=200000000:
        raise ValueError('selector_client_time')
    expected = parse_native(query,value['stdout'],value['stderr'],value['returncode'],layouts)
    if not same(expected,value['observation']):
        raise ValueError('selector_event_projection')
    for item in expected['instances']:
        if item['fields'] is not None and any(item['fields'][n]>value['last_hil_us']
                for n in ('timestamp','timestamp_sample') if n in item['fields']):
            raise ValueError('selector_future_native_time')
    if query['name']=='vehicle_control_mode' and any(i['fields'] is not None and i['fields']['flag_armed']
            for i in expected['instances']):
        raise ValueError('selector_observed_armed')


def _validate(kind, value, layouts=None, binary_dir=None):
    validators = dict(profile=validate_profile, header=validate_header, query=validate_query)
    if kind=='observation':
        validate_event(value, layouts, binary_dir)
    elif kind in validators:
        validators[kind](value)
    else:
        raise ValueError('selector_kind')


def dumps(kind, value, layouts=None, binary_dir=None):
    _validate(kind,value,layouts,binary_dir)
    raw = json.dumps(value,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')
    if len(raw)>262144:
        raise ValueError('selector_json_bytes')
    return raw


def _decode(raw):
    if type(raw) is not bytes or len(raw)>262144:
        raise ValueError('selector_json_bytes')
    def pairs(items):
        value = {}
        for key,item in items:
            if key in value:
                raise ValueError('selector_duplicate_key')
            value[key] = item
        return value
    def number(token):
        if len(token)>21:
            raise ValueError('selector_integer_text')
        return int(token)
    def bad(_):
        raise ValueError('selector_nonfinite_json')
    try:
        return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_int=number,parse_constant=bad)
    except (UnicodeError,RecursionError) as exc:
        raise ValueError('selector_json_encoding') from exc


def loads(kind, raw, layouts=None, binary_dir=None):
    value = _decode(raw)
    _validate(kind,value,layouts,binary_dir)
    return value


def validate_events(events, run_id, layouts, binary_dir, initial_wall_ns=0):
    integer(initial_wall_ns)
    expected = plan(run_id)
    rows,groups,native_times = [],{},{}
    total = 0
    previous = initial_wall_ns
    owner = None
    for event in events:
        if len(rows)>=98:
            raise ValueError('selector_query_count')
        total += len(dumps('observation',event,layouts,binary_dir))+1
        if total>16777216:
            raise ValueError('selector_query_bytes')
        if not same(event['query'],expected[len(rows)]):
            raise ValueError('selector_query_order')
        if owner is not None and not same(owner,event['owner_before']):
            raise ValueError('selector_stream_owner')
        if event['wall_start_ns']<previous or event['wall_end_ns']>initial_wall_ns+60000000000:
            raise ValueError('selector_query_deadline')
        key = (event['query']['checkpoint'],event['query']['kind'])
        first = groups.setdefault(key,event['wall_start_ns'])
        if event['wall_end_ns']-first>400000000:
            raise ValueError('selector_group_time')
        for item in event['observation']['instances']:
            if item['fields'] is not None:
                for name in ('timestamp','timestamp_sample'):
                    if name in item['fields']:
                        key = (event['query']['name'],item['instance'],name)
                        stamp = item['fields'][name]
                        if stamp<native_times.get(key,0):
                            raise ValueError('selector_native_time_regressed')
                        native_times[key] = stamp
        previous = event['wall_end_ns']; owner = event['owner_before']
        rows.append(event)
    if len(rows)!=98:
        raise ValueError('selector_incomplete_queries')
    return rows


def association(events):
    """Stable observed device IDs are not proof of the message the selector consumed."""
    before,after = original._single(events[0]),original._single(events[-1])
    first,last = original._single(events[1]),original._single(events[-2])
    hil = events[0]['last_hil_us']
    result = dict(checkpoint=events[0]['query']['checkpoint'],association_kind='unavailable',
        reason='imu_table_unavailable_or_stale',gyro_slot=None,accel_slot=None,
        sensors_before_timestamp_us=before['timestamp'] if before is not None else None,
        sensors_after_timestamp_us=after['timestamp'] if after is not None else None,
        selector_before_timestamp_us=first['timestamp'] if first is not None else None,
        selector_after_timestamp_us=last['timestamp'] if last is not None else None,
        selector_consumed_imu_timestamp_us=None,exact_source_message_verified=False)
    if (not original._fresh(before,hil,200000) or not original._fresh(after,hil,200000)
            or first is None or last is None):
        return result
    result.update(association_kind='inconsistent',reason='imu_table_changed')
    names = [family+suffix for family in ('gyro','accel') for suffix in ('_device_ids','_device_id_primary')]
    if any(before[n]!=after[n] for n in names):
        return result
    result['reason'] = 'imu_primary_identity'
    for family in ('gyro','accel'):
        device = before[family+'_device_id_primary']
        ids = before[family+'_device_ids']
        if device==0 or ids.count(device)!=1 or any(s[family+'_device_id']!=device for s in (first,last)):
            return result
        result[family+'_slot'] = ids.index(device)
    result['reason'] = 'imu_slot_unhealthy'
    for family in ('gyro','accel'):
        slot = result[family+'_slot']
        if any(not s[family+'_healthy'][slot] or s[family+'_priority'][slot]==0 for s in (before,after)):
            return result
    result['reason'] = 'selector_imu_slot_mismatch'
    for family in ('gyro','accel'):
        for i,device in enumerate(before[family+'_device_ids']):
            if any((s['accumulated_'+family+'_error'][i] is not None)!=(device!=0) for s in (first,last)):
                return result
    result.update(association_kind='observed_stable_ids',reason='')
    return result


def checkpoint_ready(events):
    result = original.checkpoint_ready(events[1:-1])
    linked = association(events)
    before,after = original._single(events[1]),original._single(events[-2])
    if result['ready'] and (before['instances_available']!=after['instances_available']
            or any(s[n] for s in (before,after) for n in ('gyro_fault_detected','accel_fault_detected'))):
        result.update(ready=False,reason='selector_availability_or_fault_changed')
    if result['ready'] and linked['association_kind']!='observed_stable_ids':
        result.update(ready=False,reason=linked['reason'])
    result['association'] = linked
    return result


def evaluate(header, physical_header, records, terminal, events, layouts, binary_dir):
    validate_header(header); physical.validate_header(physical_header); physical.validate_terminal(terminal)
    if any(header[n]!=physical_header[n] or header[n]!=terminal[n] for n in ('run_id','clock_id')):
        raise ValueError('selector_physical_identity')
    last_record = None
    def physical_rows():
        nonlocal last_record
        for row in records:
            last_record = row
            yield row
    stream = physical.validate_steps(physical_header,physical_rows())
    if (terminal['last_step']!=stream['last_step']
            or terminal['wall_ns']<last_record['wall']['fdm_finished_ns']
            or terminal['wall_ns']>physical_header['initial_wall_ns']+60000000000):
        raise ValueError('selector_physical_terminal')
    rows = validate_events(events,header['run_id'],layouts,binary_dir,physical_header['initial_wall_ns'])
    for row in rows:
        context = stream['checkpoints'].get(str(row['query']['checkpoint']))
        if context is None or row['wall_start_ns']<context['wall_ns']:
            raise ValueError('selector_query_before_checkpoint')
        if row['last_hil_us']!=context['last_hil_us'] or row['fdm_time_s']!=context['fdm_time_s']:
            raise ValueError('selector_query_source_context')
        if 'next_hil_sent_ns' in context and row['wall_end_ns']>context['next_hil_sent_ns']:
            raise ValueError('selector_query_after_physical_boundary')
        # The host closes physics immediately after Run 2500, before the last capture.
        final_capture = (row['query']['checkpoint']==2500 and complete_physics(stream,terminal))
        if row['wall_end_ns']>terminal['wall_ns'] and not final_capture:
            raise ValueError('selector_query_after_physical_boundary')
    checkpoints = {str(cp):checkpoint_ready([r for r in rows if r['query']['checkpoint']==cp
        and r['query']['kind']=='topic']) for cp in physical.CHECKPOINTS}
    ready = stream['input_settled'] and all(checkpoints[str(cp)]['ready'] for cp in (2000,2500))
    if ready:
        ready = all(checkpoints['2500'][n]>checkpoints['2000'][n] for n in ('attitude_sample','vehicle_sample'))
    complete = stream['records']==2500 and stream['fdm_successes']==2500 and not stream['terminal']
    ready = bool(ready and complete and terminal['reason'] in ('window_complete','not_ready_at_limit'))
    output = stream['output_chain_observed']
    selectors = [r for r in rows if r['query']['name']=='estimator_selector_status']
    payload_complete = all(r['observation']['state']=='payload' for r in selectors)
    return dict(collection_complete=True,input_settled=stream['input_settled'],initialization_ready=ready,
        output_chain_observed=output,passed=ready and output,selector_payload_complete=payload_complete,
        records=stream['records'],queries=len(rows),checkpoints=checkpoints,stream=stream,
        binding_status='unverified',control_gate_accepted=False)


def complete_physics(stream, terminal):
    return (stream['records']==2500 and stream['fdm_successes']==2500 and not stream['terminal']
        and terminal['reason']=='window_complete')


def _read_file(path, cap):
    with path.open('rb') as stream:
        raw = stream.read(cap+1)
    if len(raw)>cap:
        raise ValueError('selector_file_bytes')
    return raw


def _lines(path, cap, count_cap, total_cap):
    with path.open('rb') as stream:
        total = 0
        for i in range(count_cap+1):
            raw = stream.readline(cap+1)
            if not raw:
                return
            total += len(raw)
            if i>=count_cap or len(raw)>cap or total>total_cap or not raw.endswith(b'\n'):
                raise ValueError('selector_file_bound')
            yield raw


def load_recording(directory, layouts, binary_dir):
    """Read a fixed same-run composition. Wire contents need a separate MAVLink audit."""
    root = Path(directory)
    if root.is_symlink() or root.resolve()!=root.absolute():
        raise ValueError('selector_recording_path')
    query_total = artifact_total = 0
    for path in root.rglob('*'):
        if path.is_symlink():
            # PX4 installs this fixed runtime resource link; it is never recording input.
            runtime_etc = Path(__file__).resolve().parents[2]/'.runtime/build/px4-v1.13.3/etc'
            if path==root/'rootfs/etc' and path.resolve()==runtime_etc:
                continue
            raise ValueError('selector_recording_symlink')
        if path.is_file():
            artifact_total += path.stat().st_size
            if 'selector-queries' in path.relative_to(root).parts:
                query_total += path.stat().st_size
    physical.check_budget(0,0,artifact_bytes=artifact_total,query_bytes=query_total)
    if (root/'queries').exists():
        raise ValueError('selector_mixed_query_profiles')
    header = loads('header',_read_file(root/'selector-header.json',262144))
    required = [root/name for name in PHYSICAL_FILES.values()]
    if not all(path.is_file() for path in required):
        raise ValueError('selector_missing_physical_file')
    physical_header = physical.loads('header',_read_file(root/PHYSICAL_FILES['header'],262144))
    terminal = physical.loads('terminal',_read_file(root/PHYSICAL_FILES['terminal'],262144))
    records = (physical.loads('step',raw) for raw in _lines(root/PHYSICAL_FILES['steps'],16384,2500,67108864))
    events = (loads('observation',raw,layouts,binary_dir)
        for raw in _lines(root/'selector-queries/observations.jsonl',262144,98,16777216))
    # Bound retained wire payloads without pretending to validate MAVLink semantics here.
    wire_bytes = 0
    for raw in _lines(root/PHYSICAL_FILES['wire'],262144,8192,268435456):
        row = _decode(raw)
        fields(row,'direction step_index wall_ns length sent hex')
        integer(row['step_index'],2500,1); integer(row['wall_ns']); integer(row['length'],16777216)
        integer(row['sent'],row['length'],-1)
        if (row['direction'] not in ('tx','rx') or type(row['hex']) is not str
                or len(row['hex'])!=row['length']*2 or not re.fullmatch('[0-9a-f]*',row['hex'])):
            raise ValueError('selector_wire_envelope')
        wire_bytes += row['length']
        if wire_bytes>16777216:
            raise ValueError('selector_wire_bytes')
    return evaluate(header,physical_header,records,terminal,events,layouts,binary_dir)
