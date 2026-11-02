"""New query envelopes and offline readiness evaluation; no daemon client."""
import re

from .flight_probe_contract import (MESSAGE_FILES, _native_field, fields, integer,
    layouts_from_texts as old_layouts, same, text, validate_owner)
from .flight_probe_diagnostic import _block
from .flight_probe_quality import _status_block
from .flight_initialization_contract import (CHECKPOINTS, PARAMETERS, PREFIX, TOPICS, argv_for,
    bounded, gate, identity, norm, plan, validate_query, validate_steps)


def layouts_from_texts(texts, frozen):
    if set(texts) != set(MESSAGE_FILES)|{'vehicle_land_detected'} or texts != frozen:
        raise ValueError('initialization_native_sources_changed')
    layouts = old_layouts({name:texts[name] for name in MESSAGE_FILES})
    layout = {}
    for line in texts['vehicle_land_detected'].splitlines():
        line = line.split('#',1)[0].strip()
        if not line:
            continue
        match = re.fullmatch(r'(uint64|bool) ([a-z][a-z0-9_]*)',line)
        if not match or match[2] in layout:
            raise ValueError('initialization_land_layout')
        layout[match[2]] = (match[1],1)
    if not layout:
        raise ValueError('initialization_land_layout')
    layouts['vehicle_land_detected'] = layout
    return layouts


def parse_native(query, stdout, stderr, returncode, layouts):
    validate_query(query)
    text(stdout,32768,raw=True); text(stderr,32768,raw=True)
    integer(returncode,255,-255)
    if returncode or stderr or len(stdout.encode())+len(stderr.encode()) > 32768:
        raise ValueError('initialization_client_error')
    if any(ord(c)<32 and c!='\n' for c in stdout):
        raise ValueError('initialization_native_control')
    lines = [line for line in stdout.split('\n') if line]
    if query['kind'] == 'parameter':
        name,kind,expected = next(p for p in PARAMETERS if p[0]==query['name'])
        token = r'-?[0-9]{1,11}' if kind=='int32' else r'-?[0-9]{1,40}\.[0-9]{4}'
        if len(lines) != 3 or lines[0] != 'Symbols: x = used, + = saved, * = unsaved':
            raise ValueError('initialization_parameter_text')
        match = re.fullmatch(r'[ x] [ +*] '+re.escape(name)+r' \[-?[0-9]+,[0-9]+\] : ('+token+')',lines[1])
        if not match or not re.fullmatch(r' [0-9]+/[0-9]+ parameters used\.',lines[2]):
            raise ValueError('initialization_parameter_text')
        value = _native_field(match[1],name,kind,1)
        if not same(value,expected):
            raise ValueError('initialization_parameter_mismatch')
        return dict(state='payload',reason='',instances=[],parameter=dict(kind=kind,value=value))
    topic = query['name']
    if lines == ['never published']:
        return dict(state='not_published',reason='native_not_published',instances=[],parameter=None)
    if not lines:
        raise ValueError('initialization_native_empty')
    def block(body, instance):
        if topic == 'estimator_status':
            return _status_block(body,layouts[topic],instance)
        result = _block(body,topic,layouts[topic],instance)
        result['unavailable_fields'] = []
        return result
    if lines[0] == 'TOPIC: '+topic:
        instances = [block(lines[1:],None)]
    else:
        header = re.fullmatch(r'TOPIC: '+re.escape(topic)+r' ([2-9]) instances',lines[0])
        if not header:
            raise ValueError('initialization_native_header')
        blocks = []
        for line in lines[1:]:
            marker = re.fullmatch(r'Instance ([0-8]):',line)
            if marker:
                blocks.append((int(marker[1]),[]))
            elif blocks:
                blocks[-1][1].append(line)
            else:
                raise ValueError('initialization_native_instance')
        ids = [i for i,_ in blocks]
        if len(ids) != int(header[1]) or ids != sorted(set(ids)):
            raise ValueError('initialization_native_instance')
        instances = [block(body,i) for i,body in blocks]
    states = {i['state'] for i in instances}
    if 'payload_unavailable' in states:
        state,reason = 'payload_unavailable','native_payload_unavailable'
    elif 'payload_quality_unavailable' in states:
        state,reason = 'payload_quality_unavailable','native_optional_quality_unavailable'
    else:
        state,reason = 'payload',''
    return dict(state=state,reason=reason,instances=instances,parameter=None)


