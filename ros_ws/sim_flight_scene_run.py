"""Explicit observation-only 40 s flight v2 scene, same FDM and gated sampling."""
import argparse
from datetime import datetime
import errno
import json
import os
from pathlib import Path
import shutil
import sys
import time

import yaml

from sim01b_runtime import (Processes,configure_environment,install_interrupt_handler,probe_ports,
    python_process_audit,reject_existing_px4,start_master,write_json)
from sim_flight_diagnostic_run import create_ic
from sim_flight_scene_build import build
from sim_flight_scene_queries import ReadyQueries
from sim_motion_gate_run import wall_call
from ufm_flight_contract import contract as c
from ufm_flight_contract.profile import load_profile
from ufm_simulation import flight_initialization_contract as physical
from ufm_simulation import flight_initialization_selector as selector
from ufm_simulation.flight_probe_quality import SEMANTIC_PATHS
from ufm_simulation.flight_scene import FlightRegistration,FlightTransactions,PhysicalStream,CHECKPOINTS
from ufm_simulation.scene_motion_world import create_motion_world


class BuildComplete(Exception):
    pass


def read_record(stream,wait,until,limit=16384):
    raw=b''
    def available():
        nonlocal raw
        raw+=stream.readline(limit+1-len(raw))
        if len(raw)>limit:raise ValueError('host_record_limit')
        return raw.endswith(b'\n')
    wait(available,until,'host_sample_timeout')
    value=selector._decode(raw);physical.bounded(value)
    return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('normal','disconnect','missing-ir-ack','first-missing-ir-ack','not-ready'),default='normal')
    parser.add_argument('--build-only',action='store_true')
    parser.add_argument('--products',type=Path)
    parser.add_argument('--no-native',action='store_true')
    parser.add_argument('--previous-run-id',default='')
    parser.add_argument('--port',type=int,default=11821)
    parser.add_argument('--gazebo-port',type=int,default=11822)
    args=parser.parse_args()
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':raise RuntimeError('Radar-Diffusion Python required')
    if args.port==args.gazebo_port or any(not 1024<=v<=65535 for v in (args.port,args.gazebo_port)):parser.error('invalid ports')
    root=Path(__file__).resolve().parents[1]
    run=root/'.runtime/runs'/('flight-scene-'+args.case+'-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True,exist_ok=False);print(run,flush=True)
    for name in ('rootfs','ros-home','ros-logs'):(run/name).mkdir()
    sys.path.insert(0,str(root/'tests'))
    from sim_motion_matrix_run import source_snapshot
    snapshot=source_snapshot();write_json(run/'source-before.json',snapshot)
    for name in ('configs/sim_flight_scene_fixture.json','tests/fixtures/sim_flight_scene_runtime_expectations.json',
                 'tests/fixtures/sim_flight_initialization_selector_native.json'):
        shutil.copy2(root/name,run/Path(name).name)
    profile=load_profile(run/'sim_flight_scene_fixture.json')
    frozen=json.loads((run/'sim_flight_initialization_selector_native.json').read_text())
    px4_source=root/'.runtime/src/px4-v1.13.3';bridge=px4_source/'Tools/jsbsim_bridge'
    native={n:(px4_source/'msg'/(n+'.msg')).read_text() for n in frozen['native_messages']}
    originals={str(p.relative_to(root)):p.read_text() for d in ('src','include') for p in (bridge/d).glob('*') if p.is_file()}
    originals.update({str(p.relative_to(root)):p.read_text() for p in (bridge/'scene/LSZH.xml',bridge/'configs/rascal.xml',
        bridge/'models/Rascal/Rascal110-JSBSim.xml')})
    sources={n:(px4_source/n).read_text() for n in selector.SELECTOR_SOURCES}
    quality={n:(px4_source/n).read_text() for n in SEMANTIC_PATHS}
    layouts=selector.verify_sources(sources,native,quality,frozen)
    write_json(run/'third-party-before.json',originals);write_json(run/'native-msg-before.json',native)
    manifest=dict(run_id=run.name,python=sys.executable,case=args.case,commands=[],errors=[],
        passed=False,runtime_accepted=False,control_commands_sent=False,binding_status='unverified',
        control_gate_accepted=False,source_limit_steps=10000)
    env=configure_environment(run,args.port);processes=Processes(run,env,manifest);install_interrupt_handler()
    tx=FlightTransactions(run.name)
    command=raw_stream=scene_stream=receipts=source_pub=handoff=host=queries=None
    passed=False;started=deadline=None;physical_stream=None;last_budget=0
    def budget():
        nonlocal last_budget
        now=time.monotonic()
        if deadline and now>=deadline:raise TimeoutError('flight_case_deadline')
        if now-last_budget>=.5:
            last_budget=now
            total=(receipts.total if receipts is not None else 0)+(queries.bytes if queries is not None else 0)
            for path in run.iterdir():
                if path.name in ('wire','readiness') or path.is_symlink():continue
                if path.is_file():total+=path.stat().st_size
                elif path.is_dir():
                    total+=sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())
            manifest['artifact_bytes_observed']=total
            if total>profile['limits']['artifact_bytes']:raise ValueError('flight_artifact_limit')
    def guard(until_ns=None):
        budget();processes.check(allowed=('flight-host','px4') if args.case=='disconnect' else ('flight-host',))
        if until_ns is not None and time.monotonic_ns()>=until_ns:raise TimeoutError('flight_query_deadline')
    def wait(predicate,until,reason):
        while not predicate():
            guard()
            if receipts is not None:receipts.snapshot()
            if time.monotonic()>=until:raise TimeoutError(reason)
            time.sleep(.001)
        guard()
    try:
        if args.products:
            products=args.products.resolve()
            build_snapshot=json.loads((products/'build-sources.json').read_text())
            if any((root/n).read_text()!=v for n,v in build_snapshot.items()):raise ValueError('flight product sources changed')
            manifest['reused_products']=str(products)
        else:
            products=build(root,run,manifest)
            paths=['ros_ws/sim_flight_scene_build.py','simulation/gazebo_scene_step.cpp','simulation/scene_motion_context.cpp',
                'simulation/scene_motion_context.h','sensors/scene_motion_capture.h','sensors/gazebo_scene_radar.cpp',
                'sensors/gazebo_scene_ir.cpp','sensors/radar_measurement_model.h',
                'simulation/flight_initialization/host.cpp','simulation/flight_initialization/diagnostics.h',
                'simulation/flight_initialization/diagnostics.cpp','simulation/flight_initialization_time/adapt.py',
                'simulation/flight_bridge/adapt.py']+[str(p.relative_to(root)) for p in (root/'simulation/flight_scene').glob('*') if p.is_file()]
            write_json(products/'build-sources.json',{n:(root/n).read_text() for n in paths})
        manifest['products']=str(products)
        if args.build_only:raise BuildComplete()
        started=time.monotonic();deadline=started+240;startup=started+60
        manifest['ports_before']=probe_ports('LIVE',args.port)+probe_ports('REPORT',args.gazebo_port)
        if not all(v['free'] for v in manifest['ports_before']):raise RuntimeError('existing ports preserved')
        reject_existing_px4()
        scene=yaml.safe_load((root/'configs/sensor_scene.yaml').read_text());scene['body_pose']=[0,0,.5,0,0,0]
        create_motion_world(scene,root,run/'scene.world');write_json(run/'scene-profile.json',scene)
        create_ic(bridge/'scene/LSZH.xml',run/'initial.xml',physical.profile_reference())
        master=start_master(processes,args.port,startup)
        import rospy
        from rosgraph_msgs.msg import Clock
        from gazebo_msgs.srv import GetWorldProperties
        from uav_fusionmap_msgs.msg import AircraftState
        from uav_fusionmap_sim_scene_msgs.srv import SceneStep
        from ufm_ros_contract import to_ros_state
        from ufm_flight_contract.codec import to_ros,from_ros
        from sim_flight_scene_delivery import FlightDelivery
        from check_sim_motion_live import LiveReceipts
        rospy.init_node('sim_motion_host',disable_signals=True)
        clock_pub=rospy.Publisher('/clock',Clock,queue_size=512)
        source_pub=rospy.Publisher('/uav/sim/state',AircraftState,queue_size=512)
        handoff=FlightDelivery(root,run,run.name,scene,processes,master,wall_call,
            not args.no_native and args.case=='normal',args.previous_run_id)
        handoff.prepare_native()
        receipts=LiveReceipts(run,handoff.streams(),max_count=12288,max_wire_bytes=128*1024*1024,
            scene_codec=from_ros,scene_namespace='/uav/flight/scene',wire_directory='wire')
        handoff.receipts=receipts;handoff.launch()
        fault_step=7525 if args.case=='first-missing-ir-ack' else 7550
        for key,value in (('run_id',run.name),('drop_ack_kind',2 if 'missing-ir-ack' in args.case else 0),('drop_ack_step',fault_step)):
            master.setParam('/sim_motion_host','/ufm_flight_scene/'+key,value)
        processes.spawn('state-adapter',[sys.executable,'-B',str(root/'ros_ws/src/uav_fusionmap_sensors/scripts/state_adapter_node.py'),
            '_run_id:='+run.name,'_state_input_mode:=scene_ground_truth','_scene_registration:=gazebo_scene_world_enu_identity_v1',
            '_quaternion_norm_tolerance:=0.001','_pending_limit:=100','_pending_timeout_wall_s:=0.5',
            '_broadcast_tf:=true','_publish_odom:=true'])
        display=dict(DISPLAY=':0',XAUTHORITY='/run/user/%d/gdm/Xauthority'%os.getuid(),
            LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:'+env.get('LD_LIBRARY_PATH',''),
            LIBGL_ALWAYS_SOFTWARE='1',__GLX_VENDOR_LIBRARY_NAME='mesa',LP_NUM_THREADS='2',
            GAZEBO_PLUGIN_PATH=str(products)+':/opt/ros/noetic/lib:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins',
            GAZEBO_RESOURCE_PATH=str(root/'simulation/sensor_scene_media')+':/usr/share/gazebo-11',
            GAZEBO_MODEL_DATABASE_URI='',GAZEBO_MASTER_URI='http://127.0.0.1:'+str(args.gazebo_port))
        if handoff.native_products:display['GAZEBO_PLUGIN_PATH']+=':'+str(handoff.native_products)
        processes.spawn('gazebo-server',['/usr/bin/gzserver','--verbose','--pause','--lockstep','-s',
            'libgazebo_ros_api_plugin.so',str(run/'scene.world'),'/clock:=/diagnostics/gazebo_clock'],extra_env=display)
        handoff.launch_native(display)
        wait(lambda:clock_pub.get_num_connections()>=2 and source_pub.get_num_connections()>=2,startup,'business_not_ready')
        rospy.wait_for_service('/uav/flight/scene/step',timeout=max(.01,startup-time.monotonic()))
        service=rospy.ServiceProxy('/uav/flight/scene/step',SceneStep,persistent=True)
        world=rospy.ServiceProxy('/gazebo/get_world_properties',GetWorldProperties)
        handoff.ready(wait,startup)
        os.mkfifo(run/'steps.fifo',0o600)
        host=processes.spawn('flight-host',[str(products/'jsbsim_flight_scene'),str(bridge/'configs/rascal.xml'),
            str(run/'initial.xml'),str(run/'diagnostics'),run.name,str(run/'steps.fifo'),
            'disconnect' if args.case=='disconnect' else 'normal'])
        wait(lambda:not probe_ports('LIVE',args.port)[1]['free'],startup,'host_not_listening')
        px4=processes.spawn('px4',[str(root/'.runtime/build/px4-v1.13.3/bin/px4'),'-d',
            str(root/'.runtime/build/px4-v1.13.3/etc'),'-s','etc/init.d-posix/rcS'],run/'rootfs')
        def initial_ready():
            p=run/'diagnostics/initial.json'
            return p.exists() and p.stat().st_size>0
        wait(initial_ready,startup,'initial_readback_timeout')
        initial=json.loads((run/'diagnostics/initial.json').read_text());physical_stream=PhysicalStream(run.name,initial)
        fd=None
        def connected():
            nonlocal fd
            try:fd=os.open(run/'steps.fifo',os.O_WRONLY|os.O_NONBLOCK);return True
            except OSError as exc:
                if exc.errno!=errno.ENXIO:raise
                return False
        wait(connected,startup,'fifo_not_connected');command=os.fdopen(fd,'w',buffering=1)
        raw_stream=(run/'diagnostics/steps.jsonl').open('rb');scene_stream=(run/'diagnostics/scene-samples.jsonl').open('rb')
        def read_line(stream,until,limit=16384):
            return read_record(stream,wait,until,limit)
        initial_source=read_line(scene_stream,startup)
        registration=FlightRegistration(initial_source,initial['geodetic_latitude_rad'],initial['longitude_rad'],profile)
        write_json(run/'registration.json',registration.metadata)
        queries=ReadyQueries(root,run,px4,processes,guard,layouts)
        manifest['python_process_audit']=python_process_audit()
        if not manifest['python_process_audit']['passed']:raise ValueError('Python process mismatch')
        with (run/'transactions.jsonl').open('x') as log:
            for index in range(10001):
                guard()
                if index:
                    command.write('next\n')
                    row=read_line(raw_stream,min(deadline,time.monotonic()+1.))
                    if not physical_stream.add(row):
                        manifest['physical_failed_step']=index
                        if args.case=='disconnect' and index==126:break
                        raise ValueError('flight_physics_failed')
                    source=read_line(scene_stream,min(deadline,time.monotonic()+1.))
                else:source=initial_source
                if source['step_index']!=index:raise ValueError('flight_scene_source_sequence')
                frame=registration.convert(source,run.name);tx.begin(frame)
                begin=time.monotonic()
                answer=wall_call(lambda:service(to_ros('SceneFrame',frame)),3.2 if index==7525 else 1.2)
                decoded=from_ros('SceneStepResponse',answer,request=dict(frame=frame))
                log.write(json.dumps(dict(request=frame,response=decoded,wall_seconds=time.monotonic()-begin),allow_nan=False)+'\n');log.flush()
                if not decoded['accepted']:
                    tx.fail(decoded['reason']);manifest.update(failed_step=index,failure_reason=decoded['reason'])
                    if 'missing-ir-ack' in args.case and index==fault_step and decoded['reason']=='scene_ir_timeout':break
                    raise RuntimeError(decoded['reason'])
                state=tx.finish(decoded)
                clock_pub.publish(Clock(clock=rospy.Time(secs=0,nsecs=index*c.STEP_NS)));source_pub.publish(to_ros_state(state))
                if index in CHECKPOINTS:
                    if index==125:queries.capture(row,'parameter')
                    queries.capture(row,'topic')
                handoff.after_step(index,wait,deadline)
                if index==0:
                    graph=master.getSystemState('/sim_motion_host')[2]
                    from motion_delivery_checks import check_graph
                    check_graph(graph);write_json(run/'graph.json',graph)
                    probes=[]
                    for name in ('v1','identity','registration','nonfinite','quaternion','skipped_step'):
                        bad=to_ros('SceneFrame',frame)
                        if name=='v1':bad.protocol_version=1
                        elif name=='identity':bad.state.header.run_id='other'
                        elif name=='registration':bad.registration_id='jsbsim_cg_to_scene_enu_v1'
                        elif name=='nonfinite':bad.state.position[0]=float('nan')
                        elif name=='quaternion':bad.state.orientation_xyzw=[0.,0.,0.,0.]
                        else:bad.step_index=2
                        try:wall_call(lambda:service(bad),1.)
                        except rospy.ServiceException:probes.append(name)
                        else:raise ValueError('flight_preapply_error_returned_unversioned_response')
                    if wall_call(world,1.).sim_time!=0:raise ValueError('rejected_service_advanced')
                    write_json(run/'service-rejections.json',probes)
                if index==125 and args.case=='disconnect':processes.stop('px4')
                if index==7500:
                    ready=physical_stream.preparation_ready(queries.readiness)
                    manifest.update(preparation_ready=ready,queries=len(queries.rows),readiness=queries.readiness)
                    write_json(run/'preparation.json',dict(ready=ready,physical=physical_stream.checkpoints,
                        readiness=queries.readiness,queries=len(queries.rows),binding_status='unverified',control_gate_accepted=False))
                    if not ready or args.case=='not-ready':
                        if args.case=='not-ready':manifest['injected_not_ready']=True;break
                        raise ValueError('flight_not_ready_at_sampling_limit')
                if index==7525:
                    duplicate=from_ros('SceneStepResponse',wall_call(lambda:service(to_ros('SceneFrame',frame)),1.),request=dict(frame=frame))
                    if duplicate!=decoded:raise ValueError('flight_duplicate_changed')
                    manifest['duplicate_capture_idempotent']=True
        completed=tx.completed['step_index'];manifest['committed_step']=completed
        wait(lambda:any(v['value']['header']['timestamp']==completed*c.STEP_NS for v in receipts.snapshot().get('state',[])),
            min(deadline,time.monotonic()+1.),'last_state_missing')
        terminal=tx.terminal(manifest.get('failure_reason','scene_window_complete' if completed==10000 else 'scene_observation_stopped'))
        source_pub.publish(to_ros_state(terminal))
        wait(lambda:any(v['value']['header']['status']=='unavailable' for v in receipts.snapshot().get('state',[])),
            min(deadline,time.monotonic()+2.),'terminal_missing')
        if 'missing-ir-ack' in args.case:
            try:wall_call(lambda:service(to_ros('SceneFrame',frame)),1.)
            except rospy.ServiceException:manifest['late_request_rejected']=True
            else:raise ValueError('flight_failed_run_revived')
        handoff.finish(wait,deadline,completed,args.case!='normal')
        from sim_flight_scene_checks import validate_live
        write_json(run/'validation.json',validate_live(run,receipts.snapshot(),completed,args.case))
        manifest['wall_seconds']=time.monotonic()-started
        passed=(completed==10000 if args.case=='normal' else completed==125 if args.case=='disconnect'
            else completed==7500 if args.case=='not-ready' else completed==fault_step-1)
    except BuildComplete:
        passed=True
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__+': '+str(exc));print(manifest['errors'][-1],flush=True)
        if source_pub is not None and tx.completed is not None:
            try:source_pub.publish(to_ros_state(tx.terminal('flight_scene_failed')));time.sleep(.1)
            except Exception as error:manifest['errors'].append('terminal: '+str(error))
    finally:
        if command:
            try:
                if host.poll() is None:command.write('quit\n')
                command.close();host.wait(timeout=2);processes.stopped.add('flight-host')
                manifest['host_exit']=host.returncode
                if host.returncode not in ((20,) if args.case=='disconnect' else (0,)):passed=False
            except Exception as exc:manifest['errors'].append('host cleanup: '+str(exc));passed=False
        for stream in (raw_stream,scene_stream):
            if stream:stream.close()
        if receipts:receipts.close()
        manifest['cleanup']=processes.cleanup()
        if not args.build_only:
            manifest['ports_after']=probe_ports('LIVE',args.port)+probe_ports('REPORT',args.gazebo_port)
            if not all(v['free'] for v in manifest['ports_after']):passed=False
        manifest['source_unchanged']=source_snapshot()==snapshot
        manifest['third_party_unchanged']=all((root/n).read_text()==v for n,v in originals.items())
        manifest['native_sources_unchanged']=(all((px4_source/'msg'/(n+'.msg')).read_text()==v for n,v in native.items())
            and all((px4_source/n).read_text()==v for n,v in dict(sources,**quality).items()))
        manifest.update(physical_steps=physical_stream.count if physical_stream else 0,
            actuator_observations=physical_stream.observed if physical_stream else 0,queries=len(queries.rows) if queries else 0)
        manifest['passed']=bool(passed and not manifest['errors'] and manifest['cleanup']['passed'] and
            all(manifest[k] for k in ('source_unchanged','third_party_unchanged','native_sources_unchanged')))
        manifest['runtime_accepted']=manifest['passed'] and args.case=='normal' and not args.build_only
        write_json(run/'manifest.json',manifest)
        print(json.dumps(dict(run=str(run),passed=manifest['passed'],errors=manifest['errors'])),flush=True)
    return int(not manifest['passed'])


if __name__=='__main__':sys.exit(main())
