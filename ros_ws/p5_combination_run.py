"""Isolated P5 A/B ROS scenario supervisor; native S09 remains a separate delivery."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import signal
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
sys.path.insert(0,str(ROOT/'application'))
from p5_contract import load_pair,load
from sim01b_runtime import (Processes,configure_environment,install_interrupt_handler,
    probe_ports,python_process_audit,start_master,write_json)


def run_case(directory,case_id,port):
    inputs,expected = load_pair()
    case = next(c for c in inputs['cases'] if c['id']==case_id)
    if case['profile']=='C':
        raise ValueError('S09 belongs to P5-SW-03')
    identity = directory.parent.name+'-'+case_id.lower().replace('.','-')
    for name in ('ros-home','ros-logs'):
        (directory/name).mkdir()
    write_json(directory/'inputs.json',inputs)
    write_json(directory/'independent-expectations.json',expected)
    manifest = dict(run_id=identity,case_id=case_id,python=sys.executable,commands=[],errors=[],passed=False)
    env = configure_environment(directory,port)
    processes = Processes(directory,env,manifest)
    observer = None
    try:
        if any(not row['free'] for row in probe_ports('P5',port)):
            raise RuntimeError('existing port/process preserved')
        start_master(processes,port,time.monotonic()+15.)
        import rospy
        rospy.init_node('p5_source',disable_signals=True)
        from p5_ros_case import Case
        observer = Case(inputs,case,directory,identity,processes)
        observer.start()
        observer.execute()
        from p5_checkpoints import verify_receipts
        answers = next(c for c in load(directory/'independent-expectations.json')['cases'] if c['id']==case_id)
        validation = verify_receipts(answers,load(directory/'event-receipts.json'))
        write_json(directory/'validation.json',validation)
        manifest.update(passed=validation['passed'],checked_values=validation['checked_values'],
            public_counts={k:len(v) for k,v in observer.messages.items()},public_bytes=observer.bytes,
            map_replay_passed=json.loads((directory/'map-replay.json').read_text())['passed'])
        if not validation['passed']:
            manifest['errors'] += [r['event_id']+': '+str(r['errors']) for r in validation['checks'] if not r['passed']]
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise RuntimeError('Python process environment differs')
    except Exception as exc:
        manifest['passed'] = False
        manifest['errors'].append(type(exc).__name__+': '+str(exc))
        if isinstance(exc,subprocess.CalledProcessError):
            manifest['errors'].append(str(exc.stderr))
        if observer is not None:
            write_json(directory/'partial-event-receipts.json',observer.receipts)
    finally:
        if 'python_process_audit' not in manifest:
            manifest['python_process_audit'] = python_process_audit()
        cleanup = processes.cleanup()
        if observer is not None:
            observer.close()
        cleanup['ports'] = probe_ports('P5',port)
        cleanup['passed'] = cleanup['passed'] and all(r['free'] for r in cleanup['ports'])
        write_json(directory/'cleanup-audit.json',cleanup)
        manifest['passed'] = manifest['passed'] and cleanup['passed'] and not manifest['errors']
        write_json(directory/'manifest.json',manifest)
        print(json.dumps(dict(case=case_id,passed=manifest['passed'],errors=manifest['errors'])),flush=True)
    return int(not manifest['passed'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=11721)
    parser.add_argument('--cases',nargs='+')
    parser.add_argument('--case-worker')
    parser.add_argument('--directory',type=Path)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if not 1024 <= args.port <= 65535:
        parser.error('invalid isolated master port')
    install_interrupt_handler()
    if args.case_worker:
        return run_case(args.directory,args.case_worker,args.port)
    inputs,_ = load_pair()
    available = [c['id'] for c in inputs['cases'] if c['profile']!='C']
    selected = available if args.cases is None else args.cases
    if len(set(selected))!=len(selected) or not selected or any(c not in available for c in selected):
        parser.error('select unique A/B case IDs; S09 is deferred')
    directory = ROOT/'.runtime/runs'/('p5-combination-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    directory.mkdir(parents=True,exist_ok=False)
    sources = directory/'sources'
    sources.mkdir()
    for relative in ['ros_ws/p5_combination_run.py','tests/p5_ros_case.py','tests/p5_ros_nodes.py',
            'tests/p5_test_engine.py','tests/p5_checkpoints.py','tests/p5_map_call.py',
            'tests/p5_public_replay.py','tests/p5_contract.py','tests/p5_payloads.py']:
        shutil.copy2(ROOT/relative,sources/Path(relative).name)
    print(directory,flush=True)
    results = []
    for case_id in selected:
        child = directory/case_id
        child.mkdir()
        command = [sys.executable,'-B',str(Path(__file__).resolve()),'--case-worker',case_id,
                   '--directory',str(child),'--port',str(args.port)]
        # A standalone process owns each case's Master and cannot reuse latched state.
        process = subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                   text=True,start_new_session=True)
        try:
            output,_ = process.communicate(timeout=45.)
        except (subprocess.TimeoutExpired,RuntimeError) as exc:
            interrupted = isinstance(exc,RuntimeError)
            # The worker's handler enters its finally block and reaps only its own ROS groups.
            process.send_signal(signal.SIGINT)
            try:
                output,_ = process.communicate(timeout=30.)
            except subprocess.TimeoutExpired:
                manifest = json.loads((child/'manifest.json').read_text())
                for item in reversed(manifest['commands']):
                    pid = item['pid']
                    try:
                        actual = (Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
                        if actual[:len(item['args'])] == [a.encode() for a in item['args']] and os.getpgid(pid)==pid:
                            os.killpg(pid,signal.SIGKILL)
                    except (FileNotFoundError,ProcessLookupError):
                        pass
                os.killpg(process.pid,signal.SIGKILL)
                output,_ = process.communicate(timeout=5.)
                raise RuntimeError('case exceeded graceful cleanup deadline: '+case_id)
            if interrupted:
                raise
        with (child/'supervisor.log').open('x') as stream: stream.write(output)
        manifest = json.loads((child/'manifest.json').read_text())
        results.append(dict(case_id=case_id,passed=process.returncode==0 and manifest['passed'],
                            checked_values=manifest.get('checked_values',0),errors=manifest['errors']))
        print(json.dumps(results[-1]),flush=True)
    report = dict(passed=all(r['passed'] for r in results),selected_cases=len(results),
        full_ab_matrix=selected==available,results=results,
        deferred=[c['id'] for c in inputs['cases'] if c['profile']=='C'],
        checked_values=sum(r['checked_values'] for r in results))
    write_json(directory/'report.json',report)
    print(json.dumps(dict(run=str(directory),passed=report['passed'],cases=len(results))),flush=True)
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