def validate_event(value, layouts, binary_dir):
    bounded(value)
    fields(value,'schema_version query argv owner_before owner_after last_hil_us fdm_time_s '
        'wall_start_ns wall_end_ns returncode stdout stderr observation binding_status control_gate_accepted')
    if value['schema_version'] != PREFIX+'observation.v1':
        raise ValueError('initialization_event_version')
    query = value['query']
    validate_query(query); gate(value)
    if not same(value['argv'],argv_for(binary_dir,query)):
        raise ValueError('initialization_argv')
    for name in ('owner_before','owner_after'):
        validate_owner(value[name],binary_dir,query['run_id'])
    if not same(value['owner_before'],value['owner_after']):
        raise ValueError('initialization_owner_changed')
    integer(value['last_hil_us'],2**64-1)
    if value['last_hil_us'] != (query['checkpoint']-1)*4000:
        raise ValueError('initialization_event_hil')
    from .flight_initialization_contract import _time
    _time(value['fdm_time_s'],query['checkpoint'])
    for name in ('wall_start_ns','wall_end_ns'):
        integer(value[name])
    if not 0 <= value['wall_end_ns']-value['wall_start_ns'] <= 200000000:
        raise ValueError('initialization_client_time')
    expected = parse_native(query,value['stdout'],value['stderr'],value['returncode'],layouts)
    if not same(value['observation'],expected):
        raise ValueError('initialization_event_projection')
    for item in expected['instances']:
        if item['fields'] is not None:
            if any(item['fields'][n] > value['last_hil_us']
                    for n in ('timestamp','timestamp_sample') if n in item['fields']):
                raise ValueError('initialization_future_native_time')
    if query['name'] == 'vehicle_control_mode' and any(i['fields'] is not None and i['fields']['flag_armed']
            for i in expected['instances']):
        raise ValueError('initialization_observed_armed')


def validate_events(events, run_id, layouts, binary_dir, initial_wall_ns=0):
    from .flight_initialization_contract import dumps
    expected = plan(run_id)
    rows,groups = [],{}
    total = 0
    owner = None
    native_times = {}
    previous = initial_wall_ns
    for event in events:
        if len(rows) >= 84:
            raise ValueError('initialization_query_count')
        total += len(dumps('observation',event,layouts,binary_dir))+1
        if total > 16777216:
            raise ValueError('initialization_queries_bytes')
        if not same(event['query'],expected[len(rows)]):
            raise ValueError('initialization_query_order')
        if owner is not None and not same(owner,event['owner_before']):
            raise ValueError('initialization_stream_owner')
        if event['wall_start_ns'] < previous or event['wall_end_ns'] > initial_wall_ns+60000000000:
            raise ValueError('initialization_query_deadline')
        key = (event['query']['checkpoint'],event['query']['kind'])
        first = groups.setdefault(key,event['wall_start_ns'])
        if event['wall_end_ns']-first > 400000000:
            raise ValueError('initialization_group_time')
        for item in event['observation']['instances']:
            if item['fields'] is not None:
                for name in ('timestamp','timestamp_sample'):
                    if name in item['fields']:
                        key = (event['query']['name'],item['instance'],name)
                        stamp = item['fields'][name]
                        if key in native_times and stamp < native_times[key]:
                            raise ValueError('initialization_native_time_regressed')
                        native_times[key] = stamp
        previous = event['wall_end_ns']; owner = event['owner_before']
        rows.append(event)
    if len(rows) != 84:
        raise ValueError('initialization_incomplete_queries')
    return rows


def load_observations(path, run_id, layouts, binary_dir, initial_wall_ns=0):
    from pathlib import Path
    from .flight_initialization_contract import loads
    with Path(path).open('rb') as stream:
        def records():
            total = 0
            for count in range(85):
                raw = stream.readline(262145)
                if not raw:
                    return
                total += len(raw)
                if count >= 84 or total > 16777216 or not raw.endswith(b'\n'):
                    raise ValueError('initialization_observation_file_bound')
                yield loads('observation',raw,layouts,binary_dir)
        return validate_events(records(),run_id,layouts,binary_dir,initial_wall_ns)


def _single(event):
    items = event['observation']['instances']
    return items[0]['fields'] if len(items)==1 else None


def _instance(event, instance):
    return next((i['fields'] for i in event['observation']['instances'] if i['instance']==instance),None)


