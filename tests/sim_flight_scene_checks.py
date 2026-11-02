"""Independent long-window ROS sequence, pixel and original MAVLink byte checks."""
from fractions import Fraction
import json
from pathlib import Path
import struct

import numpy as np
from PIL import Image
from pymavlink.dialects.v20 import common


def validate_live(run,rows,completed,case):
    wanted=[i*4000000 for i in range(completed+1)]
    if [r['timestamp'] for r in rows.get('clock',[])]!=wanted:raise ValueError('flight_public_clock_sequence')
    for kind in ('source','state'):
        valid=[r['value']['header']['timestamp'] for r in rows.get(kind,[]) if r['value']['header']['status']=='valid']
        if valid!=wanted or not rows[kind][-1]['value']['header']['reason'].startswith('terminal:'):
            raise ValueError('flight_'+kind+'_sequence')
    attempted=completed+1 if 'missing-ir-ack' in case else completed
    captures=[s*4000000 for s in range(7525,attempted+1,25)]
    for kind in ('radar','infrared'):
        if ([r['timestamp'] for r in rows.get(kind,[])]!=captures or
                any(not r['finite'] or r['caller']!='/gazebo' for r in rows.get(kind,[]))):
            raise ValueError('flight_'+kind+'_capture_sequence')
    acks=rows.get('ack',[])
    if (len(acks)!=2*len(captures) or {(r['value']['measurement_timestamp'],r['value']['sensor_kind']) for r in acks}
            !={(s,k) for s in captures for k in (1,2)} or any(r['caller']!='/gazebo' or not r['value']['published'] for r in acks)):
        raise ValueError('flight_ack_sequence')
    if [r['value']['step_index'] for r in rows.get('applied',[])]!=list(range(attempted+1)):
        raise ValueError('flight_applied_sequence')
    transforms=[t for r in rows.get('tf',[]) for t in r['transforms']]
    if ([t['timestamp'] for t in transforms]!=wanted or
            any(t['parent']!='odom' or t['child']!='base_link' for t in transforms) or
            any(r['caller']!='/state_adapter' for r in rows.get('tf',[]))):
        raise ValueError('flight_unique_tf_sequence')
    if any(len(rows.get(k,[]))>12288 for k in rows):raise ValueError('flight_receipt_count')
    if captures:
        from check_sim_motion_live import verify_payloads
        payloads=verify_payloads(run,rows,fault=case!='normal',require_ir_change=False)
    else:payloads=None
    return dict(passed=True,completed_steps=completed,clocks=len(wanted),captures=len(captures),acks=len(acks),
        public_source_time_preserved=True,preparation_without_raw=True,tf_unique=True,payloads=payloads)


def verify_figures(directory):
    result=[]
    for stage in ('before','after','history'):
        for view in ('gazebo','rviz'):
            receipt=json.loads((directory/(view+'-'+stage+'.json')).read_text())
            path=Path(receipt['file']);pixels=np.array(Image.open(path).convert('RGB'))
            if min(pixels.shape[:2])<200 or pixels.std()<4:raise ValueError('flight_native_blank')
            if view=='rviz' and (receipt['history']!=(stage=='history') or receipt['raw_displays_enabled']!=(stage!='history')):
                raise ValueError('flight_native_history')
            if view=='rviz' and stage!='history' and (int(receipt.get('infrared_messages','0'))<1
                    or receipt.get('infrared_stamp_ns')!=receipt['clock_ns']):
                raise ValueError('flight_native_infrared_not_current')
            result.append(dict(view=view,stage=stage,file=str(path),size=list(pixels.shape),std=float(pixels.std())))
    for stage in ('before','after'):
        receipt=json.loads((directory/('rviz-'+stage+'.json')).read_text())
        targets=list(directory.glob(Path(receipt['file']).stem+'-viewport-*.png'))
        if len(targets)<2:raise ValueError('flight_native_sensor_targets_missing')
        for path in targets:
            if np.array(Image.open(path)).std()<4:raise ValueError('flight_native_sensor_target_blank')
    return dict(passed=True,images=result,scope='ground observation; no motion/flight claim')


