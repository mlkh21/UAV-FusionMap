"""Freeze final source, execute the bounded 9+3 matrix serially, never merge runs."""
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from sim_motion_fixture import ROOT

PYTHON='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python'
ORDER=['S%02d'%i for i in range(1,10)]+['C01-estimated','C02-static-native','C03-first-ir-fault']


def save(path,value):
    with Path(path).open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def source_snapshot():
    suffixes={'.py','.cpp','.h','.msg','.srv','.json','.yaml','.launch','.sh','.rviz'}
    result={}
    for directory in ('application','configs','mapping','perception','ros_ws','sensors','simulation','tests'):
        for path in sorted((ROOT/directory).rglob('*')):
            if path.is_file() and path.suffix in suffixes and '__pycache__' not in path.parts:
                result[str(path.relative_to(ROOT))]=path.read_text()
    return result


def artifact_bytes(directory):
    return sum(p.stat().st_size for p in Path(directory).rglob('*') if p.is_file() and not p.is_symlink())


def validate_totals(rows,wall_seconds,artifact_total):
    if [row['id'] for row in rows]!=ORDER:raise ValueError('matrix_incomplete_or_reordered')
    if not all(row['passed'] and row['cleanup_passed'] and row['source_unchanged'] for row in rows):
        raise ValueError('matrix_case_not_accepted')
    core=rows[:9]
    if (sum(row['committed_ns'] for row in core)!=8496000000 or
            sum(row['wire_bytes'] for row in core)>144*1024**2 or
            sum(row['session_seconds'] for row in core)>1080 or
            any(row['wire_bytes']>16*1024**2 or row['session_seconds']>120 for row in core)):
        raise ValueError('matrix_core_budget')
    if (wall_seconds>1800 or artifact_total>3*1024**3 or
            any(row['artifact_bytes']>256*1024**2 for row in rows)):
        raise ValueError('matrix_suite_budget')
    return dict(core_cases=9,compatibility_cases=3,committed_source_ns=8496000000,
        core_wire_bytes=sum(row['wire_bytes'] for row in core),
        core_session_seconds=sum(row['session_seconds'] for row in core),wall_seconds=wall_seconds,
        artifact_bytes=artifact_total,limits_passed=True)


def check_processes(manifest):
    pids=[row['pid'] for row in manifest['commands'] if 'pid' in row]
    remaining=[pid for pid in pids if Path('/proc',str(pid)).exists()]
    if remaining:raise ValueError('matrix_residual_child:'+str(remaining))
    return pids


def run_case(directory,case_id,arguments,snapshot,deadline):
    if source_snapshot()!=snapshot:raise ValueError('matrix_source_changed_before_case')
    before=set((ROOT/'.runtime/runs').iterdir())
    command=[PYTHON,'-B',*arguments]
    started=time.monotonic()
    completed_bytes=sum(json.loads(p.read_text())['artifact_bytes'] for p in directory.glob('*-receipt.json'))
    with (directory/(case_id+'.log')).open('x') as output:
        process=subprocess.Popen(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                new=set((ROOT/'.runtime/runs').iterdir())-before
                sizes=[artifact_bytes(p) for p in new if p.is_dir()]
                products=sum(artifact_bytes(ROOT/'.runtime'/p) for p in ('sim-motion-build','sensor-scene-build'))
                if (time.monotonic()>deadline or
                        any(size>256*1024**2 for size in sizes) or
                        completed_bytes+sum(sizes)+products+artifact_bytes(directory)>3*1024**3):
                    raise RuntimeError('matrix_runtime_budget')
                time.sleep(.5)
        except BaseException:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:process.wait(timeout=30.)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10.)
            raise
    new=sorted(set((ROOT/'.runtime/runs').iterdir())-before)
    manifests=[p for p in new if (p/'manifest.json').exists()]
    if len(manifests)!=1:raise ValueError('matrix_case_manifest_count')
    run=manifests[0]
    manifest=json.loads((run/'manifest.json').read_text())
    cleanup=json.loads((run/'cleanup-audit.json').read_text())
    success=manifest.get('passed',manifest.get('exit')==0)
    if process.returncode or not success or not cleanup['passed']:
        raise ValueError('matrix_case_failed:'+str(run))
    unchanged=source_snapshot()==snapshot
    if not unchanged:raise ValueError('matrix_source_changed_during_case')
    for path in (run/'sources').rglob('*') if (run/'sources').is_dir() else []:
        if path.is_file() and path.read_text()!=snapshot[str(path.relative_to(run/'sources'))]:
            raise ValueError('matrix_case_source_differs')
    row=dict(id=case_id,run=str(run),run_id=manifest['run_id'],command=command,passed=True,
        cleanup_passed=True,source_unchanged=True,artifact_bytes=sum(artifact_bytes(p) for p in new),
        primary_artifact_bytes=artifact_bytes(run),created_run_directories=[str(p) for p in new],
        child_pids=check_processes(manifest),supervisor_pid=process.pid,
        command_seconds=time.monotonic()-started)
    if case_id.startswith('S'):
        geometry=json.loads((run/'multiscene-validation.json').read_text())
        delivery=json.loads((run/'delivery-validation.json').read_text())
        validation=json.loads((run/'validation.json').read_text())
        receipts=json.loads((run/'receipts.json').read_text())
        if (not geometry['passed'] or geometry['boundary_exemptions']!=0 or
                not delivery['public_replay_equal'] or not validation['truth_terminal'] or
                receipts['errors'] or any(len(v)>512 for v in receipts['rows'].values())):
            raise ValueError('matrix_case_evidence_failed')
        expected_scans=0 if case_id=='S01' else 5 if case_id=='S08' else 10
        if len(geometry['actual_scan_checks'])!=expected_scans:raise ValueError('matrix_scan_count')
        if case_id=='S09':
            recording=json.loads((run/'public-recording.json').read_text())
            old_id=arguments[arguments.index('--previous-run-id')+1]
            initial=recording['queries'][0]['result']
            rejected=[q for q in recording['queries'] if q['request']['run_id']==old_id]
            if (initial['revision']!=0 or initial['status']!='unavailable' or len(rejected)!=1 or
                    rejected[0]['request']['clock_id']!='sim:'+old_id or
                    rejected[0]['result']['reason']!='run_or_clock_mismatch' or old_id==manifest['run_id']):
                raise ValueError('matrix_recovery_identity_evidence')
            row['previous_run_rejected']=old_id
        if case_id in ('S05','S07'):
            figures=json.loads((run/'figure-validation.json').read_text())
            if not figures['passed']:raise ValueError('matrix_native_not_accepted')
            row['native_views']=len(figures['views'])
        row.update(committed_ns=validation['completed_steps']*4000000,
            session_seconds=manifest['wall_seconds'],wire_bytes=receipts['wire_bytes'],
            scans=len(geometry['actual_scan_checks']),queries=delivery['public_queries'])
    save(directory/(case_id+'-receipt.json'),row)
    print(json.dumps(row),flush=True)
    return row


