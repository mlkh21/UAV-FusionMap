"""Freeze, run the two explicit 1s diagnostics, then verify legacy wire and tests."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_fixture import ROOT
from sim_motion_matrix_run import source_snapshot


def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run=ROOT/'.runtime/runs'/('sim-flight-sw02-stage-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True);print(run,flush=True)
    baseline=source_snapshot();save(run/'source-before.json',baseline)
    for name in ('sim_flight_expectations.json','sim_flight_diagnostic_expectations.json'):
        with (run/name).open('xb') as stream:stream.write((ROOT/'tests/fixtures'/name).read_bytes())
    save(run/'git-before.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    results=[]
    with (run/'flight-targeted.log').open('x') as stream:
        targeted=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests',
            '-p','test_sim_flight*.py','-v'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
    if targeted.returncode:raise RuntimeError('flight targeted failed; see frozen run')
    for case in ('normal','disconnect'):
        with (run/(case+'.log')).open('x') as stream:
            child=subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws/sim_flight_diagnostic_run.py'),
                '--case',case],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
        lines=(run/(case+'.log')).read_text().splitlines()
        directory=Path(lines[0]) if lines else None
        if directory is None or directory.parent!=ROOT/'.runtime/runs':
            raise ValueError('missing isolated diagnostic directory')
        manifest=json.loads((directory/'manifest.json').read_text())
        results.append(dict(case=case,directory=str(directory),returncode=child.returncode,
            passed=manifest['passed'],verification=manifest.get('verification')))
        print(case+': '+str(directory)+' passed='+str(manifest['passed']),flush=True)
    from sim_motion_multiscene_run import freeze,verify
    legacy=freeze();compatible=verify(legacy,full=args.full)
    unchanged=source_snapshot()==baseline
    passed=all(row['passed'] and row['returncode']==0 for row in results) and compatible and unchanged
    save(run/'report.json',dict(passed=passed,python=sys.executable,cases=results,legacy_report=str(legacy/'report.json'),
        flight_targeted_returncode=targeted.returncode,full_requested=args.full,source_files=len(baseline),
        source_unchanged=unchanged,control_gate_accepted=False,
        scope='Only bounded diagnostics and compatibility; actuator readiness and causal binding remain separate'))
    return int(not passed)


if __name__=='__main__':sys.exit(main())
