"""Freeze test-owned inputs, verify private JSON bytes and actual legacy genpy bytes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_initialization_fixture import (BINARY_DIR, ROOT, events, expected, header,
    native, profile, queries, step, steps)
from sim_motion_matrix_run import source_snapshot


def save(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def input_stream(path, hdr, rows):
    with path.open('xb') as stream:
        for value in (hdr,) if rows is None else rows:
            stream.write(json.dumps(value,separators=(',',':'),allow_nan=False).encode()+b'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run=ROOT/'.runtime/runs'/('flight-init-sw01-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True)
    print(run,flush=True)
    snapshot=source_snapshot()
    save(run/'source-before.json',snapshot)
    save(run/'git-before.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    # Freeze independent literals and input bytes before importing the new validators.
    for name in ('configs/sim_flight_initialization_fixture.json','tests/fixtures/sim_flight_initialization_cases.json',
            'tests/fixtures/sim_flight_initialization_native.json'):
        with (run/Path(name).name).open('xb') as stream:stream.write((ROOT/name).read_bytes())
    save(run/'header.json',header()); save(run/'query-plan.json',queries())
    for name,ready in (('missing',False),('ready',True)):
        with (run/(name+'-input.jsonl')).open('xb') as stream:
            for value in [header()]:
                stream.write(json.dumps(value,separators=(',',':'),allow_nan=False).encode()+b'\n')
            for value in steps(present=ready):
                stream.write(json.dumps(value,separators=(',',':'),allow_nan=False).encode()+b'\n')
        input_stream(run/(name+'-observations-input.jsonl'),None,events(unavailable=not ready))
    from ufm_simulation import flight_initialization_contract as contract
    from ufm_simulation import flight_initialization_observation as observation
    frozen=json.loads((run/'sim_flight_initialization_native.json').read_text())
    actual={name:(ROOT/'.runtime/src/px4-v1.13.3/msg'/(name+'.msg')).read_text() for name in frozen['native_messages']}
    formats=observation.layouts_from_texts(actual,frozen['native_messages'])
    from ufm_simulation.flight_probe_quality import SEMANTIC_PATHS, verify_sources
    verify_sources({n:(ROOT/'.runtime/src/px4-v1.13.3'/n).read_text() for n in SEMANTIC_PATHS},
        {k:v for k,v in actual.items() if k!='vehicle_land_detected'},
        dict(native_messages={k:v for k,v in frozen['native_messages'].items() if k!='vehicle_land_detected'},
            source_regions=frozen['quality_source_regions']))
    literals=json.loads((run/'sim_flight_initialization_cases.json').read_text())
    assert contract.load_profile(run/'sim_flight_initialization_fixture.json')==profile()
    assert contract.plan(literals['run_id'])==json.loads((run/'query-plan.json').read_text())
    rounds=[]
    for kind,value in [('profile',profile()),('header',header()),('step',step()),('query',queries()[0])]+[
            ('observation',r) for r in events()]:
        raw=contract.dumps(kind,value,formats,BINARY_DIR)
        assert contract.loads(kind,raw,formats,BINARY_DIR)==value
        rounds.append(dict(kind=kind,bytes=len(raw)))
    cases={}
    for name in ('missing','ready'):
        path=run/(name+'-input.jsonl')
        loaded=contract.load_recording(path)
        def records():
            with path.open('rb') as stream:
                contract.loads('header',stream.readline(262145))
                for raw in stream:
                    yield contract.loads('step',raw)
        rows=observation.load_observations(run/(name+'-observations-input.jsonl'),
            literals['run_id'],formats,BINARY_DIR)
        result=observation.evaluate(header(),records(),rows,formats,BINARY_DIR)
        for key,value in literals['expected_summaries']['ready' if name=='ready' else 'unavailable'].items():
            if result[key]!=value:raise ValueError('independent '+name+' '+key)
        if name=='missing':
            for key,value in literals['expected_summaries']['missing'].items():
                if loaded[key]!=value:raise ValueError('independent missing stream '+key)
        cases[name]=dict(stream=loaded,evaluation=result)
        save(run/(name+'-result.json'),cases[name])
    with (run/'flight-targeted.log').open('x') as stream:
        targeted=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_sim_flight*.py','-v'],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
    print('flight targeted returncode='+str(targeted.returncode),flush=True)
    from sim_motion_multiscene_run import freeze,verify
    legacy=freeze()
    compatible=verify(legacy,full=args.full)
    previous=json.loads((ROOT/'.runtime/runs/flight-init-design01-20261030T103243156519/source-before.json').read_text())
    unchanged=source_snapshot()==snapshot and all(snapshot.get(n)==v for n,v in previous.items())
    report=dict(passed=targeted.returncode==0 and compatible and unchanged,python=sys.executable,
        oracle_groups=len(literals['independent_case_groups']),private_json_roundtrips=len(rounds),roundtrips=rounds,
        synthetic_cases=cases,queries_per_case=84,steps_per_case=2500,
        targeted_returncode=targeted.returncode,legacy_report=str(legacy/'report.json'),
        source_files=len(snapshot),existing_source_files=len(previous),source_unchanged=unchanged,
        new_source_files=sorted(set(snapshot)-set(previous)),full_requested=args.full,
        new_runtime_started=False,control_commands_sent=False,public_messages_changed=False,
        binding_status='unverified',control_gate_accepted=False,
        scope='Private offline initialization contract and synthetic evaluation; no readiness runtime acceptance')
    save(run/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('synthetic_cases','roundtrips')},indent=2),flush=True)
    return int(not report['passed'])


if __name__=='__main__':sys.exit(main())
