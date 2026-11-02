"""Tests-only private observations; never supplied to the simulator or PX4."""
import json
from pathlib import Path

from ufm_simulation.flight_probe_contract import MESSAGE_FILES,layouts_from_texts,plan,argv_for

ROOT=Path(__file__).resolve().parents[1]
BINARY_DIR=ROOT/'.runtime/build/px4-v1.13.3/bin'
RUN_ID='flight-probe-offline-01'


def expected():
    return json.loads((ROOT/'tests/fixtures/sim_flight_probe_expectations.json').read_text())


def layouts():
    return layouts_from_texts({name:(ROOT/'.runtime/src/px4-v1.13.3/msg'/(name+'.msg')).read_text() for name in MESSAGE_FILES})


def owner():
    return dict(pid=12345,start_ticks=45678,executable=str(BINARY_DIR/'px4'),
        rootfs=str(ROOT/'.runtime/runs'/RUN_ID/'rootfs'),socket_path='/tmp/px4-sock-0',
        socket_dev=1,socket_file_ino=1001,socket_kernel_ino=1002)


def receipt(index=1):
    literals=expected();query=plan(RUN_ID)[index-1]
    if query['kind']=='topic':stdout=literals['missing_text'];result=literals['missing_result']
    else:
        value=literals['parameters'][query['name']]
        stdout='Symbols: x = used, + = saved, * = unsaved\nx   %s [123,456] : %s\n\n 100/1000 parameters used.\n'%(query['name'],value)
        result=dict(observed=True,reason='',value=dict(integer=value))
    start=index*10000000
    return dict(schema_version='sim_flight_uorb_snapshot.v1',query=query,argv=argv_for(BINARY_DIR,query),
        owner_before=owner(),owner_after=owner(),last_hil_us=(query['checkpoint']-1)*4000,
        fdm_time_s=query['checkpoint']*.004,wall_start_ns=start,wall_end_ns=start+1000000,
        returncode=0,stdout=stdout,stderr='',**result,binding_status='unverified',control_gate_accepted=False)
