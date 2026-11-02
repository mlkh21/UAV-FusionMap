"""Verify frozen independent selector literals and synthetic files; never start a simulator."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_initialization_selector_fixture import (ROOT,BINARY_DIR,RUN_ID,baseline,event,events,
    header,literals,physical_header,profile,queries,write_dataset)
from sim_motion_matrix_run import source_snapshot


def save(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle',type=Path,required=True)
    parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    oracle=args.oracle.resolve()
    oracle_report=json.loads((oracle/'report.json').read_text())
    if not oracle_report['passed'] or oracle_report['new_production_parser_exists']:
        raise ValueError('independent expectations were not frozen before implementation')
    run=ROOT/'.runtime/runs'/('flight-init-selector-sw01-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True);print(run,flush=True)
    snapshot=source_snapshot();save(run/'source-before.json',snapshot)
    save(run/'git-before.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    for name in ('configs/sim_flight_initialization_selector_fixture.json',
            'tests/fixtures/sim_flight_initialization_selector_cases.json',
            'tests/fixtures/sim_flight_initialization_selector_native.json'):
        raw=(ROOT/name).read_bytes()
        if raw!=(oracle/Path(name).name).read_bytes():raise ValueError('saved oracle changed')
        with (run/Path(name).name).open('xb') as stream:stream.write(raw)
    save(run/'query-plan.json',queries())
    for name,ready in (('ready',True),('missing',False)):
        write_dataset(run/name,ready)
    from ufm_simulation import flight_initialization_selector as contract
    from ufm_simulation import flight_initialization_contract as physical
    from ufm_simulation import flight_initialization_observation as original
    from ufm_simulation.flight_probe_quality import SEMANTIC_PATHS
    frozen=baseline();px4=ROOT/'.runtime/src/px4-v1.13.3'
    sources={n:(px4/n).read_text() for n in contract.SELECTOR_SOURCES}
    messages={n:(px4/'msg'/(n+'.msg')).read_text() for n in frozen['native_messages']}
    quality={n:(px4/n).read_text() for n in SEMANTIC_PATHS}
    formats=contract.verify_sources(sources,messages,quality,frozen)
    if contract.plan(RUN_ID)!=json.loads((run/'query-plan.json').read_text()):
        raise ValueError('query plan differs from independent literals')
    rounds=[]
    for kind,value in [('profile',profile()),('header',header()),('query',queries()[0])]+[
            ('observation',r) for r in events()]:
        raw=contract.dumps(kind,value,formats,BINARY_DIR)
        if contract.loads(kind,raw,formats,BINARY_DIR)!=value:raise ValueError('private JSON roundtrip')
        rounds.append(dict(kind=kind,bytes=len(raw)))
    results={}
    for name in ('ready','missing'):
        result=contract.load_recording(run/name,formats,BINARY_DIR)
        for key,expected in literals()['summaries'][name].items():
            if result[key]!=expected:raise ValueError('independent '+name+' '+key)
        save(run/(name+'-result.json'),result);results[name]=result
    raw=json.loads((ROOT/'tests/fixtures/sim_flight_initialization_selector_rejection.json').read_text())
    projected=contract.parse_native(queries()[34],raw['raw']['stdout'],raw['raw']['stderr'],raw['raw']['returncode'],formats)
    if projected['instances'][0]['unavailable_fields']!=literals()['historical_nulls']:
        raise ValueError('historical raw independent nulls')
    try:
        original.parse_native(physical.plan(raw['evidence_run'])[29],raw['raw']['stdout'],
            raw['raw']['stderr'],raw['raw']['returncode'],formats)
    except ValueError as exc:
        if str(exc)!='probe_native_float':raise
    else:raise ValueError('old strict rejection changed')
    save(run/'historical-offline-projection.json',dict(offline_only=True,historical_event_accepted=False,
        original_error='probe_native_float',projection=projected))
    with (run/'flight-targeted.log').open('x') as stream:
        targeted=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests',
            '-p','test_sim_flight*.py','-v'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
    print('flight targeted returncode='+str(targeted.returncode),flush=True)
    if targeted.returncode:raise RuntimeError('flight targeted failed')
    from sim_motion_multiscene_run import freeze,verify
    legacy=freeze();compatible=verify(legacy,full=args.full)
    previous=json.loads((ROOT/'.runtime/runs/flight-init-selector-design01-20261030T121653053407/source-before.json').read_text())
    unchanged=source_snapshot()==snapshot and all(snapshot.get(n)==v for n,v in previous.items())
    if any((px4/n).read_text()!=v for n,v in sources.items()):unchanged=False
    report=dict(passed=compatible and unchanged,python=sys.executable,oracle=str(oracle),
        independent_groups=len(literals()['case_groups']),private_json_roundtrips=len(rounds),roundtrips=rounds,
        synthetic_summaries={name:{key:result[key] for key in literals()['summaries'][name]} for name,result in results.items()},
        synthetic_steps_per_case=2500,queries_per_case=98,raw_historical_nulls=8,old_strict_rejection_preserved=True,
        source_files=len(snapshot),existing_source_files=len(previous),source_unchanged=unchanged,
        new_source_files=sorted(set(snapshot)-set(previous)),targeted_returncode=targeted.returncode,
        legacy_report=str(legacy/'report.json'),full_requested=args.full,
        new_runtime_started=False,control_commands_sent=False,public_messages_changed=False,
        synthetic_wire_packets=0,runtime_accepted=False,binding_status='unverified',control_gate_accepted=False,
        scope='Private offline selector contract and synthetic file composition; no runtime preparation acceptance')
    save(run/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='roundtrips'},indent=2),flush=True)
    return int(not report['passed'])


if __name__=='__main__':sys.exit(main())
