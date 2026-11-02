"""Freeze SW-02B expectations, run one explicit probe, then unchanged default diagnostics."""
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
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':raise RuntimeError('Radar-Diffusion Python required')
    run=ROOT/'.runtime/runs'/('sim-flight-sw02b-stage-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True);print(run,flush=True)
    with (run/'independent-probe-expectations.json').open('xb') as stream:
        stream.write((ROOT/'tests/fixtures/sim_flight_probe_expectations.json').read_bytes())
    baseline=source_snapshot();save(run/'source-before.json',baseline)
    save(run/'git-before.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    with (run/'flight-targeted.log').open('x') as stream:
        tests=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_sim_flight*.py','-v'],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
    if tests.returncode:raise RuntimeError('flight targeted failed')
    with (run/'probe.log').open('x') as stream:
        child=subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws/sim_flight_diagnostic_run.py'),'--uorb-probe'],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
    directory=Path((run/'probe.log').read_text().splitlines()[0])
    if directory.parent!=ROOT/'.runtime/runs':raise ValueError('missing isolated probe run')
    manifest=json.loads((directory/'manifest.json').read_text())
    save(run/'probe-result.json',dict(directory=str(directory),returncode=child.returncode,passed=manifest['passed']))
    print('probe: '+str(directory)+' passed='+str(manifest['passed']),flush=True)
    probe_passed=child.returncode==0 and manifest['passed']
    from ufm_simulation.flight_probe_contract import layouts_from_texts,loads,validate_stream,RECORD_BYTES,FILE_BYTES
    binary_dir=ROOT/'.runtime/build/px4-v1.13.3/bin'
    formats=layouts_from_texts(json.loads((directory/'native-msg-before.json').read_text()))
    total=[0]
    def rows():
        with (directory/'uorb-probe/snapshots.jsonl').open('rb') as stream:
            for raw in iter(lambda:stream.readline(RECORD_BYTES+1),b''):
                total[0]+=len(raw)
                if total[0]>FILE_BYTES:raise ValueError('probe file bytes')
                yield loads(raw,formats,binary_dir)
    audited=None
    if probe_passed:
        audited=validate_stream(rows(),manifest['run_id'],formats,binary_dir)
        save(run/'snapshot-reload.json',audited)
    command=[sys.executable,'-B',str(ROOT/'tests/sim_flight_stage_run.py')]+(['--full'] if args.full else [])
    with (run/'compatibility.log').open('x') as stream:
        compatibility=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=660)
    legacy=Path((run/'compatibility.log').read_text().splitlines()[0])
    previous=json.loads((legacy/'report.json').read_text())
    unchanged=source_snapshot()==baseline
    passed=probe_passed and compatibility.returncode==0 and previous['passed'] and unchanged
    save(run/'report.json',dict(passed=passed,python=sys.executable,probe_directory=str(directory),probe=audited,
        probe_passed=probe_passed,probe_errors=manifest['errors'],
        compatibility_passed=compatibility.returncode==0 and previous['passed'],
        compatibility_report=str(legacy/'report.json'),source_files=len(baseline),source_unchanged=unchanged,
        full_requested=args.full,control_gate_accepted=False))
    return int(not passed)


if __name__=='__main__':sys.exit(main())
