"""Explicit producer-time preparation; the original selector entry remains unchanged."""
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
from sim_flight_initialization_time_build import build
from sim_flight_initialization_selector_queries import SelectorQueries
from ufm_simulation import flight_initialization_contract as physical
from ufm_simulation import flight_initialization_selector as contract
from ufm_simulation.flight_probe_quality import SEMANTIC_PATHS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('normal','disconnect','transaction-timeout'),default='normal')
    parser.add_argument('--build-only',action='store_true')
    args = parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    run = root/'.runtime/runs'/('flight-init-time-sw01-'+args.case+'-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True);print(run,flush=True)
    sys.path.insert(0,str(root/'tests'))
    from sim_motion_matrix_run import source_snapshot
    baseline = source_snapshot();write_json(run/'source-before.json',baseline)
    for name in ('rootfs','ros-home','ros-logs'):
        (run/name).mkdir()
    for name in ('configs/sim_flight_initialization_selector_fixture.json',
            'tests/fixtures/sim_flight_initialization_selector_native.json'):
        shutil.copy2(root/name,run/Path(name).name)
    profile = contract.loads('profile',(run/'sim_flight_initialization_selector_fixture.json').read_bytes())
    frozen = json.loads((run/'sim_flight_initialization_selector_native.json').read_text())
    px4_source = root/'.runtime/src/px4-v1.13.3'
    native = {name:(px4_source/'msg'/(name+'.msg')).read_text() for name in frozen['native_messages']}
    sources = {name:(px4_source/name).read_text() for name in contract.SELECTOR_SOURCES}
    quality = {name:(px4_source/name).read_text() for name in SEMANTIC_PATHS}
    contract.verify_sources(sources,native,quality,frozen)
    for name,value in [('native-msg-before.json',native),('selector-source-before.json',sources),
            ('quality-source-before.json',quality)]:
        write_json(run/name,value)
    bridge = px4_source/'Tools/jsbsim_bridge'
    originals = {str(p.relative_to(root)):p.read_text() for d in ('src','include') for p in (bridge/d).glob('*') if p.is_file()}
    for path in (bridge/'configs/rascal.xml',bridge/'scene/LSZH.xml',bridge/'models/Rascal/Rascal110-JSBSim.xml'):
        originals[str(path.relative_to(root))] = path.read_text()
    write_json(run/'third-party-before.json',originals)
    manifest = dict(run_id=run.name,python=sys.executable,case=args.case,commands=[],errors=[],
        control_commands_sent=False,ros_or_gazebo_started=False,source_limit_steps=2500,
        collection_complete=False,input_settled=False,initialization_ready=False,output_chain_observed=False,
        passed=False,selector_payload_complete=False,binding_status='unverified',control_gate_accepted=False)
    processes = Processes(run,configure_environment(run,11811),manifest);install_interrupt_handler()
    command = stream = child = queries = None
    operational = False
    rows = []
    started = initial_ns = None
    try:
        product = build(root,run,manifest)
        if args.build_only:
            operational = True
        else:
            manifest['ports_before'] = probe_ports('LIVE',11811)
            if not all(p['free'] for p in manifest['ports_before']):
                raise RuntimeError('existing port owner preserved')
            reject_existing_px4()
            create_ic(bridge/'scene/LSZH.xml',run/'initial.xml',profile['physical_profile'])
            os.mkfifo(run/'steps.fifo',0o600)
            started = time.monotonic_ns()
            def guard(deadline=None,allow_px4=False):
                now = time.monotonic_ns()
                physical.check_budget(now,started,initial_ns,
                    artifact_bytes=sum(p.stat().st_size for p in run.rglob('*') if p.is_file()))
                if deadline is not None and now>=deadline:
                    raise TimeoutError('selector preparation deadline')
                processes.check(allowed=('initialization-host','px4') if allow_px4 else ('initialization-host',))
            def wait(predicate,deadline,allow_px4=False):
                while not predicate():
                    guard(deadline,allow_px4);time.sleep(.01)
                guard(deadline,allow_px4)
            child = processes.spawn('initialization-host',[str(product),str(bridge/'configs/rascal.xml'),
                str(run/'initial.xml'),str(run/'diagnostics'),run.name,str(run/'steps.fifo'),args.case])
            startup = started+60000000000
            wait(lambda:not probe_ports('LIVE',11811)[1]['free'],startup)
            px4 = processes.spawn('px4',[str(root/'.runtime/build/px4-v1.13.3/bin/px4'),'-d',
                str(root/'.runtime/build/px4-v1.13.3/etc'),'-s','etc/init.d-posix/rcS'],run/'rootfs')
            initial_path = run/'diagnostics/initial.json'
            wait(lambda:initial_path.exists() and initial_path.stat().st_size>0,startup)
            initial = json.loads(initial_path.read_text());initial_ns = initial['initial_wall_ns']
            physical_header = dict(schema_version='sim_flight_initialization_recording.v1',run_id=run.name,
                clock_id='sim:'+run.name,profile=profile['physical_profile'],**initial)
            selector_header = dict(schema_version='sim_flight_initialization_selector_recording.v1',run_id=run.name,
                clock_id='sim:'+run.name,profile=profile,physical_files=dict(contract.PHYSICAL_FILES),
                binding_status='unverified',control_gate_accepted=False)
            for name,raw in [('header.json',physical.dumps('header',physical_header)),
                    ('selector-header.json',contract.dumps('header',selector_header))]:
                with (run/name).open('xb') as output:
                    output.write(raw)
            fd = None
            def connected():
                nonlocal fd
                try:
                    fd=os.open(run/'steps.fifo',os.O_WRONLY|os.O_NONBLOCK);return True
                except OSError as exc:
                    if exc.errno!=errno.ENXIO:raise
                    return False
            wait(connected,startup)
            command = os.fdopen(fd,'w',buffering=1)
            stream = (run/'diagnostics/steps.jsonl').open('rb')
            manifest['python_process_audit'] = python_process_audit()
            if not manifest['python_process_audit']['passed']:
                raise RuntimeError('Python process mismatch')
            queries = SelectorQueries(root,run,px4,processes,guard)
            disconnected = False
            for index in range(1,2501):
                guard(allow_px4=disconnected)
                transaction = time.monotonic_ns()+1000000000
                command.write('next\n');raw = b''
                def available():
                    nonlocal raw
                    raw = stream.readline(16385)
                    return bool(raw)
                wait(available,transaction,allow_px4=disconnected)
                if len(raw)>16384 or not raw.endswith(b'\n'):
                    raise ValueError('host record bound')
                record = physical.loads('step',raw)
                if record['step_index']!=index:
                    raise ValueError('host skipped step')
                rows.append(record)
                if record['fdm']['result'] is not True:break
                if not physical._safe(record['kinematics_after'],initial['initial_kinematics']):
                    raise ValueError('unsafe source state')
                if index in physical.CHECKPOINTS:
                    if index==125:queries.capture(record,'parameter')
                    queries.capture(record,'topic')
                if args.case=='disconnect' and index==125:
                    processes.stop('px4');disconnected=True;manifest['disconnected_after_step']=index
            child.wait(timeout=3);processes.stopped.add('initialization-host')
            terminal = physical.loads('terminal',(run/'diagnostics/terminal.json').read_bytes())
            manifest['terminal'] = terminal
            manifest['stream'] = physical.validate_steps(physical_header,iter(rows))
            if args.case=='normal':
                if child.returncode!=0 or len(rows)!=2500:
                    raise ValueError('incomplete normal preparation')
                guard();queries.budget()
                evaluation = contract.load_recording(run,queries.layouts,queries.binary_dir)
                manifest.update(evaluation);operational=True
            elif args.case=='disconnect':
                operational = (child.returncode==20 and len(rows)==126 and not rows[-1]['fdm']['ran']
                    and terminal['reason']=='peer_closed')
    except Exception as exc:
        manifest['errors'].append(str(exc));print(str(exc),flush=True)
        if args.case=='transaction-timeout' and child is not None:
            try:
                child.wait(timeout=2);processes.stopped.add('initialization-host')
                terminal = physical.loads('terminal',(run/'diagnostics/terminal.json').read_bytes())
                raw_rows = [json.loads(raw) for raw in (run/'diagnostics/steps.jsonl').read_bytes().splitlines()]
                operational = (child.returncode==20 and terminal['reason']=='transaction_timeout' and len(raw_rows)==126
                    and not raw_rows[-1]['fdm']['ran'] and abs(raw_rows[-1]['fdm']['sim_time_after_s']-.5)<=1e-9)
                manifest.update(terminal=terminal,fault_raw_records=len(raw_rows))
            except Exception as audit_error:
                manifest['errors'].append('timeout audit: '+str(audit_error))
    finally:
        if command:command.close()
        if stream:stream.close()
        manifest['cleanup'] = processes.cleanup()
        manifest['collected_steps'] = len(rows)
        manifest['valid_observations'] = len(queries.rows) if queries else 0
        manifest['raw_query_count'] = len(list((run/'selector-queries').glob('*-raw.json')))
        if rows:
            try:manifest['partial_stream'] = physical.validate_steps(physical_header,iter(rows))
            except ValueError as exc:manifest['errors'].append('partial stream: '+str(exc))
        manifest['source_unchanged'] = source_snapshot()==baseline
        manifest['third_party_unchanged'] = all((root/n).read_text()==v for n,v in originals.items())
        manifest['native_msgs_unchanged'] = all((px4_source/'msg'/(n+'.msg')).read_text()==v for n,v in native.items())
        manifest['selector_sources_unchanged'] = all((px4_source/n).read_text()==v for n,v in sources.items())
        manifest['quality_sources_unchanged'] = all((px4_source/n).read_text()==v for n,v in quality.items())
        try:manifest['ports_after'] = [] if args.build_only else probe_ports('LIVE',11811)
        except OSError as exc:
            manifest['ports_after']=[];manifest['errors'].append(str(exc));operational=False
        manifest['software_checks_passed'] = bool(operational and manifest['cleanup']['passed']
            and all(manifest[n] for n in ('source_unchanged','third_party_unchanged','native_msgs_unchanged',
                'selector_sources_unchanged','quality_sources_unchanged')) and all(p['free'] for p in manifest['ports_after']))
        manifest['runtime_accepted'] = bool(not args.build_only and args.case=='normal'
            and manifest['passed'] and manifest['software_checks_passed'])
        manifest['operational_checks_passed'] = operational
        if args.case!='normal' or args.build_only:manifest['passed']=manifest['software_checks_passed']
        write_json(run/'manifest.json',manifest)
    return int(not manifest['software_checks_passed'])


if __name__=='__main__':sys.exit(main())
