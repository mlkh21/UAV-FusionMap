"""Private bounded PX4 observations. No transport, control permission or ROS imports."""
import json
import copy
import math
from pathlib import Path
import re

TOPICS=('vehicle_imu','estimator_status','estimator_status_flags','estimator_attitude',
    'estimator_selector_status','vehicle_attitude','vehicle_control_mode','actuator_controls_0','actuator_outputs')
PARAMETERS={'SYS_AUTOSTART':1033,'SYS_CTRL_ALLOC':0,'SENS_IMU_MODE':0}
RAW_BYTES=32768
RECORD_BYTES=262144
FILE_BYTES=8388608
CLIENT_NS=200000000
GROUP_NS=400000000
MESSAGE_FILES=('vehicle_imu','estimator_status','estimator_status_flags','vehicle_attitude',
    'estimator_selector_status','vehicle_control_mode','actuator_controls','actuator_outputs')


def integer(value,maximum=2**63-1,minimum=0):
    if type(value) is not int or not minimum<=value<=maximum:raise ValueError('probe_integer')


def text(value,limit,raw=False):
    if type(value) is not str or len(value)>limit:raise ValueError('probe_text_limit')
    try:
        if len(value.encode('utf-8'))>limit:raise ValueError('probe_text_limit')
    except UnicodeError as exc:raise ValueError('probe_text_encoding') from exc
    if any(ord(c)<32 and (not raw or c not in '\n\r\t') for c in value):raise ValueError('probe_text_control')


def bounded(value):
    pending=[(value,0)];nodes=0
    while pending:
        item,depth=pending.pop();nodes+=1
        if nodes>8192 or depth>8:raise ValueError('probe_structure_limit')
        if type(item) is dict:
            if len(item)>256:raise ValueError('probe_object_limit')
            for key,child in item.items():text(key,128);pending.append((child,depth+1))
        elif type(item) is list:
            if len(item)>512:raise ValueError('probe_list_limit')
            pending.extend((child,depth+1) for child in item)
        elif type(item) is str:text(item,RAW_BYTES,raw=True)
        elif type(item) in (int,float):
            try:
                if not math.isfinite(item):raise ValueError('probe_nonfinite')
            except OverflowError as exc:raise ValueError('probe_number_limit') from exc
        elif item is not None and type(item) is not bool:raise ValueError('probe_type')


def fields(value,names):
    if type(value) is not dict or set(value)!=set(names.split()):raise ValueError('probe_fields')


def same(actual,expected):
    if type(actual) is not type(expected):return False
    if type(expected) is dict:return set(actual)==set(expected) and all(same(actual[k],v) for k,v in expected.items())
    if type(expected) is list:return len(actual)==len(expected) and all(same(a,b) for a,b in zip(actual,expected))
    return actual==expected


def plan(run_id):
    text(run_id,120)
    if not re.fullmatch('[A-Za-z0-9_.-]+',run_id):raise ValueError('probe_run_id')
    items=[(checkpoint,'topic',topic) for checkpoint in (125,250) for topic in TOPICS]
    items += [(250,'parameter',name) for name in PARAMETERS]
    return [dict(schema_version='sim_flight_uorb_query.v1',run_id=run_id,clock_id='sim:'+run_id,
        checkpoint=checkpoint,query_index=i+1,kind=kind,name=name)
        for i,(checkpoint,kind,name) in enumerate(items)]


def validate_query(value):
    bounded(value);fields(value,'schema_version run_id clock_id checkpoint query_index kind name')
    integer(value['query_index'],21,1);integer(value['checkpoint'],250,125)
    if value!=plan(value['run_id'])[value['query_index']-1]:raise ValueError('probe_query_plan')


def argv_for(binary_dir,query):
    validate_query(query)
    if query['kind']=='topic':return [str(Path(binary_dir)/'px4-listener'),'--instance','0',query['name'],'-n','1']
    return [str(Path(binary_dir)/'px4-param'),'--instance','0','show',query['name']]


def layouts_from_texts(texts):
    if set(texts)!=set(MESSAGE_FILES):raise ValueError('probe_message_sources')
    parsed={}
    for name,source in texts.items():
        text(source,32768,raw=True);layout={}
        for line in source.splitlines():
            line=line.split('#',1)[0].strip()
            if not line or '=' in line:continue
            match=re.fullmatch(r'(uint(?:8|16|32|64)|int(?:8|16|32|64)|float32|bool)(?:\[([0-9]+)\])?\s+([a-z][a-z0-9_]*)',line)
            if not match:raise ValueError('probe_message_layout')
            kind,size,field=match.groups();size=int(size) if size else 1
            if field in layout or not 1<=size<=512:raise ValueError('probe_message_layout')
            layout[field]=(kind,size)
        if not layout or len(layout)>256:raise ValueError('probe_message_layout')
        parsed[name]=layout
    return {topic:parsed[{'estimator_attitude':'vehicle_attitude','actuator_controls_0':'actuator_controls'}.get(topic,topic)]
        for topic in TOPICS}


