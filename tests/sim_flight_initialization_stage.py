"""Audit retained real preparation/fault evidence and run compatibility, without retrying normal."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_initialization_fixture import ROOT
from sim_flight_initialization_checks import audit
from sim_motion_matrix_run import source_snapshot

CASES=dict(normal='flight-init-sw02-normal-20261030T115944038112',
    disconnect='flight-init-sw02-disconnect-20261030T120111523545',
    transaction_timeout='flight-init-sw02-transaction-timeout-20261030T120254975810')


def save(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def main():
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run=ROOT/'.runtime/runs'/('flight-init-sw02-stage-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True);print(run,flush=True)
    baseline=source_snapshot();save(run/'source-before.json',baseline)
    save(run/'git-before.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    results={}
    for name,identity in CASES.items():
        path=ROOT/'.runtime/runs'/identity
        manifest=json.loads((path/'manifest.json').read_text())
        result=audit(path)
        if (not manifest['cleanup']['passed'] or manifest['cleanup']['forced']
                or not manifest['source_unchanged'] or not manifest['third_party_unchanged']
                or not all(p['free'] for p in manifest['ports_after'])):raise ValueError('case protection failed')
        before=json.loads((path/'source-before.json').read_text())
        changed=[n for n,v in before.items() if baseline.get(n)!=v]
        if set(changed)-{'ros_ws/sim_flight_initialization_run.py',
                'tests/sim_flight_initialization_checks.py','tests/test_sim_flight_initialization_runtime.py'}:
            raise ValueError('host/query/contract source changed after actual evidence')
        results[name]=dict(directory=str(path),actual=result,manifest_runtime_accepted=manifest['runtime_accepted'],
            later_source_changes=changed,software_checks_passed=manifest['software_checks_passed'])
        save(run/(name+'-audit.json'),results[name])
    normal=results['normal']['actual']
    if normal['records']!=500 or normal['raw_query_files']!=30 or normal['valid_observations']!=29:
        raise ValueError('unexpected normal collection boundary')
    manifest=json.loads((ROOT/'.runtime/runs'/CASES['normal']/'manifest.json').read_text())
    if manifest['errors']!=['probe_native_float']:raise ValueError('normal failure changed')
    from ufm_simulation.flight_initialization_contract import plan
    from ufm_simulation.flight_initialization_observation import layouts_from_texts,parse_native
    path=ROOT/'.runtime/runs'/CASES['normal']
    native=json.loads((path/'native-msg-before.json').read_text())
    formats=layouts_from_texts(native,native)
    raw=json.loads((path/'queries/30-raw.json').read_text())
    try:parse_native(plan(path.name)[29],raw['stdout'],raw['stderr'],raw['returncode'],formats)
    except ValueError as exc:
        if str(exc)!='probe_native_float':raise
    else:raise ValueError('strict selector rejection no longer reproduces')
    source_names=('src/modules/ekf2/EKF2Selector.cpp','src/modules/ekf2/EKF2Selector.hpp',
        'msg/estimator_selector_status.msg','msg/sensors_status_imu.msg')
    save(run/'selector-source-evidence.json',{n:(ROOT/'.runtime/src/px4-v1.13.3'/n).read_text() for n in source_names})
    with (run/'flight-targeted.log').open('x') as stream:
        targeted=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests',
            '-p','test_sim_flight*.py','-v'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
    with (run/'compatibility.log').open('x') as stream:
        compatibility=subprocess.run([sys.executable,'-B',str(ROOT/'tests/sim_flight_stage_run.py'),'--full'],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=660)
    compatibility_path=Path((run/'compatibility.log').read_text().splitlines()[0])/'report.json'
    compatible=compatibility.returncode==0 and json.loads(compatibility_path.read_text())['passed']
    unchanged=source_snapshot()==baseline
    software=(targeted.returncode==0 and compatible and unchanged
        and results['disconnect']['software_checks_passed'] and results['transaction_timeout']['software_checks_passed'])
    result=dict(passed=False,software_regression_and_fault_checks_passed=software,runtime_accepted=False,
        python=sys.executable,cases=results,flight_targeted_returncode=targeted.returncode,
        compatibility_report=str(compatibility_path),compatibility_passed=compatible,
        source_files=len(baseline),source_unchanged=unchanged,normal_retried=False,
        diagnostic_collection_complete=False,normal_failure='selector native NaN at query 30, checkpoint 500',
        binding_status='unverified',control_gate_accepted=False,
        scope='Implementation, partial actual acquisition and fault/compatibility checks; full preparation acceptance failed')
    save(run/'report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2),flush=True)
    return int(not software)


if __name__=='__main__':sys.exit(main())
