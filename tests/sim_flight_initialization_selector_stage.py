"""Audit explicitly named actual selector runs; do not repeat normal preparation."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_initialization_selector_checks import audit
from sim_flight_initialization_selector_fixture import ROOT
from sim_motion_matrix_run import source_snapshot


def save(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normal',type=Path,required=True)
    parser.add_argument('--disconnect',type=Path,required=True)
    parser.add_argument('--transaction-timeout',type=Path,required=True)
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run=ROOT/'.runtime/runs'/('flight-init-selector-sw02-stage-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True);print(run,flush=True)
    snapshot=source_snapshot();save(run/'source-before.json',snapshot)
    cases={};actual_snapshot=None
    for name,path in [('normal',args.normal),('disconnect',args.disconnect),('transaction-timeout',args.transaction_timeout)]:
        directory=path.resolve()
        if directory.parent!=ROOT/'.runtime/runs':raise ValueError('actual run outside owned runs directory')
        manifest=json.loads((directory/'manifest.json').read_text())
        if manifest['case']!=name:raise ValueError('wrong actual case')
        before=json.loads((directory/'source-before.json').read_text())
        if actual_snapshot is None:actual_snapshot=before
        if before!=actual_snapshot:raise ValueError('actual cases do not share source snapshot')
        later_changes=[n for n,value in before.items() if snapshot.get(n)!=value]
        if set(later_changes)-{'tests/sim_flight_initialization_selector_checks.py',
                'tests/sim_flight_initialization_selector_stage.py','tests/test_sim_flight_initialization_selector_runtime.py'}:
            raise ValueError('production source changed after actual runs')
        if (not manifest['cleanup']['passed'] or manifest['cleanup']['forced']
                or not all(manifest[n] for n in ('source_unchanged','third_party_unchanged','native_msgs_unchanged',
                    'selector_sources_unchanged','quality_sources_unchanged'))
                or not all(p['free'] for p in manifest['ports_after'])):
            raise ValueError('actual protections failed')
        results=audit(directory)
        if name!='normal' and not manifest['software_checks_passed']:raise ValueError('actual fault failed')
        cases[name]=dict(directory=str(directory),audit=results,software_checks_passed=manifest['software_checks_passed'],
            runtime_accepted=manifest['runtime_accepted'],errors=manifest['errors'],later_test_changes=later_changes)
        save(run/(name+'-audit.json'),cases[name])
    with (run/'compatibility.log').open('x') as stream:
        child=subprocess.run([sys.executable,'-B',str(ROOT/'tests/sim_flight_stage_run.py'),'--full'],
            cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=660)
    legacy=Path((run/'compatibility.log').read_text().splitlines()[0])/'report.json'
    compatible=child.returncode==0 and json.loads(legacy.read_text())['passed']
    unchanged=source_snapshot()==snapshot
    accepted=cases['normal']['runtime_accepted']
    software=compatible and unchanged and all(cases[n]['software_checks_passed'] for n in ('disconnect','transaction-timeout'))
    report=dict(passed=bool(accepted and software),software_regression_and_fault_checks_passed=software,
        runtime_accepted=accepted,python=sys.executable,cases=cases,source_files=len(snapshot),source_unchanged=unchanged,
        compatibility_report=str(legacy),normal_retried=False,binding_status='unverified',control_gate_accepted=False,
        scope='Selector preparation actual evidence/fault/compatibility; control and strict binding remain unverified')
    save(run/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2),flush=True)
    return int(not software)


if __name__=='__main__':sys.exit(main())
