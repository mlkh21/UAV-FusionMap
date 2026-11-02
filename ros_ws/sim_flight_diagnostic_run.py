"""Explicit <=250-step/1s same-FDM diagnostic; no ROS graph or flight commands."""
import argparse
from datetime import datetime
import errno
import json
import os
from pathlib import Path
import shutil
import sys
import time
import xml.etree.ElementTree as ET

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
    probe_ports, python_process_audit, reject_existing_px4, write_json)
from sim_flight_build import build
from ufm_simulation.flight_contract import load_profile


def create_ic(source,destination,profile):
    tree=ET.parse(source);node=tree.getroot();ic=profile['ic']
    values={'latitude':ic['latitude_deg'],'longitude':ic['longitude_deg'],
        'altitude':ic['altitude_m'],'elevation':ic['terrain_elevation_m'],
        'vt':ic['true_airspeed_mps']/.3048,'phi':ic['phi_theta_psi_deg'][0],
        'theta':ic['phi_theta_psi_deg'][1],'psi':ic['phi_theta_psi_deg'][2]}
    for key,value in values.items():
        element=node.find(key)
        if element is None:raise ValueError('IC source missing '+key)
        element.text=str(value)
    for element in list(node.findall('gamma')):node.remove(element)
    with destination.open('xb') as stream:tree.write(stream,encoding='utf-8',xml_declaration=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-only',action='store_true')
    parser.add_argument('--case',choices=('normal','disconnect'),default='normal')
    parser.add_argument('--uorb-probe',action='store_true')
    parser.add_argument('--uorb-diagnostics',action='store_true')
    parser.add_argument('--uorb-quality-diagnostics',action='store_true')
    args=parser.parse_args()
    if args.uorb_probe and (args.case!='normal' or args.build_only):
        parser.error('uorb-probe requires the actual normal diagnostic')
    if args.uorb_diagnostics and (args.uorb_probe or args.case!='normal' or args.build_only):
        parser.error('uorb-diagnostics requires the actual normal case and excludes uorb-probe')
    if args.uorb_quality_diagnostics and (args.uorb_probe or args.uorb_diagnostics or args.case!='normal' or args.build_only):
        parser.error('uorb-quality-diagnostics requires normal and excludes other diagnostic modes')
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root=Path(__file__).resolve().parents[1]
    prefix='sim-flight-sw02c-diagnostics-' if args.uorb_diagnostics else (
        'sim-flight-sw02b-probe-' if args.uorb_probe else 'sim-flight-sw02-'+args.case+'-')
    if args.uorb_quality_diagnostics:prefix='sim-flight-sw02d-quality-'
    identity=prefix+datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run=root/'.runtime/runs'/identity;run.mkdir(parents=True)
    for name in ('rootfs','ros-home','ros-logs'):(run/name).mkdir()
    sys.path.insert(0,str(root/'tests'))
    from sim_motion_matrix_run import source_snapshot
    baseline=source_snapshot();write_json(run/'source-before.json',baseline)
    for source in ('configs/sim_flight_fixture.json','tests/fixtures/sim_flight_diagnostic_expectations.json'):
        shutil.copy2(root/source,run/Path(source).name)
    native_messages={}
    if args.uorb_probe:
        from ufm_simulation.flight_probe_contract import MESSAGE_FILES
        shutil.copy2(root/'tests/fixtures/sim_flight_probe_expectations.json',run/'independent-probe-expectations.json')
        native_messages={name:(root/'.runtime/src/px4-v1.13.3/msg'/(name+'.msg')).read_text() for name in MESSAGE_FILES}
        write_json(run/'native-msg-before.json',native_messages)
    if args.uorb_diagnostics:
        from ufm_simulation.flight_probe_contract import MESSAGE_FILES
        shutil.copy2(root/'tests/fixtures/sim_flight_diagnostic_cases.json',run/'independent-diagnostic-expectations.json')
        native_messages={name:(root/'.runtime/src/px4-v1.13.3/msg'/(name+'.msg')).read_text() for name in MESSAGE_FILES}
        write_json(run/'native-msg-before.json',native_messages)
    if args.uorb_quality_diagnostics:
        from ufm_simulation.flight_probe_contract import MESSAGE_FILES
        for name in ('sim_flight_quality_cases.json','sim_flight_quality_baseline.json'):
            shutil.copy2(root/'tests/fixtures'/name,run/name)
        native_messages={name:(root/'.runtime/src/px4-v1.13.3/msg'/(name+'.msg')).read_text() for name in MESSAGE_FILES}
        write_json(run/'native-msg-before.json',native_messages)
    bridge=root/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
    original={str(p.relative_to(root)):p.read_text() for d in ('src','include') for p in (bridge/d).glob('*') if p.is_file()}
    original[str((bridge/'configs/rascal.xml').relative_to(root))]=(bridge/'configs/rascal.xml').read_text()
    original[str((bridge/'scene/LSZH.xml').relative_to(root))]=(bridge/'scene/LSZH.xml').read_text()
    write_json(run/'third-party-before.json',original)
    profile=load_profile(run/'sim_flight_fixture.json')
    expected=json.loads((run/'sim_flight_diagnostic_expectations.json').read_text())
    env=configure_environment(run,11811)
    manifest=dict(run_id=identity,python=sys.executable,case=args.case,commands=[],errors=[],
        control_commands_sent=False,ros_or_gazebo_started=False,source_limit_steps=250,
        binding_status='unverified',control_gate_accepted=False)
    if args.uorb_probe:manifest['uorb_probe']=True
    if args.uorb_diagnostics:
        manifest.update(uorb_diagnostics=True,diagnostic_collection_complete=False,payload_complete=False,
            scope='Diagnostic collection only; does not accept legacy SW-02B or control readiness')
    if args.uorb_quality_diagnostics:
        manifest.update(uorb_quality_diagnostics=True,diagnostic_collection_complete=False,
            payload_complete=False,body_complete=False,
            scope='Conditional quality diagnostic collection only; no state or control permission')
    processes=Processes(run,env,manifest);install_interrupt_handler()
    command=None;stream=None;passed=False
    print(run,flush=True)
    try:
        if args.uorb_quality_diagnostics:
            from sim_flight_uorb_quality import source_preflight
            source_preflight(root,run)
        product=build(root,run,manifest)
        if args.build_only:passed=True;return 0
        ports=probe_ports('LIVE',11811)
        manifest['ports_before']=ports
        if not all(row['free'] for row in ports):raise RuntimeError('existing port owner preserved')
        reject_existing_px4()
        create_ic(bridge/'scene/LSZH.xml',run/'initial.xml',profile)
        os.mkfifo(run/'steps.fifo',0o600)
        child=processes.spawn('diagnostic-host',[str(product),str(bridge/'configs/rascal.xml'),
            str(run/'initial.xml'),str(run/'diagnostics'),identity,str(run/'steps.fifo')])
        deadline=time.monotonic()+60
        def wait(predicate,until,reason,allowed=()):
            while not predicate():
                processes.check(allowed=allowed)
                if time.monotonic()>until:raise RuntimeError(reason)
                if sum(p.stat().st_size for p in run.rglob('*') if p.is_file())>536870912:
                    raise RuntimeError('diagnostic artifact budget')
                time.sleep(.01)
        wait(lambda:not probe_ports('LIVE',11811)[1]['free'],deadline,'host not listening')
        px4=processes.spawn('px4',[str(root/'.runtime/build/px4-v1.13.3/bin/px4'),'-d',
            str(root/'.runtime/build/px4-v1.13.3/etc'),'-s','etc/init.d-posix/rcS'],run/'rootfs')
        initial=run/'diagnostics/initial.json'
        wait(lambda:initial.exists() and initial.stat().st_size>0,deadline,'initial FDM missing')
        fd=None
        def connected():
            nonlocal fd
            try:fd=os.open(run/'steps.fifo',os.O_WRONLY|os.O_NONBLOCK);return True
            except OSError as exc:
                if exc.errno!=errno.ENXIO:raise
                return False
        wait(connected,deadline,'host FIFO missing')
        command=os.fdopen(fd,'w',buffering=1)
        stream=(run/'diagnostics/actuators.jsonl').open()
        manifest['python_process_audit']=python_process_audit()
        if not manifest['python_process_audit']['passed']:raise RuntimeError('Python process mismatch')
        disconnected=False;received=[]
        session=time.monotonic()+30
        probe=None
        if args.uorb_probe:
            from sim_flight_uorb_probe import UorbProbe
            initial_meta=json.loads(initial.read_text())
            probe=UorbProbe(root,run,identity,px4,processes,initial_meta['initial_wall_ns']+5000000000,int(session*1e9))
        diagnostic=None
        if args.uorb_diagnostics:
            from sim_flight_uorb_diagnostics import UorbDiagnostics
            initial_meta=json.loads(initial.read_text())
            diagnostic=UorbDiagnostics(root,run,identity,px4,processes,
                initial_meta['initial_wall_ns']+5000000000,int(session*1e9))
        quality=None
        if args.uorb_quality_diagnostics:
            from sim_flight_uorb_quality import UorbQualityDiagnostics
            initial_meta=json.loads(initial.read_text())
            quality=UorbQualityDiagnostics(root,run,identity,px4,processes,
                initial_meta['initial_wall_ns']+5000000000,int(session*1e9))
        for index in range(1,251):
            # Keep diagnostic overhead explicit; source time still advances only 4ms per next.
            if not (args.uorb_probe or args.uorb_diagnostics or args.uorb_quality_diagnostics):time.sleep(.006)
            if diagnostic:diagnostic.guard()
            if quality:quality.guard()
            command.write('next\n');line=''
            def available():
                nonlocal line
                line=stream.readline(16385)
                return bool(line)
            wait(available,min(session,time.monotonic()+2),'diagnostic step timeout',
                allowed=('px4','diagnostic-host') if disconnected else ('diagnostic-host',))
            if len(line)>16384 or not line.endswith('\n'):raise ValueError('record line bound')
            record=json.loads(line);received.append(record)
            if record['step_index']!=index:raise ValueError('host skipped step')
            if probe and index in (125,250) and record['fdm']['result'] is True:
                probe.capture(record)
            if diagnostic and index in (125,250) and record['fdm']['result'] is True:
                diagnostic.capture(record)
            if quality and index in (125,250) and record['fdm']['result'] is True:
                quality.capture(record)
            if (args.case=='disconnect' and not disconnected and 125<=index<250
                    and 'Startup script returned successfully' in (run/'px4.log').read_text(errors='replace')):
                processes.stop('px4');disconnected=True
                manifest['disconnected_after_step']=index
            if not record['fdm']['ran'] or not record['fdm']['result']:break
        if args.case=='disconnect' and not disconnected:raise RuntimeError('bootstrap_not_ready_for_disconnect')
        if probe:
            probe.capture(received[-1],kind='parameter')
            manifest['uorb_verification']=probe.finish()
        if diagnostic:
            diagnostic.capture(received[-1],kind='parameter')
            manifest['uorb_diagnostics_verification']=diagnostic.finish()
        if quality:
            quality.capture(received[-1],kind='parameter')
            manifest['uorb_quality_verification']=quality.finish()
        code=child.wait(timeout=3)
        processes.stopped.add('diagnostic-host')
        if code!=(20 if disconnected else 0):raise RuntimeError('diagnostic host exit '+str(code))
        from sim_flight_diagnostic_checks import verify
        verification=verify(run/'diagnostics',identity,profile,expected,disconnect=disconnected)
        write_json(run/'verification.json',verification)
        manifest['verification']=verification
        passed=True
    except Exception as exc:
        manifest['errors'].append(str(exc));print(str(exc),flush=True)
    finally:
        if command:command.close()
        if stream:stream.close()
        manifest['cleanup']=processes.cleanup()
        manifest['source_unchanged']=source_snapshot()==baseline
        manifest['third_party_unchanged']=all((root/name).read_text()==text for name,text in original.items())
        if args.uorb_probe or args.uorb_diagnostics or args.uorb_quality_diagnostics:
            manifest['native_msgs_unchanged']=all((root/'.runtime/src/px4-v1.13.3/msg'/(name+'.msg')).read_text()==text
                for name,text in native_messages.items())
            passed=passed and manifest['native_msgs_unchanged']
        if args.uorb_quality_diagnostics:
            from ufm_simulation.flight_probe_quality import SEMANTIC_PATHS
            original_sources=run/'quality-source-before.json'
            manifest['quality_sources_unchanged']=original_sources.exists() and all(
                (root/'.runtime/src/px4-v1.13.3'/name).read_text()==text
                for name,text in json.loads(original_sources.read_text()).items())
            passed=passed and manifest['quality_sources_unchanged']
        try:
            manifest['ports_after']=[] if args.build_only else probe_ports('LIVE',11811)
        except OSError as exc:
            manifest['ports_after']=[];manifest['errors'].append('port audit: '+str(exc));passed=False
        manifest['passed']=(passed and manifest['cleanup']['passed'] and manifest['source_unchanged']
            and manifest['third_party_unchanged'] and all(row['free'] for row in manifest['ports_after']))
        if args.uorb_diagnostics:
            manifest['diagnostic_collection_complete']=manifest['passed'] and bool(
                manifest.get('uorb_diagnostics_verification',{}).get('diagnostic_collection_complete'))
            manifest['payload_complete']=bool(manifest.get('uorb_diagnostics_verification',{}).get('payload_complete'))
        if args.uorb_quality_diagnostics:
            verified=manifest.get('uorb_quality_verification',{})
            manifest['diagnostic_collection_complete']=manifest['passed'] and bool(verified.get('diagnostic_collection_complete'))
            manifest['payload_complete']=bool(verified.get('payload_complete'))
            manifest['body_complete']=bool(verified.get('body_complete'))
        write_json(run/'manifest.json',manifest)
    return int(not manifest['passed'])


if __name__=='__main__':sys.exit(main())