def _scalar(raw,kind):
    if kind=='bool':
        if raw not in ('True','False'):raise ValueError('probe_native_boolean')
        return raw=='True'
    if kind=='float32':
        if not re.fullmatch(r'-?[0-9]{1,40}\.[0-9]{4}',raw):raise ValueError('probe_native_float')
        value=float(raw)
        if not math.isfinite(value) or abs(value)>3.403e38:raise ValueError('probe_native_float')
        return value
    if not re.fullmatch(r'-?[0-9]{1,21}',raw):raise ValueError('probe_native_integer')
    value=int(raw);bits=int(kind.lstrip('uint'));signed=kind.startswith('int')
    integer(value,2**(bits-int(signed))-1,-2**(bits-1) if signed else 0)
    return value


def _native_field(raw,field,kind,size):
    suffix=''
    if ' (' in raw:raw,suffix=raw.split(' (',1);suffix='('+suffix
    if suffix:
        if field=='timestamp':pattern=r'\(-?[0-9]+\.[0-9]{6} seconds ago\)'
        elif field=='timestamp_sample':pattern=r'\(-?[0-9]+ us before timestamp\)'
        elif 'flags' in field:pattern=r"\(0b[01']+\)"
        elif 'device_id' in field:pattern=r'\(Type: 0x[0-9A-F]{2}, (?:I2C|SPI|UAVCAN|SIMULATION|SERIAL|MAVLINK|UNKNOWN):[0-9]{1,2} \(0x[0-9A-F]{2}\)\)'
        elif field=='q' or field.startswith('q_'):pattern=r'\(Roll: -?[0-9]+\.[0-9] deg, Pitch: -?[0-9]+\.[0-9] deg, Yaw: -?[0-9]+\.[0-9] deg\)'
        else:raise ValueError('probe_native_annotation')
        if not re.fullmatch(pattern,suffix):raise ValueError('probe_native_annotation')
    if size==1:return _scalar(raw,kind)
    if not raw.startswith('[') or not raw.endswith(']'):raise ValueError('probe_native_array')
    values=raw[1:-1].split(', ')
    if len(values)!=size:raise ValueError('probe_native_array')
    return [_scalar(item,kind) for item in values]


def parse_output(query,stdout,stderr,returncode,layouts):
    validate_query(query);text(stdout,RAW_BYTES,raw=True);text(stderr,RAW_BYTES,raw=True)
    if len(stdout.encode())+len(stderr.encode())>RAW_BYTES:raise ValueError('probe_raw_limit')
    integer(returncode,255,-255)
    if returncode or stderr.strip():raise ValueError('probe_client_error')
    lines=[line for line in stdout.splitlines() if line.strip()]
    if query['kind']=='parameter':
        if len(lines)!=3 or lines[0]!='Symbols: x = used, + = saved, * = unsaved':raise ValueError('probe_parameter_text')
        pattern=r'[ x] [ +*] '+re.escape(query['name'])+r' \[-?[0-9]+,[0-9]+\] : (-?[0-9]{1,11})'
        match=re.fullmatch(pattern,lines[1])
        if not match or not re.fullmatch(r' [0-9]+/[0-9]+ parameters used\.',lines[2]):raise ValueError('probe_parameter_text')
        value=int(match.group(1));integer(value,2**31-1,-2**31)
        return dict(observed=True,reason='',value=dict(integer=value))
    if lines==['never published']:return dict(observed=False,reason='not_published',value=None)
    topic=query['name'];layout=layouts[topic]
    if not lines:raise ValueError('probe_native_empty')
    single=lines[0]=='TOPIC: '+topic
    multi=re.fullmatch(r'TOPIC: '+re.escape(topic)+r' ([2-9]) instances',lines[0])
    if not single and not multi:raise ValueError('probe_native_header')
    instances=[];current=None;body=False
    for line in lines[1:]:
        marker=re.fullmatch(r'Instance ([0-8]):',line)
        if marker:
            if single:raise ValueError('probe_native_instance')
            current=dict(instance=int(marker.group(1)),fields={});instances.append(current);body=False
        elif line==' '+topic:
            if single:
                if current is not None:raise ValueError('probe_native_duplicate')
                current=dict(instance=0,fields={});instances.append(current)
            if current is None or body:raise ValueError('probe_native_body')
            body=True
        else:
            match=re.fullmatch(r'    ([a-z][a-z0-9_]*): (.+)',line)
            if not match or not body or current is None:raise ValueError('probe_native_fields')
            name,raw=match.groups()
            if name not in layout or name in current['fields']:raise ValueError('probe_native_fields')
            current['fields'][name]=_native_field(raw,name,*layout[name])
    if len(instances)!=(1 if single else int(multi.group(1))):raise ValueError('probe_native_count')
    ids=[item['instance'] for item in instances]
    if ids!=sorted(set(ids)):raise ValueError('probe_native_instance')
    if any(set(item['fields'])!=set(layout) for item in instances):raise ValueError('probe_native_incomplete')
    return dict(observed=True,reason='',value=dict(instances=instances))


