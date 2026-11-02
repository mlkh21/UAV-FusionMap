"""Test-owned synthetic records and literal expectations; never live sensor input."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY_DIR = ROOT/'.runtime/src/px4-v1.13.3/build/px4_sitl_default/bin'


def expected():
    return json.loads((ROOT/'tests/fixtures/sim_flight_initialization_cases.json').read_text())


def native():
    return json.loads((ROOT/'tests/fixtures/sim_flight_initialization_native.json').read_text())


def profile():
    return json.loads((ROOT/'configs/sim_flight_initialization_fixture.json').read_text())


def header(run_id='initialization-offline-01'):
    literals = expected()
    return dict(schema_version='sim_flight_initialization_recording.v1',run_id=run_id,clock_id='sim:'+run_id,
        profile=profile(),peer=dict(address='127.0.0.1',port=24560,system_id=1,component_id=1),
        initial_wall_ns=0,initial_properties=[0.,0.,0.,0.],
        initial_kinematics=literals['kinematics_reference'],initial_ground=literals['ground_reference'])


def step(index=1, present=False, failed=False, run_id='initialization-offline-01'):
    literals = expected()
    row = literals['step_reference']
    row.update(run_id=run_id,clock_id='sim:'+run_id,step_index=index,source_step=index-1,
        hil_sensor_time_us=(index-1)*4000)
    for phase,offset in (('before',-1),('after',0)):
        row['kinematics_'+phase] = copy.deepcopy(literals['kinematics_reference'])
        row['kinematics_'+phase]['sim_time_s'] = (index+offset)*.004
        row['ground_'+phase] = copy.deepcopy(literals['ground_reference'])
    row['fdm'].update(sim_time_before_s=(index-1)*.004,sim_time_after_s=index*.004)
    row['fdm']['hil_sensor']['time_usec'] = (index-1)*4000
    row['wall'].update(hil_sent_ns=index*1000000,fdm_finished_ns=index*1000000+100)
    if present:
        row.update(has_actuator=True,reason='',actuator=dict(receive_sequence=index-2000,
            peer=header(run_id)['peer'],time_usec=(index-1)*4000+1,flags=1,mode=1,armed=False,controls=[0.]*16))
        row['properties']['requested'] = [0.]*4
        row['wall'].update(actuator_received_ns=index*1000000+10,properties_applied_ns=index*1000000+20)
    if failed:
        row['fdm'].update(ran=False,result=None,sim_time_after_s=(index-1)*.004)
        row['kinematics_after'] = copy.deepcopy(row['kinematics_before'])
        row['ground_after'] = copy.deepcopy(row['ground_before'])
    return row


def steps(present=False):
    # The oracle fixes two observations after step 2000, with strict continuity thereafter.
    for index in range(1,2501):
        yield step(index,present=present and index>2000)


def queries(run_id='initialization-offline-01'):
    literals = expected()
    items = [(125,'parameter',name) for name in literals['parameter_order']]
    items += [(cp,'topic',name) for cp in literals['checkpoints'] for name in literals['topic_order']]
    return [dict(schema_version='sim_flight_initialization_query.v1',run_id=run_id,clock_id='sim:'+run_id,
        checkpoint=cp,query_index=i+1,kind=kind,name=name) for i,(cp,kind,name) in enumerate(items)]


def test_layouts():
    result = {}
    aliases = dict(estimator_attitude='vehicle_attitude',actuator_controls_0='actuator_controls')
    messages = native()['native_messages']
    for topic in set(expected()['topic_order']):
        layout = {}
        for raw in messages[aliases.get(topic,topic)].splitlines():
            raw = raw.split('#',1)[0].strip()
            if not raw or '=' in raw:
                continue
            kind,name = raw.split()
            size = int(kind.split('[')[1][:-1]) if '[' in kind else 1
            layout[name] = (kind.split('[')[0],size)
        result[topic] = layout
    return result


def topic_fields(topic, checkpoint):
    values = {}
    for name,(kind,size) in test_layouts()[topic].items():
        scalar = False if kind=='bool' else 0. if kind=='float32' else 0
        values[name] = [scalar]*size if size>1 else scalar
    stamp = (checkpoint-2)*4000
    for name in ('timestamp','timestamp_sample'):
        if name in values:
            values[name] = stamp
    for name,val in dict(accel_device_id=111,gyro_device_id=222,baro_device_id=333,mag_device_id=444).items():
        if name in values:
            values[name] = val
    if topic == 'estimator_selector_status':
        values.update(primary_instance=0,instances_available=2,healthy=[True]*9)
    elif topic == 'estimator_status':
        values.update(control_mode_flags=3,vel_test_ratio=None,pos_test_ratio=None)
    elif topic == 'estimator_status_flags':
        values.update(cs_tilt_align=True,cs_yaw_align=True,cs_baro_hgt=True)
    elif topic in ('estimator_attitude','vehicle_attitude'):
        values['q'] = [1.,0.,0.,0.]
    elif topic == 'vehicle_land_detected':
        values.update(landed=True,at_rest=True,ground_contact=True)
    return values


def body(topic, values):
    lines = [' '+topic]
    for name,(kind,size) in test_layouts()[topic].items():
        value = values[name]
        def token(item):
            if item is None:
                return 'nan'
            return ('True' if item else 'False') if kind=='bool' else ('%.4f'%item) if kind=='float32' else str(item)
        raw = '['+', '.join(token(i) for i in value)+']' if size>1 else token(value)
        if name == 'control_mode_flags':
            digits = format(value,'032b')
            raw += " (0b"+"'".join(digits[i:i+4] for i in range(0,32,4))+")"
        lines.append('    '+name+': '+raw)
    return '\n'.join(lines)+'\n'


def event(query, unavailable=False, changes=None):
    q = copy.deepcopy(query)
    owner = dict(pid=100,start_ticks=123,executable=str(BINARY_DIR/'px4'),
        rootfs=str(ROOT/'.runtime/runs'/q['run_id']/'rootfs'),socket_path='/tmp/px4-sock-0',
        socket_dev=1,socket_file_ino=2,socket_kernel_ino=3)
    if q['kind']=='parameter':
        data = expected()
        index = data['parameter_order'].index(q['name'])
        token = data['parameter_tokens'][index]
        kind = 'float32' if index==3 else 'int32'
        value = float(token) if index==3 else int(token)
        stdout = 'Symbols: x = used, + = saved, * = unsaved\nx * '+q['name']+' [1,1] : '+token+'\n 7/1590 parameters used.\n'
        observation = dict(state='payload',reason='',instances=[],parameter=dict(kind=kind,value=value))
        argv = [str(BINARY_DIR/'px4-param'),'--instance','0','show',q['name']]
    else:
        topic = q['name']
        argv = [str(BINARY_DIR/'px4-listener'),'--instance','0',topic,'-n','1']
        if unavailable:
            stdout = 'never published\n'
            observation = dict(state='not_published',reason='native_not_published',instances=[],parameter=None)
        else:
            values = topic_fields(topic,q['checkpoint'])
            values.update(changes or {})
            multi = topic in ('estimator_status','estimator_status_flags','estimator_attitude')
            unavailable_fields = [dict(field=name,native_token='nan',reason='native_ratio_source_not_selected')
                for name in ('vel_test_ratio','pos_test_ratio') if values.get(name,0) is None]
            instances = [dict(instance=i if multi else None,state='payload_quality_unavailable' if unavailable_fields else 'payload',
                fields=copy.deepcopy(values),unavailable_fields=copy.deepcopy(unavailable_fields)) for i in range(2 if multi else 1)]
            stdout = ('TOPIC: '+topic+' 2 instances\n'+''.join('Instance %d:\n'%i+body(topic,values) for i in range(2))) if multi else 'TOPIC: '+topic+'\n'+body(topic,values)
            observation = dict(state='payload_quality_unavailable' if unavailable_fields else 'payload',
                reason='native_optional_quality_unavailable' if unavailable_fields else '',instances=instances,parameter=None)
    return dict(schema_version='sim_flight_initialization_observation.v1',query=q,argv=argv,
        owner_before=owner,owner_after=copy.deepcopy(owner),last_hil_us=(q['checkpoint']-1)*4000,
        fdm_time_s=q['checkpoint']*.004,wall_start_ns=q['checkpoint']*1000000+q['query_index']*1000,
        wall_end_ns=q['checkpoint']*1000000+q['query_index']*1000+500,
        returncode=0,stdout=stdout,stderr='',observation=observation,
        binding_status='unverified',control_gate_accepted=False)


def events(unavailable=False):
    return [event(q,unavailable=unavailable and q['kind']=='topic') for q in queries()]