def audit_wire(run):
    rows=[json.loads(raw) for raw in (run/'diagnostics/steps.jsonl').read_bytes().splitlines()]
    parsers={d:common.MAVLink(None) for d in ('tx','rx')}
    sensors={};actuators={};times={};types={'tx':{},'rx':{}}
    for raw in (run/'diagnostics/wire.jsonl').open('rb'):
        item=json.loads(raw);direction=item['direction'];step=item['step_index'];data=bytes.fromhex(item['hex'])
        if len(data)!=item['length'] or (direction=='tx' and item['sent']!=len(data)):raise ValueError('flight_wire_length')
        for byte in data:
            m=parsers[direction].parse_char(bytes([byte]))
            if m is None:continue
            kind=m.get_type();types[direction][kind]=types[direction].get(kind,0)+1
            if direction=='tx':
                if kind not in ('HIL_SENSOR','HIL_GPS'):raise ValueError('flight_host_sent_command')
                key=('hil_sensor' if kind=='HIL_SENSOR' else 'hil_gps',step-1)
                if key in times:raise ValueError('flight_duplicate_source_packet')
                times[key]=m.time_usec
                if kind=='HIL_SENSOR':sensors[step]=m
            elif kind=='HIL_ACTUATOR_CONTROLS':
                if step in actuators or m.get_srcSystem()!=1 or m.get_srcComponent()!=1 or m.mode!=1 or any(m.controls):
                    raise ValueError('flight_bad_actuator_wire')
                actuators[step]=m
    if len(sensors)!=len(rows):raise ValueError('flight_wire_step_count')
    for i,row in enumerate(rows,1):
        m=sensors[i]
        if m.time_usec!=(i-1)*4000 or m.time_usec!=row['hil_sensor_time_us']:raise ValueError('flight_original_hil_time')
        for names,key in ((('xacc','yacc','zacc'),'accel_mps2'),(('xgyro','ygyro','zgyro'),'gyro_radps')):
            if struct.pack('<3f',*(getattr(m,n) for n in names))!=struct.pack('<3f',*row['fdm']['hil_sensor'][key]):
                raise ValueError('flight_original_sensor_float32')
        if row['has_actuator']!=(i in actuators):raise ValueError('flight_actuator_presence')
        if i in actuators:
            a=actuators[i];saved=row['actuator']
            if any(saved[k]!=getattr(a,k) for k in ('mode','flags','time_usec')) or struct.pack('<16f',*saved['controls'])!=struct.pack('<16f',*a.controls):
                raise ValueError('flight_original_actuator_float32')
    receipts={};max_error=0
    for raw in (run/'diagnostics/time-grid.jsonl').open('rb'):
        if len(raw)>256:raise ValueError('flight_time_receipt_size')
        row=json.loads(raw);key=(row['sensor_kind'],row['source_step'])
        error=abs(Fraction(row['source_time_s'])*1000000000-row['source_step']*4000000)
        if (key in receipts or key not in times or error>1 or row['time_usec']!=times[key]
                or row['time_usec']!=row['source_step']*4000
                or row['source_time_s']!=rows[row['source_step']]['fdm']['sim_time_before_s']):
            raise ValueError('flight_original_time_receipt')
        max_error=max(max_error,float(error));receipts[key]=row
    if set(receipts)!=set(times):raise ValueError('flight_source_receipt_coverage')
    return dict(passed=True,physical_records=len(rows),fdm_successes=sum(r['fdm']['result'] is True for r in rows),
        actuator_packets=len(actuators),source_receipts=len(receipts),wire_types=types,max_source_error_ns=max_error,
        source_preserved=True,no_control_commands=True,binding_status='unverified',control_gate_accepted=False)