def validate_owner(value,binary_dir,run_id):
    fields(value,'pid start_ticks executable rootfs socket_path socket_dev socket_file_ino socket_kernel_ino')
    for name in ('pid','start_ticks','socket_dev','socket_file_ino','socket_kernel_ino'):integer(value[name],minimum=1)
    for name in ('executable','rootfs','socket_path'):text(value[name],1024)
    if (value['executable']!=str(Path(binary_dir)/'px4') or value['socket_path']!='/tmp/px4-sock-0'
            or not value['rootfs'].endswith('/'+run_id+'/rootfs')):raise ValueError('probe_owner_identity')


def validate_receipt(value,layouts,binary_dir):
    bounded(value)
    fields(value,'schema_version query argv owner_before owner_after last_hil_us fdm_time_s wall_start_ns wall_end_ns returncode stdout stderr observed reason value binding_status control_gate_accepted')
    if value['schema_version']!='sim_flight_uorb_snapshot.v1':raise ValueError('probe_snapshot_version')
    q=value['query'];validate_query(q)
    if value['argv']!=argv_for(binary_dir,q):raise ValueError('probe_argv')
    for name in ('owner_before','owner_after'):validate_owner(value[name],binary_dir,q['run_id'])
    if value['owner_before']!=value['owner_after']:raise ValueError('probe_owner_changed')
    integer(value['last_hil_us'],2**64-1)
    if type(value['fdm_time_s']) not in (int,float) or abs(value['fdm_time_s']-q['checkpoint']*.004)>1e-9:
        raise ValueError('probe_checkpoint_time')
    for name in ('wall_start_ns','wall_end_ns'):integer(value[name])
    if not 0<=value['wall_end_ns']-value['wall_start_ns']<=CLIENT_NS:raise ValueError('probe_client_time')
    if value['binding_status']!='unverified' or value['control_gate_accepted'] is not False:raise ValueError('probe_control_gate')
    result=parse_output(q,value['stdout'],value['stderr'],value['returncode'],layouts)
    if any(not same(value[name],result[name]) for name in ('observed','reason','value')):
        raise ValueError('probe_output_projection')


def dumps(value,layouts,binary_dir):
    validate_receipt(value,layouts,binary_dir)
    raw=json.dumps(value,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode('utf-8')
    if len(raw)>RECORD_BYTES:raise ValueError('probe_record_bytes')
    return raw


def loads(raw,layouts,binary_dir):
    if type(raw) is not bytes or len(raw)>RECORD_BYTES:raise ValueError('probe_record_bytes')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('probe_duplicate_json_key')
            result[key]=value
        return result
    def bad(_):raise ValueError('probe_nonfinite_json')
    def number(raw):
        if len(raw)>21:raise ValueError('probe_integer_limit')
        return int(raw)
    try:value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_int=number,parse_constant=bad)
    except (UnicodeError,RecursionError) as exc:raise ValueError('probe_json_encoding') from exc
    validate_receipt(value,layouts,binary_dir);return value


def validate_stream(records,run_id,layouts,binary_dir):
    total=0;expected=plan(run_id);seen=[];groups={};previous_end=None
    for row in records:
        if len(seen)>=21:raise ValueError('probe_stream_count')
        raw=dumps(row,layouts,binary_dir);total+=len(raw)+1
        if total>FILE_BYTES:raise ValueError('probe_stream_bytes')
        if row['query']!=expected[len(seen)]:raise ValueError('probe_stream_order')
        if seen and row['owner_before']!=seen[0]['owner_before']:raise ValueError('probe_stream_owner')
        if previous_end is not None and row['wall_start_ns']<previous_end:raise ValueError('probe_stream_time')
        key=(row['query']['checkpoint'],row['query']['kind'])
        first=groups.setdefault(key,row['wall_start_ns'])
        if row['wall_end_ns']-first>GROUP_NS:raise ValueError('probe_group_time')
        if row['query']['kind']=='parameter' and row['value']['integer']!=PARAMETERS[row['query']['name']]:
            raise ValueError('probe_profile_parameter_mismatch')
        if row['query']['name']=='vehicle_control_mode' and row['observed']:
            if any(item['fields']['flag_armed'] for item in row['value']['instances']):raise ValueError('probe_observation_armed')
        seen.append(copy.deepcopy(row));previous_end=row['wall_end_ns']
    if len(seen)!=21:raise ValueError('probe_stream_incomplete')
    return dict(passed=True,queries=21,bytes=total,observed_queries=sum(r['observed'] for r in seen),
        missing_queries=sum(not r['observed'] for r in seen),binding_status='unverified',control_gate_accepted=False)