def main():
    if sys.executable!=PYTHON:raise RuntimeError('Radar-Diffusion Python required')
    started=time.monotonic()
    directory=ROOT/'.runtime/runs'/('sim-motion-sw04c-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    directory.mkdir(parents=True)
    print(directory,flush=True)
    snapshot=source_snapshot()
    save(directory/'final-source.json',snapshot)
    save(directory/'independent-expectations.json',json.loads((ROOT/'tests/fixtures/sim_motion_multiscene_expectations.json').read_text()))
    save(directory/'strict-geometry-expectations.json',json.loads((ROOT/'tests/fixtures/sim_motion_strict_geometry_expectations.json').read_text()))
    save(directory/'matrix-plan.json',dict(order=ORDER,native=['S05','S07'],single_final_source=True,
        no_automatic_retry=True,source_ns=8496000000,wall_seconds=1800,artifact_bytes=3*1024**3))
    save(directory/'git-state.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    rows=[]
    manifest=dict(passed=False,python=sys.executable,supervisor_pid=os.getpid(),rows=rows,errors=[])
    try:
        for case_id in ORDER:
            if case_id.startswith('S'):
                arguments=['ros_ws/sim_motion_multiscene_ros_run.py','--case',case_id]
                if case_id in ('S05','S07'):arguments+=['--native']
                if case_id=='S09':arguments+=['--previous-run-id',rows[-1]['run_id']]
            elif case_id=='C01-estimated':arguments=['ros_ws/sim01_smoke.py','--fixture','--t14-compat']
            elif case_id=='C02-static-native':arguments=['ros_ws/sensor_scene_run.py','--check']
            else:arguments=['ros_ws/sim_motion_delivery_run.py','--no-native','--fault','missing-ir-ack','--fault-step','25']
            rows.append(run_case(directory,case_id,arguments,snapshot,started+1800))
        total=artifact_bytes(directory)+sum(r['artifact_bytes'] for r in rows)
        # Products are shared but counted once, including reused binaries.
        total+=sum(artifact_bytes(ROOT/'.runtime'/p) for p in ('sim-motion-build','sensor-scene-build'))
        manifest['budgets']=validate_totals(rows,time.monotonic()-started,total)
        manifest['analytic_box_cases']=ORDER[1:9]
        manifest['legacy_geometry_scope']='S01 original sensor/map checks; no cylinder analytic oracle'
        manifest['passed']=True
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__+': '+str(exc))
    finally:
        manifest['wall_seconds']=time.monotonic()-started
        save(directory/'manifest.json',manifest)
        print(json.dumps(dict(run=str(directory),passed=manifest['passed'],errors=manifest['errors'])),flush=True)
    return int(not manifest['passed'])


if __name__=='__main__':sys.exit(main())