def audit_run(run):
    from ufm_simulation import flight_initialization_selector as native
    from ufm_simulation.flight_probe_contract import validate_owner
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((run/'manifest.json').read_text())
    if (not manifest['passed'] or not manifest['cleanup']['passed'] or manifest['cleanup']['forced']
            or not all(v['free'] for v in manifest['ports_after'])
            or not all(manifest[k] for k in ('source_unchanged','third_party_unchanged','native_sources_unchanged'))):
        raise ValueError('flight_run_not_accepted_or_clean')
    result=audit_wire(run)
    physical={r['step_index']:r for r in map(json.loads,(run/'diagnostics/steps.jsonl').read_text().splitlines())}
    rows=json.loads((run/'receipts.json').read_text())['rows']
    result['live']=validate_live(run,rows,manifest['committed_step'],manifest['case'])
    frozen=json.loads((run/'sim_flight_initialization_selector_native.json').read_text())
    layouts=native.layouts_from_texts(json.loads((run/'native-msg-before.json').read_text()),frozen['native_messages'])
    expected=json.loads((root/'tests/fixtures/sim_flight_initialization_selector_cases.json').read_text())
    runtime=json.loads((run/'sim_flight_scene_runtime_expectations.json').read_text())
    plan=[(125,'parameter',n) for n in expected['parameter_order']]
    plan += [(s,'topic',n) for s in runtime['checkpoints'] for n in expected['topic_order']]
    files=sorted((run/'readiness').glob('*-event.json'));events=[];owner=None
    for i,path in enumerate(files):
        event=json.loads(path.read_text());q=event['query'];step=q['checkpoint']
        raw=json.loads((path.parent/path.name.replace('-event','-raw')).read_text())
        if (q['schema_version']!='sim_flight_scene_query.v1' or q['run_id']!=run.name or q['clock_id']!='sim:'+run.name
                or q['query_index']!=i+1 or (step,q['kind'],q['name'])!=plan[i]
                or event['binding_status']!='unverified' or event['control_gate_accepted'] is not False):
            raise ValueError('flight_audit_query_identity_order')
        argv=[str(root/'.runtime/build/px4-v1.13.3/bin'/('px4-param' if q['kind']=='parameter' else 'px4-listener')),'--instance','0']
        argv += ['show',q['name']] if q['kind']=='parameter' else [q['name'],'-n','1']
        if event['argv']!=argv or raw['argv']!=argv or any(event[k]!=raw[k] for k in ('returncode','stdout','stderr')):
            raise ValueError('flight_audit_raw_projection')
        decoded=native.parse_native_payload(q['kind'],q['name'],raw['stdout'],raw['stderr'],raw['returncode'],layouts)
        if decoded!=event['observation']:raise ValueError('flight_audit_native_payload')
        for key in ('owner_before','owner_after'):validate_owner(event[key],root/'.runtime/build/px4-v1.13.3/bin',run.name)
        if event['owner_before']!=event['owner_after'] or (owner is not None and owner!=event['owner_before']):
            raise ValueError('flight_audit_owner_changed')
        owner=event['owner_before']
        if (not physical[step]['wall']['fdm_finished_ns']<=event['wall_start_ns']<=event['wall_end_ns']
                or event['wall_end_ns']-event['wall_start_ns']>200000000
                or event['last_hil_us']!=physical[step]['hil_sensor_time_us']
                or event['fdm_time_s']!=physical[step]['fdm']['sim_time_after_s']
                or (step+1 in physical and event['wall_end_ns']>physical[step+1]['wall']['hil_sent_ns'])):
            raise ValueError('flight_audit_query_source_time')
        events.append(event)
    for step in runtime['checkpoints']:
        group=[e for e in events if e['query']['checkpoint']==step and e['query']['kind']=='topic']
        if len(group)==13:
            if group[-1]['wall_end_ns']-group[0]['wall_start_ns']>400000000:raise ValueError('flight_audit_query_group_time')
            ready=native.checkpoint_ready(group)
            if (run/'preparation.json').exists():
                saved=json.loads((run/'preparation.json').read_text())['readiness'][str(step)]
                if saved!=ready:raise ValueError('flight_audit_ready_projection')
    result.update(queries=len(events),query_raw_reparsed=True,query_source_bound=True,
        products=manifest['products'],committed_step=manifest['committed_step'],wall_seconds=manifest['wall_seconds'])
    return result