def _fresh(fields, hil, age):
    if fields is None:
        return False
    return all(type(fields[n]) is int and 0 < fields[n] <= hil and hil-fields[n] <= age
        for n in ('timestamp','timestamp_sample') if n in fields)


def checkpoint_ready(events):
    """The two selector reads constrain identity only; they are not an atomic snapshot."""
    selector,imu,status,flags,attitude,vehicle,mode,controls,outputs,land,last = events
    before,after = _single(selector),_single(last)
    hil = selector['last_hil_us']
    if not _fresh(before,hil,1200000) or not _fresh(after,hil,1200000):
        return dict(ready=False,reason='selector_unavailable_or_stale')
    names = ('primary_instance','instance_changed_count','accel_device_id','gyro_device_id','mag_device_id','baro_device_id')
    if any(before[n] != after[n] for n in names):
        return dict(ready=False,reason='selector_changed')
    primary = before['primary_instance']
    if not 0 <= primary < min(before['instances_available'],after['instances_available'],9):
        return dict(ready=False,reason='primary_out_of_range')
    state,alignment,pose = _instance(status,primary),_instance(flags,primary),_instance(attitude,primary)
    selected,control,landed = _single(vehicle),_single(mode),_single(land)
    if (not _fresh(state,hil,200000) or not _fresh(alignment,hil,1200000)
            or not _fresh(pose,hil,20000) or not _fresh(selected,hil,20000)
            or not _fresh(control,hil,1200000) or not _fresh(landed,hil,1200000)):
        return dict(ready=False,reason='state_pose_or_land_unavailable_stale')
    devices = ('accel_device_id','gyro_device_id','mag_device_id','baro_device_id')
    if any(state[n] != before[n] or state[n] == 0 for n in devices):
        return dict(ready=False,reason='primary_device_mismatch')
    imus = [i['fields'] for i in imu['observation']['instances'] if i['fields'] is not None]
    if not any(_fresh(i,hil,200000) and all(i[n]==before[n] for n in ('accel_device_id','gyro_device_id')) for i in imus):
        return dict(ready=False,reason='imu_device_or_age')
    ready = (state['filter_fault_flags']==0 and alignment['cs_tilt_align'] and alignment['cs_yaw_align']
        and before['healthy'][primary] and after['healthy'][primary] and landed['landed'] and landed['at_rest']
        and not control['flag_armed'] and abs(norm(pose['q'])-1)<=.001 and abs(norm(selected['q'])-1)<=.001)
    return dict(ready=bool(ready),reason='' if ready else 'alignment_health_land_or_pose',primary=primary,
        attitude_sample=pose['timestamp_sample'],vehicle_sample=selected['timestamp_sample'],
        controls_observed=_single(controls) is not None,outputs_observed=_single(outputs) is not None)


def evaluate(header, records, events, layouts, binary_dir):
    stream = validate_steps(header,records)
    rows = validate_events(events,header['run_id'],layouts,binary_dir,header['initial_wall_ns'])
    for row in rows:
        context = stream['checkpoints'].get(str(row['query']['checkpoint']))
        if context is None or row['wall_start_ns'] < context['wall_ns']:
            raise ValueError('initialization_query_before_checkpoint')
        if row['last_hil_us'] != context['last_hil_us'] or row['fdm_time_s'] != context['fdm_time_s']:
            raise ValueError('initialization_query_source_context')
        # Captures happen before the next next/Run, including the first parameter group.
        if 'next_hil_sent_ns' in context and row['wall_end_ns'] > context['next_hil_sent_ns']:
            raise ValueError('initialization_query_after_next_step')
    checkpoints = {}
    for step in (2000,2500):
        group = [r for r in rows if r['query']['checkpoint']==step and r['query']['kind']=='topic']
        checkpoints[str(step)] = checkpoint_ready(group)
    ready = stream['input_settled'] and all(c['ready'] for c in checkpoints.values())
    if ready:
        first,last = checkpoints['2000'],checkpoints['2500']
        ready = all(last[n]>first[n] for n in ('attitude_sample','vehicle_sample'))
    output = stream['output_chain_observed']
    return dict(collection_complete=True,input_settled=stream['input_settled'],initialization_ready=ready,
        output_chain_observed=output,passed=ready and output,records=stream['records'],queries=len(rows),
        checkpoints=checkpoints,stream=stream,binding_status='unverified',control_gate_accepted=False)
