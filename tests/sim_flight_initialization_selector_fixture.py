"""Independent test literals and synthetic producer; no production parser or plan imports."""
import copy
import json
from pathlib import Path

import sim_flight_initialization_fixture as original

ROOT = original.ROOT
BINARY_DIR = original.BINARY_DIR
RUN_ID = 'selector-offline-01'


def literals():
    return json.loads((ROOT/'tests/fixtures/sim_flight_initialization_selector_cases.json').read_text())


def baseline():
    return json.loads((ROOT/'tests/fixtures/sim_flight_initialization_selector_native.json').read_text())


def profile():
    return json.loads((ROOT/'configs/sim_flight_initialization_selector_fixture.json').read_text())


def header(run_id=RUN_ID):
    return dict(schema_version='sim_flight_initialization_selector_recording.v1',run_id=run_id,
        clock_id='sim:'+run_id,profile=profile(),physical_files=dict(header='header.json',
        steps='diagnostics/steps.jsonl',terminal='diagnostics/terminal.json',wire='diagnostics/wire.jsonl'),
        binding_status='unverified',control_gate_accepted=False)


def queries(run_id=RUN_ID):
    data = literals()
    rows = [(125,'parameter',n) for n in data['parameter_order']]
    rows += [(cp,'topic',n) for cp in data['checkpoints'] for n in data['topic_order']]
    return [dict(schema_version='sim_flight_initialization_selector_query.v1',run_id=run_id,
        clock_id='sim:'+run_id,checkpoint=cp,query_index=i+1,kind=kind,name=name)
        for i,(cp,kind,name) in enumerate(rows)]


def layout(topic):
    name = dict(estimator_attitude='vehicle_attitude',actuator_controls_0='actuator_controls').get(topic,topic)
    result = {}
    for line in baseline()['native_messages'][name].splitlines():
        line = line.split('#',1)[0].strip()
        if not line or '=' in line:
            continue
        kind,field = line.split()
        size = int(kind.split('[')[1][:-1]) if '[' in kind else 1
        result[field] = (kind.split('[')[0],size)
    return result


def values(topic, checkpoint):
    if topic=='sensors_status_imu':
        result = literals()['imu_reference']
        result['timestamp'] = (checkpoint-3)*4000
        return result
    result = original.topic_fields(topic,checkpoint)
    if topic=='estimator_selector_status':
        result.update(primary_instance=1,instances_available=2,healthy=[True,True]+[False]*7,
            combined_test_ratio=[1.,1.]+[None]*7,relative_test_ratio=[0.,0.]+[None]*7,
            accumulated_gyro_error=[None,None,0.,None],accumulated_accel_error=[0.,None,None,None])
    return result


def body(topic, fields):
    rows = [' '+topic]
    for name,(kind,size) in layout(topic).items():
        def token(value):
            if value is None:
                return 'nan'
            if kind=='bool':
                return 'True' if value else 'False'
            return '%.4f'%value if kind=='float32' else str(value)
        value = fields[name]
        raw = '['+', '.join(token(v) for v in value)+']' if size>1 else token(value)
        if name=='control_mode_flags':
            digits = format(value,'032b')
            raw += ' (0b'+"'".join(digits[i:i+4] for i in range(0,32,4))+')'
        rows.append('    '+name+': '+raw)
    return '\n'.join(rows)+'\n'


def event(query, unavailable=False, changes=None):
    q = copy.deepcopy(query)
    topic = q['name']
    if q['kind']=='parameter' or topic not in ('estimator_selector_status','sensors_status_imu'):
        row = original.event(q,unavailable,changes)
        row['schema_version'] = 'sim_flight_initialization_selector_observation.v1'
        return row
    owner = dict(pid=100,start_ticks=123,executable=str(BINARY_DIR/'px4'),
        rootfs=str(ROOT/'.runtime/runs'/q['run_id']/'rootfs'),socket_path='/tmp/px4-sock-0',
        socket_dev=1,socket_file_ino=2,socket_kernel_ino=3)
    if unavailable:
        stdout = 'never published\n'
        observation = dict(state='not_published',reason='native_not_published',instances=[],parameter=None)
    else:
        data = values(topic,q['checkpoint']); data.update(changes or {})
        missing = []
        if topic=='estimator_selector_status':
            for name in ('combined_test_ratio','relative_test_ratio','accumulated_gyro_error','accumulated_accel_error'):
                for i,val in enumerate(data[name]):
                    if val is None:
                        missing.append(dict(field=name,index=i,native_token='nan',reason=
                            'native_estimator_slot_not_seen' if name.endswith('test_ratio') else 'native_imu_slot_unavailable'))
        state = 'payload_quality_unavailable' if missing else 'payload'
        item = dict(instance=None,state=state,fields=data,unavailable_fields=missing)
        observation = dict(state=state,reason='native_optional_quality_unavailable' if missing else '',
            instances=[item],parameter=None)
        stdout = 'TOPIC: '+topic+'\n'+body(topic,data)
    return dict(schema_version='sim_flight_initialization_selector_observation.v1',query=q,
        argv=[str(BINARY_DIR/'px4-listener'),'--instance','0',topic,'-n','1'],
        owner_before=owner,owner_after=copy.deepcopy(owner),last_hil_us=(q['checkpoint']-1)*4000,
        fdm_time_s=q['checkpoint']*.004,wall_start_ns=q['checkpoint']*1000000+q['query_index']*1000,
        wall_end_ns=q['checkpoint']*1000000+q['query_index']*1000+500,returncode=0,stdout=stdout,stderr='',
        observation=observation,binding_status='unverified',control_gate_accepted=False)


def events(unavailable=False, run_id=RUN_ID):
    return [event(q,unavailable=unavailable and q['kind']=='topic') for q in queries(run_id)]


def group(checkpoint=2000):
    return [event(q) for q in queries() if q['checkpoint']==checkpoint and q['kind']=='topic']


def steps(present=False):
    for i in range(1,2501):
        yield original.step(i,present=present and i>2000,run_id=RUN_ID)


def physical_header():
    return original.header(RUN_ID)


def terminal(ready=True):
    return dict(schema_version='sim_flight_initialization_terminal.v1',run_id=RUN_ID,clock_id='sim:'+RUN_ID,
        profile_id='sim-flight-initialization-observe-v1',last_step=2500,
        reason='window_complete' if ready else 'not_ready_at_limit',wall_ns=2501000000,
        binding_status='unverified',control_gate_accepted=False)


def write_dataset(directory, ready=True):
    root = Path(directory)
    root.mkdir()
    (root/'diagnostics').mkdir(); (root/'selector-queries').mkdir()
    def save(name, value):
        with (root/name).open('x') as stream:
            json.dump(value,stream,separators=(',',':'),allow_nan=False)
    save('selector-header.json',header()); save('header.json',physical_header())
    save('diagnostics/terminal.json',terminal(ready))
    # Synthetic physics has no real MAVLink evidence; never fabricate wire packets.
    (root/'diagnostics/wire.jsonl').touch(exist_ok=False)
    for name,rows in [('diagnostics/steps.jsonl',steps(present=ready)),
            ('selector-queries/observations.jsonl',events(unavailable=not ready))]:
        with (root/name).open('xb') as stream:
            for row in rows:
                stream.write(json.dumps(row,separators=(',',':'),allow_nan=False).encode()+b'\n')
