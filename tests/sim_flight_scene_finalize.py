"""Read-only case/source/budget closeout for explicit flight v2 acceptance evidence."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
CORE=(('normal','flight-scene-normal-20261102T143554316028'),
      ('missing-ir-ack','flight-scene-missing-ir-ack-20261102T144416957631'),
      ('first-missing-ir-ack','flight-scene-first-missing-ir-ack-20261102T144635173445'),
      ('not-ready','flight-scene-not-ready-20261102T144915727879'),
      ('disconnect','flight-scene-disconnect-20261102T145119708230'))
EXPECT={'normal':(10000,10000,100),'missing-ir-ack':(7550,7549,1),
        'first-missing-ir-ack':(7525,7524,0),'not-ready':(7500,7500,0),'disconnect':(126,125,0)}


def size(directory):
    return sum(p.stat().st_size for p in directory.rglob('*') if p.is_file() and not p.is_symlink())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compat',type=Path,nargs=3,required=True)
    parser.add_argument('--regression-log',type=Path,required=True)
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':raise RuntimeError('Radar-Diffusion Python required')
    output=ROOT/'.runtime/runs'/('flight-scene-final-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    output.mkdir();print(output,flush=True)
    cases=[];snapshot=None;products=set();pids=[]
    for label,name in CORE:
        directory=ROOT/'.runtime/runs'/name
        manifest=json.loads((directory/'manifest.json').read_text())
        if (manifest['case']!=label or not manifest['passed'] or manifest['errors'] or
                not manifest['cleanup']['passed'] or manifest['cleanup']['forced'] or
                any(not p['free'] for p in manifest['ports_after']) or
                not all(manifest[k] for k in ('source_unchanged','third_party_unchanged','native_sources_unchanged'))):
            raise ValueError('core case not accepted: '+label)
        before=json.loads((directory/'source-before.json').read_text())
        if snapshot is None:snapshot=before
        if before!=snapshot:raise ValueError('core cases did not share final implementation')
        delivery=json.loads((directory/'delivery-validation.json').read_text())
        if (manifest['physical_steps'],manifest['committed_step'],delivery['bundles'])!=EXPECT[label]:
            raise ValueError('independent core expectation differs')
        for key in ('binding_status','control_gate_accepted'):
            if manifest[key]!=('unverified' if key=='binding_status' else False):raise ValueError('control gate changed')
        for row in manifest['commands']:
            if 'pid' in row:pids.append(row['pid'])
        artifact=size(directory)
        if artifact>512*1024**2 or manifest['wall_seconds']>240:raise ValueError('core budget exceeded')
        receipts=json.loads((directory/'receipts.json').read_text())
        if receipts['wire_bytes']>128*1024**2 or any(len(r)>12288 for r in receipts['rows'].values()):
            raise ValueError('core receipt budget exceeded')
        products.add(manifest['products'])
        cases.append(dict(case=label,directory=str(directory),passed=True,physical_records=manifest['physical_steps'],
            committed_step=manifest['committed_step'],bundles=delivery['bundles'],queries=manifest['queries'],
            wall_seconds=manifest['wall_seconds'],artifact_bytes=artifact,wire_bytes=receipts['wire_bytes']))
    changed=[n for n,v in snapshot.items() if not (ROOT/n).is_file() or (ROOT/n).read_text()!=v]
    if changed:raise ValueError('accepted implementation changed: '+str(changed))
    baseline=json.loads((ROOT/'.runtime/runs/flight-sw03b-oracle-20261102/freeze.json').read_text())
    old_changed=[n for n,v in baseline['sources'].items() if (ROOT/n).read_text()!=v]
    expected_changes={'simulation/gazebo_scene_step.cpp','simulation/ufm_simulation/scene_motion.py',
        'simulation/ufm_simulation/flight_initialization_contract.py','simulation/ufm_simulation/flight_initialization_selector.py',
        'sensors/scene_motion_capture.h','ros_ws/native_scene_rviz.cpp','tests/check_sim_motion_live.py','tests/motion_delivery_checks.py'}
    if set(old_changed)!=expected_changes:raise ValueError('unexpected original source change')
    definitions=[n for n in baseline['sources'] if n.endswith(('.msg','.srv'))]
    if len(definitions)!=25 or any(n in old_changed for n in definitions):raise ValueError('old definitions changed')
    compatibility=[]
    for item in args.compat:
        directory=item.resolve()
        manifest=json.loads((directory/'manifest.json').read_text())
        cleanup=json.loads((directory/'cleanup-audit.json').read_text()) if (directory/'cleanup-audit.json').exists() else manifest.get('cleanup',{})
        accepted=manifest.get('passed',manifest.get('exit')==0)
        if not accepted or manifest.get('errors') or cleanup.get('passed') is False:
            raise ValueError('legacy case not accepted: '+str(directory))
        for build in manifest.get('builds',[]):
            command=build['command']
            if '-o' in command:
                try:Path(command[command.index('-o')+1]).relative_to(ROOT/'.runtime/ros')
                except ValueError as exc:raise ValueError('compatibility build outside .runtime/ros') from exc
        for row in manifest['commands']:
            if 'pid' in row:pids.append(row['pid'])
        compatibility.append(dict(directory=str(directory),passed=True,artifact_bytes=size(directory)))
    remaining=[]
    for pid in sorted(set(pids)):
        path=Path('/proc')/str(pid)/'stat'
        if path.exists():
            try:
                value=path.read_text();state=value[value.rfind(')')+2:].split()[0]
                if state!='Z':remaining.append(pid)
            except FileNotFoundError:pass
    if remaining:raise ValueError('residual case PIDs: '+str(remaining))
    log=args.regression_log.read_text()
    if 'Ran 1130 tests' not in log or not log.rstrip().endswith('OK'):raise ValueError('final regression not accepted')
    attempts=[]
    for directory in sorted((ROOT/'.runtime/runs').glob('flight-scene-*-20261102T*')):
        path=directory/'manifest.json'
        if path.exists():
            m=json.loads(path.read_text())
            attempts.append(dict(directory=str(directory),passed=m['passed'],build_only=m.get('physical_steps',0)==0,
                errors=m['errors'],artifact_bytes=size(directory),wall_seconds=m.get('wall_seconds')))
    artifacts=sum(r['artifact_bytes'] for r in attempts)+sum(r['artifact_bytes'] for r in compatibility)
    artifacts+=sum(size(Path(p)) for p in products)
    core_wall=sum(r['wall_seconds'] for r in cases)
    if artifacts>5*1024**3 or core_wall>2400:raise ValueError('suite budget exceeded')
    report=dict(passed=True,core_cases=cases,compatibility=compatibility,old_definition_count=len(definitions),
        old_sources_changed=old_changed,accepted_source_files=len(snapshot),accepted_source_unchanged=True,
        later_test_helpers=['tests/sim_flight_scene_legacy.py','tests/sim_flight_scene_finalize.py'],
        attempts=attempts,artifact_bytes_with_attempts=artifacts,core_wall_seconds=core_wall,
        pid_count=len(set(pids)),residual_pids=remaining,regression_tests=1130,
        regression_log=str(args.regression_log),binding_status='unverified',control_gate_accepted=False,
        scope='40s observation-only public flight v2 software; no control/flight/PERF acceptance')
    with (output/'report.json').open('x') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({k:v for k,v in report.items() if k not in ('attempts','core_cases','compatibility')},indent=2))
    return 0


if __name__=='__main__':sys.exit(main())
