"""Tests-only saved observations and independent expected JSON, not live FDM input."""
import copy
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def expected():
    return json.loads((ROOT/'tests/fixtures/sim_flight_expectations.json').read_text())


def profile():
    return json.loads((ROOT/'configs/sim_flight_fixture.json').read_text())


def header():
    return dict(schema_version='sim_flight_recording.v1',run_id='flight-offline-01',clock_id='sim:flight-offline-01',
        profile=profile(),peer=dict(address='127.0.0.1',port=24560,system_id=1,component_id=1),
        initial_properties=[0,0,0,0],initial_wall_ns=0)


def record(index=1, *, present=False, armed=False):
    value=copy.deepcopy(expected()['record_reference'])
    value.update(step_index=index,source_step=index-1,hil_sensor_time_us=(index-1)*4000)
    value['fdm'].update(sim_time_before_s=(index-1)*.004,sim_time_after_s=index*.004)
    start=index*10
    value['wall'].update(hil_sent_ns=start,fdm_finished_ns=start+4)
    if present:
        value.update(has_actuator=True,reason='')
        controls=expected()['mapping_probes'][1 if armed else 0]['controls']
        # Deliberately different from sent HIL time: the relationship is unverified.
        value['actuator']=dict(receive_sequence=max(1,index-1),peer=copy.deepcopy(header()['peer']),
            time_usec=value['hil_sensor_time_us']+1,flags=1,mode=129 if armed else 1,armed=armed,controls=controls)
        properties=expected()['mapping_probes'][1 if armed else 0]['properties']
        value['properties'].update(requested=copy.deepcopy(properties),after=copy.deepcopy(properties))
        value['wall'].update(actuator_received_ns=start+1,properties_applied_ns=start+2)
    return value


def cases():
    observed=record(2,present=True)
    failure=record(3,present=True);failure['fdm'].update(result=False,sim_time_after_s=.008)
    stopped=record(3);stopped['fdm'].update(ran=False,result=None,sim_time_after_s=.008)
    return dict(bootstrap=record(),disarmed=observed,armed_probe=record(3,present=True,armed=True),
        fdm_failed=failure,not_run=stopped)
