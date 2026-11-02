"""Independent real MAVLink byte/step/query audit, separate from collection."""
import json
from pathlib import Path
import struct

from pymavlink.dialects.v20 import common
from ufm_simulation.flight_initialization_contract import load_recording,loads
from ufm_simulation.flight_initialization_observation import evaluate,layouts_from_texts,load_observations


def audit(directory):
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((directory/'manifest.json').read_text())
    header=loads('header',(directory/'header.json').read_bytes())
    path=directory/'diagnostics/steps.jsonl'
    # Failure raw rows intentionally remain available even if deadline exceeds the accepted contract.
    if path.stat().st_size>67108864:raise ValueError('audit step file budget')
    rows=[json.loads(line) for line in path.read_bytes().splitlines()]
    parsers={d:common.MAVLink(None) for d in ('tx','rx')}
    sensors={};actuators={};types={'tx':{},'rx':{}};wire_bytes=0;wire_count=0
    with (directory/'diagnostics/wire.jsonl').open('rb') as stream:
        for raw in stream:
            if len(raw)>262144:raise ValueError('audit raw wire line')
            wire_count+=1
            item=json.loads(raw);data=bytes.fromhex(item['hex']);wire_bytes+=len(data)
            if wire_bytes>16777216 or wire_count>8192 or len(data)!=item['length']:raise ValueError('audit wire budget')
            if item['direction']=='tx' and item['sent']!=len(data):raise ValueError('audit incomplete send')
            for byte in data:
                message=parsers[item['direction']].parse_char(bytes([byte]))
                if message is None:continue
                name=message.get_type();counts=types[item['direction']];counts[name]=counts.get(name,0)+1
                step=item['step_index']
                if item['direction']=='tx' and name not in ('HIL_SENSOR','HIL_GPS'):raise ValueError('audit host command')
                if name=='HIL_SENSOR' and item['direction']=='tx':
                    if step in sensors:raise ValueError('audit repeated HIL')
                    sensors[step]=message
                if name=='HIL_ACTUATOR_CONTROLS' and item['direction']=='rx':
                    if step in actuators:raise ValueError('audit repeated actuator')
                    if message.get_srcSystem()!=1 or message.get_srcComponent()!=1:raise ValueError('audit actuator peer')
                    actuators[step]=message
    if len(sensors)!=len(rows):raise ValueError('audit sensor count')
    for index,row in enumerate(rows,1):
        if row['step_index']!=index:raise ValueError('audit step sequence')
        sensor=sensors[index]
        if sensor.time_usec!=(index-1)*4000 or row['hil_sensor_time_us']!=sensor.time_usec:raise ValueError('audit original HIL time')
        values=row['fdm']['hil_sensor']
        for names,key in [(('xacc','yacc','zacc'),'accel_mps2'),(('xgyro','ygyro','zgyro'),'gyro_radps')]:
            if struct.pack('<3f',*(getattr(sensor,n) for n in names))!=struct.pack('<3f',*values[key]):
                raise ValueError('audit original sensor float32')
        if row['has_actuator']!=(index in actuators):raise ValueError('audit actuator presence')
        if index in actuators:
            a=actuators[index];saved=row['actuator']
            if any(saved[k]!=getattr(a,k) for k in ('mode','flags','time_usec')):raise ValueError('audit actuator metadata')
            if struct.pack('<16f',*saved['controls'])!=struct.pack('<16f',*a.controls):raise ValueError('audit actuator float32')
        for phase in ('before','after'):
            k=row['kinematics_'+phase]
            for src,dst,scale in [('vel_ned_ftps','vel_ned_mps',.3048),('pilot_accel_ftps2','pilot_accel_mps2',.3048)]:
                if any(abs(a*scale-b)>1e-9 for a,b in zip(k[src],k[dst])):raise ValueError('audit physics units')
            for gear in row['ground_'+phase]:
                if abs(gear['compression_lbf']*4.4482216152605-gear['compression_n'])>1e-9:raise ValueError('audit force units')
    native=json.loads((directory/'native-msg-before.json').read_text())
    frozen=json.loads((directory/'sim_flight_initialization_native.json').read_text())['native_messages']
    formats=layouts_from_texts(native,frozen)
    binary=root/'.runtime/build/px4-v1.13.3/bin'
    evaluation=None
    raw_query_files=sorted((directory/'queries').glob('*-raw.json'))
    query_rows=[]
    if (directory/'queries/observations.jsonl').exists():
        for line in (directory/'queries/observations.jsonl').read_bytes().splitlines():
            query_rows.append(loads('observation',line,formats,binary))
    for row in query_rows:
        source=rows[row['query']['checkpoint']-1]
        if source['hil_sensor_time_us']!=row['last_hil_us'] or source['fdm']['sim_time_after_s']!=row['fdm_time_s']:
            raise ValueError('audit query source context')
        if row['wall_start_ns']<source['wall']['fdm_finished_ns']:raise ValueError('audit query before Run')
        if source['step_index']<len(rows) and row['wall_end_ns']>rows[source['step_index']]['wall']['hil_sent_ns']:
            raise ValueError('audit query after next')
        raw=json.loads((directory/'queries'/('%02d-raw.json'%row['query']['query_index'])).read_text())
        if any(row[k]!=raw[k] for k in ('argv','stdout','stderr','returncode')):raise ValueError('audit query raw projection')
    for p in (directory/'queries').glob('group-*.json'):
        group=json.loads(p.read_text())
        subset=[r for r in query_rows if r['query']['checkpoint']==group['checkpoint'] and r['query']['kind']==group['kind']]
        if (len(subset)!=group['queries'] or group['end_ns']>group['deadline_ns']
                or group['end_ns']-group['start_ns']>400000000
                or subset[0]['wall_start_ns']<group['start_ns'] or subset[-1]['wall_end_ns']>group['end_ns']):
            raise ValueError('audit query group')
    if manifest['case']=='normal' and len(rows)==2500 and len(query_rows)==84:
        reloaded=load_observations(directory/'queries/observations.jsonl',directory.name,formats,binary,header['initial_wall_ns'])
        evaluation=evaluate(header,iter(rows),reloaded,formats,binary)
        if any(evaluation[k]!=manifest[k] for k in evaluation):raise ValueError('audit evaluation differs')
    terminal=loads('terminal',(directory/'diagnostics/terminal.json').read_bytes())
    if terminal['last_step']!=len(rows):raise ValueError('audit terminal last step')
    if manifest['case']!='normal':
        reason='peer_closed' if manifest['case']=='disconnect' else 'transaction_timeout'
        if (len(rows)!=126 or terminal['reason']!=reason or rows[-1]['fdm']['ran']
                or rows[-1]['fdm']['result'] is not None or abs(rows[-1]['fdm']['sim_time_after_s']-.5)>1e-9):
            raise ValueError('audit fault did not stop before Run')
    return dict(wire_types=types,wire_bytes=wire_bytes,wire_events=wire_count,records=len(rows),
        fdm_runs=sum(r['fdm']['ran'] for r in rows),actuator_packets=len(actuators),
        raw_query_files=len(raw_query_files),valid_observations=len(query_rows),terminal=terminal,
        independent_evaluation=evaluation,control_gate_accepted=False,binding_status='unverified')
