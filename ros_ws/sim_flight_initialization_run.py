"""Independent <=10s observation-only preparation; never sends control commands."""
import argparse
from datetime import datetime
import errno
import json
import os
from pathlib import Path
import shutil
import sys
import time

from sim01b_runtime import (Processes,configure_environment,install_interrupt_handler,
    probe_ports,python_process_audit,reject_existing_px4,write_json)
from sim_flight_diagnostic_run import create_ic
from sim_flight_initialization_build import build
from sim_flight_initialization_queries import InitializationQueries
from ufm_simulation.flight_initialization_contract import (CHECKPOINTS,check_budget,dumps,load_profile,loads,
    validate_step,validate_steps)
from ufm_simulation.flight_initialization_observation import evaluate
from ufm_simulation.flight_probe_quality import SEMANTIC_PATHS,verify_sources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('normal','disconnect','transaction-timeout'),default='normal')
    parser.add_argument('--build-only',action='store_true')
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root=Path(__file__).resolve().parents[1]
    run=root/'.runtime/runs'/('flight-init-sw02-'+args.case+'-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True);print(run,flush=True)
    sys.path.insert(0,str(root/'tests'))
    from sim_motion_matrix_run import source_snapshot
    baseline=source_snapshot();write_json(run/'source-before.json',baseline)
    for n in ('rootfs','ros-home','ros-logs'):(run/n).mkdir()
    for n in ('configs/sim_flight_initialization_fixture.json','tests/fixtures/sim_flight_initialization_native.json',
            'tests/fixtures/sim_flight_initialization_cases.json'):
        shutil.copy2(root/n,run/Path(n).name)
    profile=load_profile(run/'sim_flight_initialization_fixture.json')
    frozen=json.loads((run/'sim_flight_initialization_native.json').read_text())
    native={n:(root/'.runtime/src/px4-v1.13.3/msg'/(n+'.msg')).read_text() for n in frozen['native_messages']}
    write_json(run/'native-msg-before.json',native)
    semantic={n:(root/'.runtime/src/px4-v1.13.3'/n).read_text() for n in SEMANTIC_PATHS}
    verify_sources(semantic,{n:v for n,v in native.items() if n!='vehicle_land_detected'},dict(
        native_messages={n:v for n,v in frozen['native_messages'].items() if n!='vehicle_land_detected'},
        source_regions=frozen['quality_source_regions']))
    write_json(run/'quality-source-before.json',semantic)
    bridge=root/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
    originals={str(p.relative_to(root)):p.read_text() for d in ('src','include') for p in (bridge/d).glob('*') if p.is_file()}
    for p in (bridge/'configs/rascal.xml',bridge/'scene/LSZH.xml',bridge/'models/Rascal/Rascal110-JSBSim.xml'):
        originals[str(p.relative_to(root))]=p.read_text()
    write_json(run/'third-party-before.json',originals)
    manifest=dict(run_id=run.name,python=sys.executable,case=args.case,commands=[],errors=[],
        control_commands_sent=False,ros_or_gazebo_started=False,source_limit_steps=2500,
        collection_complete=False,initialization_ready=False,output_chain_observed=False,
        binding_status='unverified',control_gate_accepted=False)
    processes=Processes(run,configure_environment(run,11811),manifest);install_interrupt_handler()
    command=stream=None;operational=False;rows=[];queries=None
    started=initial_ns=None
    try:
        product=build(root,run,manifest)
        if args.build_only:operational=True;return 0
        manifest['ports_before']=probe_ports('LIVE',11811)
        if not all(p['free'] for p in manifest['ports_before']):raise RuntimeError('existing port owner preserved')
        reject_existing_px4()
        create_ic(bridge/'scene/LSZH.xml',run/'initial.xml',profile)
        os.mkfifo(run/'steps.fifo',0o600)
        started=time.monotonic_ns()
        def guard(deadline=None,allow_px4=False):
            now=time.monotonic_ns()
            check_budget(now,started,initial_ns,artifact_bytes=sum(p.stat().st_size for p in run.rglob('*') if p.is_file()))
            if deadline is not None and now>=deadline:raise TimeoutError('preparation deadline')
            processes.check(allowed=('initialization-host','px4') if allow_px4 else ('initialization-host',))
        def wait(predicate,deadline,reason,allow_px4=False):
            while not predicate():
                guard(deadline,allow_px4)
                time.sleep(.01)
            guard(deadline,allow_px4)
        child=processes.spawn('initialization-host',[str(product),str(bridge/'configs/rascal.xml'),str(run/'initial.xml'),
            str(run/'diagnostics'),run.name,str(run/'steps.fifo'),args.case])
        startup=started+60000000000
        wait(lambda:not probe_ports('LIVE',11811)[1]['free'],startup,'host listener missing')
        px4=processes.spawn('px4',[str(root/'.runtime/build/px4-v1.13.3/bin/px4'),'-d',
            str(root/'.runtime/build/px4-v1.13.3/etc'),'-s','etc/init.d-posix/rcS'],run/'rootfs')
        initial_path=run/'diagnostics/initial.json'
        wait(lambda:initial_path.exists() and initial_path.stat().st_size>0,startup,'initial missing')
        initial=json.loads(initial_path.read_text());initial_ns=initial['initial_wall_ns']
        header=dict(schema_version='sim_flight_initialization_recording.v1',run_id=run.name,clock_id='sim:'+run.name,
            profile=profile,**initial)
        with (run/'header.json').open('xb') as output:output.write(dumps('header',header))
        fd=None
        def connected():
            nonlocal fd
            try:fd=os.open(run/'steps.fifo',os.O_WRONLY|os.O_NONBLOCK);return True
            except OSError as exc:
                if exc.errno!=errno.ENXIO:raise
                return False
        wait(connected,startup,'FIFO missing')
        command=os.fdopen(fd,'w',buffering=1)
        stream=(run/'diagnostics/steps.jsonl').open('rb')
        manifest['python_process_audit']=python_process_audit()
        if not manifest['python_process_audit']['passed']:raise RuntimeError('Python process mismatch')
        queries=InitializationQueries(root,run,px4,processes,guard)
        disconnected=False
        for index in range(1,2501):
            guard(allow_px4=disconnected)
            transaction=time.monotonic_ns()+1000000000
            command.write('next\n');raw=b''
            def available():
                nonlocal raw
                raw=stream.readline(16385)
                return bool(raw)
            # A timeout case must stop before Run; the raw host failure may arrive just after this deadline.
            wait(available,transaction,'step timeout',allow_px4=disconnected)
            if len(raw)>16384 or not raw.endswith(b'\n'):raise ValueError('host record bound')
            record=loads('step',raw)
            if record['step_index']!=index:raise ValueError('host skipped step')
            rows.append(record)
            if record['fdm']['result'] is not True:break
            from ufm_simulation.flight_initialization_contract import _safe
            if not _safe(record['kinematics_after'],initial['initial_kinematics']):raise ValueError('unsafe source state')
            if index in CHECKPOINTS:
                if index==125:queries.capture(record,'parameter')
                queries.capture(record,'topic')
            if args.case=='disconnect' and index==125:
                processes.stop('px4');disconnected=True;manifest['disconnected_after_step']=index
        child.wait(timeout=3);processes.stopped.add('initialization-host')
        terminal=loads('terminal',(run/'diagnostics/terminal.json').read_bytes())
        manifest['terminal']=terminal
        summary=validate_steps(header,iter(rows));manifest['stream']=summary
        if args.case=='normal':
            if child.returncode!=0 or len(rows)!=2500:raise ValueError('incomplete normal preparation')
            evaluation=evaluate(header,iter(rows),queries.rows,queries.layouts,queries.binary_dir)
            manifest.update(evaluation);operational=True
        elif args.case=='disconnect':
            operational=child.returncode==20 and len(rows)==126 and not rows[-1]['fdm']['ran'] and terminal['reason']=='peer_closed'
        manifest['operational_checks_passed']=operational
    except Exception as exc:
        manifest['errors'].append(str(exc));print(str(exc),flush=True)
        if args.case=='transaction-timeout' and started is not None:
            # Preserve late failure evidence, without advancing source time or retrying the transaction.
            try:
                child.wait(timeout=2);processes.stopped.add('initialization-host')
                terminal=loads('terminal',(run/'diagnostics/terminal.json').read_bytes())
                raw_rows=[json.loads(r) for r in (run/'diagnostics/steps.jsonl').read_bytes().splitlines()]
                operational=(child.returncode==20 and terminal['reason']=='transaction_timeout' and len(raw_rows)==126
                    and not raw_rows[-1]['fdm']['ran'] and abs(raw_rows[-1]['fdm']['sim_time_after_s']-.5)<=1e-9)
                manifest.update(terminal=terminal,fault_raw_records=len(raw_rows),operational_checks_passed=operational)
            except Exception as audit_error:manifest['errors'].append('timeout audit: '+str(audit_error))
    finally:
        if command:command.close()
        if stream:stream.close()
        manifest['cleanup']=processes.cleanup()
        manifest['collected_steps']=len(rows)
        manifest['valid_observations']=len(queries.rows) if queries else 0
        manifest['raw_query_count']=len(list((run/'queries').glob('*-raw.json'))) if (run/'queries').exists() else 0
        if rows:
            try:
                manifest['partial_stream']=validate_steps(header,iter(rows))
            except ValueError as exc:manifest['errors'].append('partial stream: '+str(exc))
        manifest['source_unchanged']=source_snapshot()==baseline
        manifest['third_party_unchanged']=all((root/n).read_text()==v for n,v in originals.items())
        manifest['native_msgs_unchanged']=all((root/'.runtime/src/px4-v1.13.3/msg'/(n+'.msg')).read_text()==v for n,v in native.items())
        manifest['quality_sources_unchanged']=all((root/'.runtime/src/px4-v1.13.3'/n).read_text()==v for n,v in semantic.items())
        try:manifest['ports_after']=[] if args.build_only else probe_ports('LIVE',11811)
        except OSError as exc:manifest['ports_after']=[];manifest['errors'].append(str(exc));operational=False
        manifest['software_checks_passed']=(operational and manifest['cleanup']['passed'] and manifest['source_unchanged']
            and manifest['third_party_unchanged'] and manifest['native_msgs_unchanged'] and manifest['quality_sources_unchanged']
            and all(p['free'] for p in manifest['ports_after']))
        manifest['runtime_accepted']=bool(args.case=='normal' and manifest.get('passed',False) and manifest['software_checks_passed'])
        if args.case!='normal':manifest['passed']=manifest['software_checks_passed']
        write_json(run/'manifest.json',manifest)
    return int(not manifest['software_checks_passed'])


if __name__=='__main__':sys.exit(main())
