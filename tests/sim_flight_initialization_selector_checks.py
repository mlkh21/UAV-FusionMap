"""Independent retained wire/physics/query audit for the selector preparation runs."""
import json
from pathlib import Path
import struct

from pymavlink.dialects.v20 import common
from ufm_simulation import flight_initialization_contract as physical
from ufm_simulation import flight_initialization_selector as contract


def audit(directory):
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((directory/'manifest.json').read_text())
    header = physical.loads('header',(directory/'header.json').read_bytes())
    contract.loads('header',(directory/'selector-header.json').read_bytes())
    path = directory/'diagnostics/steps.jsonl'
    if path.stat().st_size>67108864:raise ValueError('selector audit step budget')
    rows = [json.loads(raw) for raw in path.read_bytes().splitlines()]
    rejected = None
    if manifest['case']=='normal' and manifest['errors']==['initialization_hil_time']:
        last = rows[-1]
        try:physical.validate_step(last)
        except ValueError as exc:
            if str(exc)!='initialization_hil_time':raise
        else:raise ValueError('selector audit missing original rejection')
        if (last['fdm']['ran'] or last['fdm']['result'] is not None
                or last['fdm']['sim_time_before_s']!=last['fdm']['sim_time_after_s']
                or last['kinematics_before']!=last['kinematics_after']
                or last['ground_before']!=last['ground_after']):
            raise ValueError('selector audit rejected time advanced physics')
        physical._time(last['fdm']['sim_time_before_s'],last['source_step'])
        rejected = dict(step=last['step_index'],expected_hil_us=last['source_step']*4000,
            raw_hil_us=last['hil_sensor_time_us'],source_time_s=last['fdm']['sim_time_before_s'],
            reason='initialization_hil_time',accepted=False,ran=False)
    parsers = {direction:common.MAVLink(None) for direction in ('tx','rx')}
    sensors,actuators = {},{}
    counts = {'tx':{},'rx':{}}
    wire_bytes = wire_events = 0
    with (directory/'diagnostics/wire.jsonl').open('rb') as stream:
        for raw in stream:
            if len(raw)>262144:raise ValueError('selector audit wire row')
            item = json.loads(raw);data = bytes.fromhex(item['hex'])
            wire_bytes+=len(data);wire_events+=1
            if wire_bytes>16777216 or wire_events>8192 or len(data)!=item['length']:
                raise ValueError('selector audit wire budget')
            if item['direction']=='tx' and item['sent']!=len(data):raise ValueError('selector audit incomplete send')
            for byte in data:
                message = parsers[item['direction']].parse_char(bytes([byte]))
                if message is None:continue
                name = message.get_type();values = counts[item['direction']]
                values[name] = values.get(name,0)+1
                step = item['step_index']
                if item['direction']=='tx' and name not in ('HIL_SENSOR','HIL_GPS'):
                    raise ValueError('selector audit host command')
                if name=='BAD_DATA':raise ValueError('selector audit malformed wire')
                if item['direction']=='tx' and name=='HIL_SENSOR':
                    if step in sensors:raise ValueError('selector audit repeated HIL')
                    sensors[step] = message
                if item['direction']=='rx' and name=='HIL_ACTUATOR_CONTROLS':
                    if step in actuators:raise ValueError('selector audit repeated actuator')
                    if message.get_srcSystem()!=1 or message.get_srcComponent()!=1:
                        raise ValueError('selector audit peer')
                    actuators[step] = message
    if len(sensors)!=len(rows):raise ValueError('selector audit wire step count')
    deltas = []
    first_actuator = None
    for index,row in enumerate(rows,1):
        if row['step_index']!=index:raise ValueError('selector audit step order')
        sensor = sensors[index]
        if row['hil_sensor_time_us']!=sensor.time_usec or (sensor.time_usec!=(index-1)*4000
                and not (rejected is not None and index==len(rows))):
            raise ValueError('selector audit original timestamp')
        values = row['fdm']['hil_sensor']
        for names,key in [(('xacc','yacc','zacc'),'accel_mps2'),(('xgyro','ygyro','zgyro'),'gyro_radps')]:
            if struct.pack('<3f',*(getattr(sensor,n) for n in names))!=struct.pack('<3f',*values[key]):
                raise ValueError('selector audit sensor float32')
        if row['has_actuator']!=(index in actuators):raise ValueError('selector audit actuator presence')
        if index in actuators:
            message = actuators[index];saved = row['actuator']
            if (message.mode!=1 or message.flags>1 or any(message.controls)
                    or any(saved[k]!=getattr(message,k) for k in ('mode','flags','time_usec'))
                    or struct.pack('<16f',*message.controls)!=struct.pack('<16f',*saved['controls'])):
                raise ValueError('selector audit actuator values')
            if first_actuator is None:first_actuator=index
            deltas.append(message.time_usec-sensor.time_usec)
        for phase in ('before','after'):
            k = row['kinematics_'+phase]
            for src,dst in [('vel_ned_ftps','vel_ned_mps'),('pilot_accel_ftps2','pilot_accel_mps2')]:
                if any(abs(a*.3048-b)>1e-9 for a,b in zip(k[src],k[dst])):
                    raise ValueError('selector audit units')
            for gear in row['ground_'+phase]:
                if abs(gear['compression_lbf']*4.4482216152605-gear['compression_n'])>1e-9:
                    raise ValueError('selector audit force units')
    terminal = physical.loads('terminal',(directory/'diagnostics/terminal.json').read_bytes())
    if terminal['last_step']!=len(rows):raise ValueError('selector audit terminal')
    timeout = manifest['case']=='transaction-timeout'
    accepted_physics = rows[:-1] if timeout or rejected is not None else rows
    summary = physical.validate_steps(header,iter(accepted_physics))
    if manifest['case']!='normal':
        reason = 'transaction_timeout' if timeout else 'peer_closed'
        if (len(rows)!=126 or terminal['reason']!=reason or rows[-1]['fdm']['ran']
                or rows[-1]['fdm']['result'] is not None or abs(rows[-1]['fdm']['sim_time_after_s']-.5)>1e-9):
            raise ValueError('selector audit fault Run')
    baseline = json.loads((directory/'sim_flight_initialization_selector_native.json').read_text())
    messages = json.loads((directory/'native-msg-before.json').read_text())
    layouts = contract.layouts_from_texts(messages,baseline['native_messages'])
    binary = root/'.runtime/build/px4-v1.13.3/bin'
    path = directory/'selector-queries/observations.jsonl'
    observations = [contract.loads('observation',raw,layouts,binary) for raw in path.read_bytes().splitlines()] if path.exists() else []
    planned = contract.plan(directory.name)
    owner = None
    previous = header['initial_wall_ns']
    native_times = {}
    for index,row in enumerate(observations):
        if row['query']!=planned[index]:raise ValueError('selector audit query order')
        if row['wall_start_ns']<previous or owner is not None and row['owner_before']!=owner:
            raise ValueError('selector audit query stream')
        previous=row['wall_end_ns'];owner=row['owner_before']
        source = rows[row['query']['checkpoint']-1]
        if (source['hil_sensor_time_us']!=row['last_hil_us'] or source['fdm']['sim_time_after_s']!=row['fdm_time_s']
                or row['wall_start_ns']<source['wall']['fdm_finished_ns']):
            raise ValueError('selector audit query context')
        if source['step_index']<len(rows) and row['wall_end_ns']>rows[source['step_index']]['wall']['hil_sent_ns']:
            raise ValueError('selector audit query after next HIL')
        raw = json.loads((directory/'selector-queries'/('%02d-raw.json'%row['query']['query_index'])).read_text())
        if any(raw[n]!=row[n] for n in ('argv','returncode','stdout','stderr')):
            raise ValueError('selector audit raw projection')
        for item in row['observation']['instances']:
            if item['fields'] is not None:
                for name in ('timestamp','timestamp_sample'):
                    if name in item['fields']:
                        key=(row['query']['name'],item['instance'],name);stamp=item['fields'][name]
                        if stamp<native_times.get(key,0):raise ValueError('selector audit regressed native time')
                        native_times[key]=stamp
    for path in (directory/'selector-queries').glob('group-*.json'):
        group = json.loads(path.read_text())
        subset = [row for row in observations if row['query']['checkpoint']==group['checkpoint']
            and row['query']['kind']==group['kind']]
        if (len(subset)!=group['queries'] or group['end_ns']>group['deadline_ns']
                or group['end_ns']-group['start_ns']>400000000 or subset[0]['wall_start_ns']<group['start_ns']
                or subset[-1]['wall_end_ns']>group['end_ns']):
            raise ValueError('selector audit query group')
    raw_count = len(list((directory/'selector-queries').glob('*-raw.json')))
    evaluation = None
    if manifest['case']=='normal' and len(rows)==2500 and len(observations)==98:
        evaluation = contract.load_recording(directory,layouts,binary)
        if any(manifest[k]!=v for k,v in evaluation.items()):raise ValueError('selector audit evaluation')
    associations = {}
    for cp in physical.CHECKPOINTS:
        group = [r for r in observations if r['query']['checkpoint']==cp and r['query']['kind']=='topic']
        if len(group)==13:associations[str(cp)]=contract.checkpoint_ready(group)
    return dict(records=len(rows),fdm_runs=sum(row['fdm']['ran'] for row in rows),wire_types=counts,
        wire_bytes=wire_bytes,wire_events=wire_events,actuator_packets=len(actuators),first_actuator_step=first_actuator,
        actuator_minus_hil_us=sorted(set(deltas)),raw_query_count=raw_count,valid_observations=len(observations),
        terminal=terminal,accepted_physics=summary,rejected_raw_step=rejected,
        checkpoints=associations,independent_evaluation=evaluation,
        binding_status='unverified',control_gate_accepted=False)
