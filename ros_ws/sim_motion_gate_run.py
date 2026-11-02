"""Explicit bounded PX4/JSBSim + paused Gazebo engine gate; no flight commands."""
import argparse
import datetime
import errno
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

import yaml

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
    probe_ports, python_process_audit, reject_existing_px4, start_master, write_json)
from sim_motion_build import build
from ufm_scene_contract.profile import load_json, validate_profile
from ufm_simulation.scene_motion import SceneRegistration, SceneTransactions
from ufm_simulation.scene_motion_world import create_motion_world


def wall_call(function, timeout):
    result = queue.Queue(maxsize=1)
    def invoke():
        try:
            result.put((True, function()))
        except Exception as exc:
            result.put((False, exc))
    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    try:
        success, value = result.get(timeout=timeout)
    except queue.Empty as exc:
        raise RuntimeError('scene_rpc_wall_timeout') from exc
    if not success:
        raise value
    return value


def main(delivery_mode=False, suite_mode=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-only', action='store_true')
    if suite_mode:parser.set_defaults(fault=None,fault_step=250)
    else:
        parser.add_argument('--fault', choices=('missing-ir-ack',))
        parser.add_argument('--fault-step', type=int, choices=(25,250), default=250)
    parser.add_argument('--no-native', action='store_true')
    parser.add_argument('--previous-run-id', default='')
    parser.add_argument('--inject-clock-conflict', action='store_true')
    parser.add_argument('--port', type=int, default=11801)
    parser.add_argument('--gazebo-port', type=int, default=11802)
    if delivery_mode and not suite_mode:
        parser.add_argument('--report-scene', action='store_true', help='explicit sparse/noisy report scene')
    if suite_mode:
        parser.add_argument('--case', required=True, choices=tuple('S%02d'%i for i in range(1,10)))
        parser.add_argument('--native', dest='no_native', action='store_false')
        parser.set_defaults(no_native=True)
    args = parser.parse_args()
    report_scene = getattr(args, 'report_scene', False)
    if report_scene and (args.fault or args.inject_clock_conflict):
        parser.error('report scene is a normal-run demonstration, separate from frozen fault cases')
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if args.port == args.gazebo_port or any(not 1024 <= p <= 65535 for p in (args.port, args.gazebo_port)):
        parser.error('invalid ports')
    root = Path(__file__).resolve().parents[1]
    spec = None
    if suite_mode:
        from ufm_simulation.motion_suite import case_spec, load_suite
        if args.fault or args.fault_step != 250 or args.inject_clock_conflict:
            parser.error('suite fault/clock plan is selected by the frozen case only')
        spec = case_spec(load_suite(root/'configs/sim_motion_multiscene_fixture.json'),args.case)
        if not args.no_native and not spec['native']:
            parser.error('native capture is only declared for S05/S07')
        args.fault = 'missing-radar-ack' if spec['fault'] else None
        args.fault_step = spec['fault']['step_index'] if spec['fault'] else 250
    identity = (('sim-motion-sw04b-'+spec['case_id']+'-') if spec else
        ('sim-motion-report-' if report_scene else 'sim-motion-sw03-' if delivery_mode else 'sim-motion-sw02-')) + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True)
    for name in ('ros-home', 'ros-logs', 'rootfs', 'sources'):
        (run / name).mkdir()
    # Literal expectations are saved before compilation, simulator or generated-message use.
    for source in ('configs/sim_scene_motion_fixture.json', 'tests/fixtures/sim_motion_expectations.json'):
        shutil.copy2(root / source, run / Path(source).name)
    if spec:
        for source in ('configs/sim_motion_multiscene_fixture.json','tests/fixtures/sim_motion_multiscene_expectations.json',
                       'tests/fixtures/sim_motion_strict_geometry_expectations.json'):
            shutil.copy2(root/source,run/Path(source).name)
        write_json(run/'case-spec.json',spec)
    write_json(run / 'gate-expectations.json', dict(completed_steps=args.fault_step-1 if args.fault else 250,
        captures_per_sensor=args.fault_step//25 if args.fault else 10,
        acks=2*(args.fault_step//25 if args.fault else 10), fault_step=args.fault_step if args.fault else None,
        clock_publishers=['/sim_motion_host'], state_publishers=['/sim_motion_host'],
        tf_publishers=['/state_adapter'], first_capture_ns=100000000, timestamp_rewriting=False,
        terminal_required=True, pause_step=24, duplicate_step=25,
        rejected_service_probes=['version', 'identity', 'nonfinite', 'confidence', 'quaternion',
            'registration', 'skipped_step', 'wire_limit']))
    profile = load_json(run / 'sim_scene_motion_fixture.json')
    validate_profile(profile)
    sources = ['simulation/jsbsim_scene_host.cpp', 'simulation/gazebo_scene_step.cpp',
        'simulation/scene_motion_context.h', 'simulation/scene_motion_context.cpp',
        'simulation/ufm_simulation/scene_motion.py', 'simulation/ufm_simulation/scene_motion_world.py',
        'sensors/gazebo_scene_radar.cpp', 'sensors/gazebo_scene_ir.cpp', 'sensors/scene_motion_capture.h',
        'sensors/ufm_sensors/state_adapter.py', 'sensors/ufm_sensors/scene_stream.py',
        'ros_ws/sim_motion_gate_run.py', 'ros_ws/sim_motion_build.py', 'tests/check_sim_motion_live.py']
    if delivery_mode:
        sources += ['ros_ws/sim_motion_delivery.py','ros_ws/sim_motion_delivery_run.py','tests/motion_delivery_checks.py',
            'ros_ws/scene_sensor_node.py','ros_ws/scene_map_viz.py','ros_ws/local_map_replay.py',
            'ros_ws/native_scene_rviz.cpp','simulation/gazebo_scene_gui.cpp','tests/check_motion_delivery_figures.py',
            'tests/motion_graph_conflict.py','tests/test_sim_motion_delivery.py']
    if report_scene:
        sources += ['configs/report_sensor_scene.yaml','sensors/radar_measurement_model.h',
            'tests/report_motion_checks.py']
    if spec:
        sources += ['simulation/ufm_simulation/motion_suite.py','simulation/ufm_simulation/multiscene_world.py',
            'ros_ws/sim_motion_multiscene_ros_run.py','ros_ws/sim_motion_multiscene_delivery.py',
            'tests/sim_motion_multiscene_live.py','tests/sim_motion_multiscene_oracle.py',
            'tests/sim_motion_multiscene_figures.py']
    for source in sources:
        dest = run / 'sources' / source
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / source, dest)
    env = configure_environment(run, args.port)
    manifest = dict(run_id=identity, python=sys.executable, supervisor_pid=os.getpid(), commands=[], errors=[],
        mode='jsbsim_scene_truth', automatic_flight_commands=False, fault=args.fault,
        scope='SW-03 functional motion handoff; not controlled flight or model quality' if delivery_mode else
              'SW-02 same-FDM engine/sampling gate; not controlled flight or SW-03 end-to-end acceptance')
    if spec:
        manifest.update(case_id=spec['case_id'],scope='Single multiscene case; full matrix acceptance requires SW-04C receipts')
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    receipts = commands = raw_stream = clock_pub = source_pub = handoff = None
    transaction = SceneTransactions(identity)
    passed = False
    print(str(run), flush=True)
    try:
        products = build(root, run, manifest, output_directory=root/'.runtime/ros/report-motion-build') if report_scene else build(root,run,manifest)
        if args.build_only:
            passed = True
            return 0
        started = time.monotonic()
        deadline = started + profile['deadlines_ns']['session']/1e9
        startup = started + profile['deadlines_ns']['startup']/1e9
        manifest['ports_before'] = probe_ports('LIVE', args.port) + probe_ports('REPORT', args.gazebo_port)
        if not all(row['free'] for row in manifest['ports_before']):
            raise RuntimeError('port busy; existing processes preserved')
        reject_existing_px4()
        scene = yaml.safe_load((root / ('configs/report_sensor_scene.yaml' if report_scene else 'configs/sensor_scene.yaml')).read_text())
        from ufm_sensors.scene_stream import validate_scene_profile
        validate_scene_profile(scene)
        scene['body_pose'] = profile['scene_anchor_m'] + [0., 0., 0.]
        if spec:
            from ufm_simulation.multiscene_world import assemble_scene, create_suite_world
            scene = assemble_scene(scene,spec)
            create_suite_world(scene,spec,root,run/'scene.world')
        else:create_motion_world(scene, root, run / 'scene.world')
        write_json(run / 'scene-profile.json', scene)
        ic = ET.parse(root / '.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/scene/LSZH.xml')
        ic.getroot().find('altitude').text = '8'
        ic.getroot().find('vt').text = str(profile['initial_forward_speed_mps'] / .3048)
        ic.getroot().find('psi').text = '90'
        if spec:
            from ufm_simulation.multiscene_world import create_suite_ic
            create_suite_ic(root/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/scene/LSZH.xml',
                run/'initial.xml',spec['ic_degrees'],profile['initial_forward_speed_mps'])
        else:ic.write(run / 'initial.xml', encoding='utf-8', xml_declaration=True)
        master = start_master(processes, args.port, startup)
        import rospy
        from gazebo_msgs.srv import GetWorldProperties
        from rosgraph_msgs.msg import Clock
        from uav_fusionmap_msgs.msg import AircraftState
        from uav_fusionmap_sim_scene_msgs.srv import SceneStep
        from ufm_ros_contract import to_ros_state
        from ufm_scene_contract.codec import to_ros, from_ros
        sys.path.insert(0, str(root / 'tests'))
        from check_sim_motion_live import LiveReceipts, validate, verify_payloads
        rospy.init_node('sim_motion_host', disable_signals=True)
        clock_pub = rospy.Publisher('/clock', Clock, queue_size=512)
        source_pub = rospy.Publisher('/uav/sim/state', AircraftState, queue_size=512)
        if delivery_mode:
            if spec:
                from sim_motion_multiscene_delivery import MultisceneDelivery
                handoff=MultisceneDelivery(root,run,identity,scene,processes,master,wall_call,
                    not args.no_native,args.previous_run_id,spec=spec)
            else:
                from sim_motion_delivery import Delivery
                handoff=Delivery(root,run,identity,scene,processes,master,wall_call,not args.no_native,args.previous_run_id)
            handoff.prepare_native()
        receipts = LiveReceipts(run, extra_streams=handoff.streams() if handoff else ())
        if handoff:
            handoff.receipts=receipts
            handoff.launch()
        for key, value in (('run_id', identity), ('drop_ack_kind', (1 if spec else 2) if args.fault else 0),
                           ('drop_ack_step', args.fault_step),('geometry_case','S07' if spec and spec['case_id']=='S07' else '')):
            master.setParam('/sim_motion_host', '/ufm_scene_motion/' + key, value)
        processes.spawn('state-adapter', [sys.executable, '-B', str(root /
            'ros_ws/src/uav_fusionmap_sensors/scripts/state_adapter_node.py'),
            '_run_id:=' + identity, '_state_input_mode:=scene_ground_truth',
            '_scene_registration:=gazebo_scene_world_enu_identity_v1', '_quaternion_norm_tolerance:=0.001',
            '_pending_limit:=100', '_pending_timeout_wall_s:=0.5', '_broadcast_tf:=true', '_publish_odom:=true'])
        native = dict(DISPLAY=':0', XAUTHORITY='/run/user/%d/gdm/Xauthority' % os.getuid(),
            LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:' + env.get('LD_LIBRARY_PATH', ''),
            LIBGL_ALWAYS_SOFTWARE='1', __GLX_VENDOR_LIBRARY_NAME='mesa', LP_NUM_THREADS='2',
            GAZEBO_PLUGIN_PATH=str(products) + ':/opt/ros/noetic/lib:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins',
            GAZEBO_RESOURCE_PATH=str(root / 'simulation/sensor_scene_media') + ':/usr/share/gazebo-11',
            GAZEBO_MODEL_DATABASE_URI='', GAZEBO_MASTER_URI='http://127.0.0.1:' + str(args.gazebo_port))
        if handoff and handoff.native_products:
            native['GAZEBO_PLUGIN_PATH'] += ':' + str(handoff.native_products)
        processes.spawn('gazebo-server', ['/usr/bin/gzserver', '--verbose', '--pause', '--lockstep', '-s',
            'libgazebo_ros_api_plugin.so', str(run / 'scene.world'), '/clock:=/diagnostics/gazebo_clock'], extra_env=native)
        if handoff:handoff.launch_native(native)
        last_budget_check = [0.]
        def check_budget():
            if spec and time.monotonic()-last_budget_check[0] >= .5:
                last_budget_check[0] = time.monotonic()
                total = sum(p.stat().st_size for p in run.rglob('*') if p.is_file() and not p.is_symlink())
                manifest['artifact_bytes_observed'] = total
                if total > 256*1024*1024:raise RuntimeError('suite_case_artifact_limit')
        def wait(predicate, until, reason):
            while not predicate():
                processes.check()
                receipts.snapshot()
                check_budget()
                if time.monotonic() >= until:
                    raise RuntimeError(reason)
                time.sleep(.01)
        if handoff and args.inject_clock_conflict:
            processes.spawn('conflicting-clock',[sys.executable,'-B',str(root/'tests/motion_graph_conflict.py')])
            wait(lambda:'/motion_conflicting_clock' in dict(master.getSystemState('/sim_motion_host')[2][0]).get('/clock',[]),
                startup,'motion_conflict_fixture_not_ready')
        wait(lambda: clock_pub.get_num_connections() >= 2 and source_pub.get_num_connections() >= 2,
             startup, 'scene_business_consumers_not_ready')
        rospy.wait_for_service('/uav/scene/step', timeout=max(.01, startup-time.monotonic()))
        service = rospy.ServiceProxy('/uav/scene/step', SceneStep)
        world = rospy.ServiceProxy('/gazebo/get_world_properties', GetWorldProperties)
        if handoff:handoff.ready(wait,startup)
        os.mkfifo(run / 'commands.fifo', 0o600)
        bridge_root = root / '.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
        processes.spawn('bridge', [str(products / 'jsbsim_scene_host'), str(bridge_root / 'configs/rascal.xml'),
            str(run / 'initial.xml'), str(run / 'fdm.jsonl'), str(run / 'initial-geography.json'), str(run / 'commands.fifo')])
        wait(lambda:not probe_ports('LIVE', args.port)[1]['free'], startup, 'scene_bridge_not_listening')
        processes.spawn('px4', [str(root / '.runtime/build/px4-v1.13.3/bin/px4'), '-d',
            str(root / '.runtime/build/px4-v1.13.3/etc'), '-s', 'etc/init.d-posix/rcS'], run / 'rootfs')
        wait(lambda:(run / 'fdm.jsonl').exists() and (run / 'fdm.jsonl').stat().st_size > 0,
             startup, 'scene_fdm_initial_not_ready')
        command_fd = None
        def command_ready():
            nonlocal command_fd
            try:
                command_fd = os.open(run / 'commands.fifo', os.O_WRONLY | os.O_NONBLOCK)
                return True
            except OSError as exc:
                if exc.errno != errno.ENXIO:
                    raise
                return False
        wait(command_ready, startup, 'scene_command_pipe_not_ready')
        commands = os.fdopen(command_fd, 'w', buffering=1)
        raw_stream = (run / 'fdm.jsonl').open()
        def sample(until):
            def line_ready():
                nonlocal raw_line
                raw_line = raw_stream.readline(65537)
                return bool(raw_line)
            raw_line = ''
            wait(line_ready, until, 'scene_fdm_sample_timeout')
            if len(raw_line) > 65536 or not raw_line.endswith('\n'):
                raise ValueError('scene_fdm_record_limit')
            return json.loads(raw_line)
        initial = sample(startup)
        geography = load_json(run / 'initial-geography.json')
        registration = SceneRegistration(initial, geography['geodetic_latitude_rad'], geography['longitude_rad'], profile)
        write_json(run / 'registration.json', registration.metadata)
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise RuntimeError('Python executable mismatch')
        with (run / 'transactions.jsonl').open('x') as log:
            for index in range(profile['duration_steps']+1):
                check_budget()
                if time.monotonic() >= deadline:
                    raise RuntimeError('scene_session_deadline')
                if index == 250 and 'Startup script returned successfully' not in (run / 'px4.log').read_text(errors='replace'):
                    raise RuntimeError('scene_px4_startup_not_complete')
                if index:
                    commands.write('next\n')
                    source = sample(min(deadline, time.monotonic()+1.))
                else:
                    source = initial
                if source['step_index'] != index:
                    raise ValueError('scene_fdm_step_sequence')
                frame = registration.convert(source, identity)
                transaction.begin(frame)
                begin = time.monotonic()
                timeout = 4. if index == 25 else 1.2
                response = wall_call(lambda:service(to_ros('SceneFrame', frame)), timeout)
                decoded = from_ros('SceneStepResponse', response, request=dict(frame=frame))
                log.write(json.dumps(dict(request=frame, response=decoded, wall_seconds=time.monotonic()-begin),
                    allow_nan=False) + '\n'); log.flush()
                if not decoded['accepted']:
                    transaction.fail(decoded['reason'])
                    manifest['failed_step'] = index
                    if args.fault and index == args.fault_step and decoded['reason'] == ('scene_radar_timeout' if spec else 'scene_ir_timeout'):
                        break
                    raise RuntimeError(decoded['reason'])
                state = transaction.finish(decoded)
                clock_pub.publish(Clock(clock=rospy.Time(secs=0, nsecs=state['header']['timestamp'])))
                source_pub.publish(to_ros_state(state))
                if handoff:handoff.after_step(index,wait,deadline)
                if index == 0:
                    graph = master.getSystemState('/sim_motion_host')[2]
                    publishers = dict(graph[0])
                    for topic, nodes in (('/clock', ['/sim_motion_host']), ('/uav/sim/state', ['/sim_motion_host']),
                            ('/uav/sensors/state', ['/state_adapter']), ('/tf', ['/state_adapter'])):
                        if publishers.get(topic) != nodes:
                            raise RuntimeError('scene_publisher_authority:' + topic)
                    if any(any(token in name.lower() for token in ('lidar', 'observed_mask', 'training'))
                            for section in graph[:2] for topic, nodes in section for name in [topic, *nodes]):
                        raise RuntimeError('training_graph_present')
                    manifest['graph'] = graph
                    probes = []
                    for name in ('version', 'identity', 'nonfinite', 'confidence', 'quaternion',
                                 'registration', 'skipped_step', 'wire_limit'):
                        bad = to_ros('SceneFrame', frame)
                        if name == 'version':bad.protocol_version = 2
                        elif name == 'identity':bad.state.header.run_id = 'another-run'
                        elif name == 'nonfinite':bad.state.position[0] = float('nan')
                        elif name == 'confidence':bad.state.quality.confidence_available = True
                        elif name == 'quaternion':bad.state.orientation_xyzw = [0.,0.,0.,0.]
                        elif name == 'registration':bad.registration_id = 'undeclared'
                        elif name == 'skipped_step':
                            bad.step_index = 2; bad.state.header.timestamp = 8000000
                            bad.state.header.sample_id = 'scene.frame:%s:2' % identity
                        else:bad.registration_id = 'x'*4097
                        answer = from_ros('SceneStepResponse', wall_call(lambda:service(bad), 1.))
                        if answer['accepted'] or answer['applied_frame'] is not None:
                            raise RuntimeError('scene_bad_service_request_applied:' + name)
                        probes.append(dict(case=name, response=answer))
                    if wall_call(world, 1.).sim_time != 0.:
                        raise RuntimeError('scene_bad_service_request_advanced')
                    write_json(run / 'service-rejections.json', probes)
                if index == 24:
                    wait(lambda:len(receipts.snapshot().get('state', [])) >= 25, deadline, 'state drain before pause')
                    before = receipts.snapshot()
                    before_world = wall_call(world, 1.).sim_time
                    time.sleep(.1)
                    after = receipts.snapshot()
                    after_world = wall_call(world, 1.).sim_time
                    if before != after or before_world != after_world:
                        raise RuntimeError('scene_pause_advanced_or_republished')
                    write_json(run / 'pause.json', dict(step=24, world_before=before_world,
                        world_after=after_world, wall_pause_s=.1, receipts_unchanged=True))
                if index == 25:
                    duplicate = from_ros('SceneStepResponse', wall_call(lambda:service(to_ros('SceneFrame', frame)), 1.),
                        request=dict(frame=frame))
                    if duplicate != decoded:
                        raise RuntimeError('scene_duplicate_receipt_changed')
                    manifest['duplicate_step_25'] = True
        completed = transaction.completed['step_index']
        def last_state_delivered():
            rows = receipts.snapshot()
            expected = completed*profile['step_ns']
            return (any(r['value']['header']['status'] == 'valid' and
                        r['value']['header']['timestamp'] == expected for r in rows.get('state', [])) and
                    any(t['timestamp'] == expected for r in rows.get('tf', []) for t in r['transforms']))
        wait(last_state_delivered, min(deadline, time.monotonic()+1.), 'scene_last_state_not_delivered')
        terminal = transaction.terminal(('scene_radar_timeout' if spec else 'scene_ir_timeout') if args.fault else 'scene_window_complete')
        source_pub.publish(to_ros_state(terminal))
        wait(lambda:any(r['value']['header']['status'] == 'unavailable'
            for r in receipts.snapshot().get('state', [])), min(deadline, time.monotonic()+2.), 'scene_terminal_not_propagated')
        time.sleep(.1)
        result = validate(receipts.snapshot(), completed, fault=bool(args.fault),allow_empty=bool(spec and spec['case_id']=='S06'))
        if report_scene:
            from report_motion_checks import verify_report_payloads
            result['payloads'] = verify_report_payloads(run,receipts.snapshot(),scene)
        else:
            result['payloads'] = verify_payloads(run, receipts.snapshot(), fault=bool(args.fault),
                require_ir_change=not bool(spec) or spec['case_id']=='S01')
        if args.fault:
            rejected = from_ros('SceneStepResponse', wall_call(lambda:service(to_ros('SceneFrame', frame)), 1.))
            if rejected['accepted'] or rejected['reason'] != 'scene_run_locked':
                raise RuntimeError('failed run revived')
            result['locked_after_fault'] = True
        if handoff:handoff.finish(wait,deadline,completed,args.fault)
        check_budget()
        write_json(run / 'validation.json', result)
        manifest['wall_seconds'] = time.monotonic()-started
        passed = True
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
        if source_pub is not None:
            terminal = transaction.terminal('scene_engine_gate_failed')
            if terminal is not None:
                try:
                    source_pub.publish(to_ros_state(terminal))
                    time.sleep(.1)
                except Exception as terminal_error:
                    manifest['errors'].append('terminal:' + str(terminal_error))
    finally:
        if receipts is not None:
            receipts.close()
        if 'px4' in processes.children and 'px4' not in processes.stopped:
            try:
                px4=processes.children['px4']
                if handoff and args.fault and args.fault_step==25 and px4.poll() is None:
                    command=[str(root/'.runtime/build/px4-v1.13.3/bin/px4-shutdown')]
                    with (run/'px4-shutdown.log').open('x') as stream:
                        code=subprocess.run(command,cwd=run/'rootfs',env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=2.).returncode
                    manifest['px4_shutdown_request_exit']=code
                    manifest['commands'].append(dict(name='px4-shutdown-request',args=command,exit=code))
                    px4.wait(timeout=3.)
                    # POSIX shutdown exits the daemon before its IPC client always receives a reply.
                    marker='Exiting NOW.' in (run/'px4.log').read_text(errors='replace')
                    manifest['px4_shutdown_daemon_exit']=px4.returncode
                    manifest['px4_shutdown_marker']=marker
                    if px4.returncode or code not in (0,255) or not marker:
                        raise RuntimeError('PX4 requested daemon shutdown failed: '+str(px4.returncode))
                    processes.stopped.add('px4')
                else:processes.stop('px4')
            except (RuntimeError, ProcessLookupError, subprocess.TimeoutExpired) as exc:
                manifest['errors'].append('cleanup: ' + str(exc))
        if commands is not None:
            bridge = processes.children['bridge']
            try:
                commands.write('quit\n'); commands.close()
                bridge.wait(timeout=1.)
                processes.stopped.add('bridge')
                if bridge.returncode != 0:
                    manifest['errors'].append('bridge exit:' + str(bridge.returncode))
            except __import__('subprocess').TimeoutExpired:
                pass
            except (BrokenPipeError, OSError) as exc:
                commands.close()
                manifest['errors'].append('bridge command close:' + str(exc))
        if raw_stream is not None:
            raw_stream.close()
        cleanup = processes.cleanup()
        if not args.build_only:
            cleanup['ports'] = probe_ports('LIVE', args.port) + probe_ports('REPORT', args.gazebo_port)
            cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        manifest['passed'] = passed and cleanup['passed'] and not manifest['errors']
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=manifest['passed'], errors=manifest['errors'])), flush=True)
    return int(not manifest['passed'])


if __name__ == '__main__':
    sys.exit(main())
