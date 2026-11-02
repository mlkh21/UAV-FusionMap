"""Freeze independent flight literals before offline validation and real legacy wire."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_fixture import ROOT,cases,expected,header,profile


def save(path,value):
    with Path(path).open('x') as output:
        json.dump(value,output,indent=2,allow_nan=False)
        output.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run=ROOT/'.runtime/runs'/('sim-flight-sw01-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True)
    print(run,flush=True)
    # Save test-owned literals and inputs before importing the validator.
    literals=expected()
    save(run/'independent-expectations.json',literals)
    save(run/'profile.json',profile());save(run/'header.json',header());save(run/'record-inputs.json',cases())
    save(run/'git-state-before.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    from sim_motion_matrix_run import source_snapshot
    baseline=source_snapshot()
    save(run/'source-before.json',baseline)
    from sim_motion_multiscene_run import freeze,verify
    legacy=freeze()
    from ufm_simulation.flight_contract import (capture_step,dumps,loads,map_controls,load_profile,
        load_recording,validate_recording)
    loaded=load_profile(run/'profile.json')
    if loaded['ic']!=literals['ic'] or loaded['actuator_channels']!=literals['channels']:
        raise ValueError('flight differs from saved independent IC or channels')
    records=json.loads((run/'record-inputs.json').read_text())
    roundtrips=[]
    for kind,name,value in [('profile','profile',loaded),('ic','ic',literals['ic']),
            ('header','header',json.loads((run/'header.json').read_text()))]+[
            ('record',name,value) for name,value in records.items()]:
        raw=dumps(kind,value)
        if loads(kind,raw)!=value:raise ValueError('flight offline roundtrip')
        with (run/(name+'.json-wire')).open('xb') as output:output.write(raw)
        roundtrips.append(dict(kind=kind,id=name,bytes=len(raw)))
    for probe in literals['mapping_probes']:
        if map_controls(probe['controls'])!=probe['properties']:raise ValueError('flight signed mapping')
    captures=[i*4000000 for i in range(10001) if capture_step(i)]
    if (len(captures)!=literals['capture_reference']['count'] or
            captures[0]!=literals['capture_reference']['first_timestamp_ns'] or
            captures[-1]!=literals['capture_reference']['last_timestamp_ns']):
        raise ValueError('flight future sampling table differs')
    hdr=json.loads((run/'header.json').read_text())
    rows=[records['bootstrap'],records['disarmed']]
    summary=validate_recording(hdr,iter(rows))
    for key,value in literals['stream_reference'].items():
        if summary[key]!=value:raise ValueError('flight saved stream summary')
    recording=run/'recording.jsonl'
    with recording.open('xb') as output:
        for kind,value in [('header',hdr)]+[('record',r) for r in rows]:output.write(dumps(kind,value)+b'\n')
    replay=load_recording(recording)
    if any(replay[k]!=v for k,v in summary.items()):raise ValueError('flight saved JSONL differs')
    save(run/'recording-validation.json',replay)
    command=[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_sim_flight*.py','-v']
    result=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120.)
    with (run/'targeted.log').open('x') as output:output.write(result.stdout)
    print('\n'.join(result.stdout.strip().splitlines()[-5:]),flush=True)
    compatibility=verify(legacy,full=args.full)
    unchanged=source_snapshot()==baseline
    save(run/'report.json',dict(passed=result.returncode==0 and compatibility and unchanged,python=sys.executable,
        roundtrips=roundtrips,mapping_probes=len(literals['mapping_probes']),capture_schedule_points=len(captures),
        stream=summary,legacy_report=str(legacy/'report.json'),existing_sources_unchanged=len(baseline) if unchanged else False,
        targeted_returncode=result.returncode,full_requested=args.full,runtime_started=False,control_commands_sent=False,
        scope='Offline private contract only; packet timing correspondence remains unverified'))
    return int(result.returncode!=0 or not compatibility or not unchanged)


if __name__=='__main__':sys.exit(main())
