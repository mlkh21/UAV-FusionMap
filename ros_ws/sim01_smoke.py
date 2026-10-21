"""独立SIM-01A监督器：项目资产、Conda Python、仅清理本次进程组。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixture',action='store_true')
    parser.add_argument('--t14-compat',action='store_true',
                        help='enable optional Odometry/TF mirror in isolated state fixture')
    args=parser.parse_args()
    if args.t14_compat and not args.fixture:
        parser.error('--t14-compat requires --fixture')
    root=Path(__file__).resolve().parents[1]
    runtime=root/'.runtime'
    run_id=('sim01a-fixture-' if args.fixture else 'sim01a-live-')+datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run=runtime/'runs'/run_id
    run.mkdir(parents=True,exist_ok=False)
    for name in ('rootfs','ros-home','ros-logs'):
        (run/name).mkdir()
    launch='sim01_sensor_fixture.launch' if args.fixture else 'sim01_state.launch'
    for source in (root/'ros_ws/launch'/launch,root/'ros_ws/launch/sim00b_mavros.launch',root/'configs/sim01_state.yaml'):
        shutil.copy2(source,run/source.name)
    env=dict(os.environ,ROS_MASTER_URI='http://127.0.0.1:11331',ROS_IP='127.0.0.1',
             ROS_HOME=str(run/'ros-home'),ROS_LOG_DIR=str(run/'ros-logs'),
             HEADLESS='1',PX4_SIM_MODEL='rascal',PX4_SIM_SPEED_FACTOR='1',MAVLINK20='1')
    manifest=dict(run_id=run_id,run=str(run),fixture=args.fixture,t14_compat=args.t14_compat,python=sys.executable,
                  supervisor_pid=os.getpid(),ros_master_uri=env['ROS_MASTER_URI'],commands=[],errors=[],armed_commands=False,
                  px4_commit='1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa',
                  bridge_commit='68de2cc63ded9a0d6641d45e9eb3ed2b43454cba',patch='SIM00B-INIT-01')
    children,handles=[],[]
    started=time.monotonic()
    ports=[(socket.SOCK_STREAM,[11331])] if args.fixture else [
        (socket.SOCK_STREAM,[11331,4560]),(socket.SOCK_DGRAM,[14540,14580,18570,14280,13030])]

    def spawn(name,command,cwd=None):
        handle=(run/(name+'.log')).open('x')
        handles.append(handle)
        process=subprocess.Popen(command,cwd=cwd or run,env=env,stdin=subprocess.DEVNULL,
                                  stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
        children.append((name,process))
        manifest['commands'].append(dict(name=name,args=command,pid=process.pid))
        return process

    def probe_ports():
        result=[]
        for kind,numbers in ports:
            for number in numbers:
                with socket.socket(socket.AF_INET,kind) as probe:
                    if kind==socket.SOCK_STREAM:
                        probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                    try:
                        probe.bind(('0.0.0.0',number))
                        result.append(dict(port=number,free=True))
                    except OSError as exc:
                        result.append(dict(port=number,free=False,error=str(exc)))
        return result

    def interrupt(signum,frame):
        raise RuntimeError('supervisor interrupted: '+str(signum))

    def python_process_audit():
        # 只记录本监督器后代的命令；不读取其他用户/任务的进程参数。
        parents={}
        for entry in Path('/proc').glob('[0-9]*'):
            try:
                text=(entry/'stat').read_text()
                fields=text[text.rfind(')')+2:].split()
                parents[int(entry.name)]=int(fields[1])
            except (FileNotFoundError,PermissionError,ProcessLookupError):
                pass
        owned={os.getpid()}
        while True:
            expanded=owned|{pid for pid,parent in parents.items() if parent in owned}
            if expanded==owned:
                break
            owned=expanded
        records=[]
        for pid in sorted(owned):
            try:
                exe=(Path('/proc')/str(pid)/'exe').resolve(strict=True)
                if exe.name.startswith('python'):
                    command=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode().split('\0')
                    records.append(dict(pid=pid,executable=str(exe),args=[a for a in command if a]))
            except (FileNotFoundError,PermissionError,ProcessLookupError):
                pass
        expected=str(Path(os.environ['UFM_PYTHON']).resolve())
        return dict(passed=bool(records) and all(r['executable']==expected for r in records),
                    expected=expected,processes=records)

    signal.signal(signal.SIGINT,interrupt)
    signal.signal(signal.SIGTERM,interrupt)
    result=1
    try:
        if sys.executable!=str(Path(os.environ['UFM_PYTHON'])):
            raise RuntimeError('supervisor must use configured Conda Python')
        before=probe_ports()
        manifest['ports_before']=before
        if any(not item['free'] for item in before):
            raise RuntimeError('required port occupied; existing process preserved')
        if not args.fixture:
            for comm in Path('/proc').glob('[0-9]*/comm'):
                try:
                    if comm.read_text().strip()=='px4':
                        raise RuntimeError('existing PX4 preserved; run stopped')
                except FileNotFoundError:
                    pass
        spawn('roscore',[sys.executable,'/opt/ros/noetic/bin/roscore','-p','11331'])
        master=xmlrpc.client.ServerProxy(env['ROS_MASTER_URI'])
        for _ in range(100):
            try:
                if master.getPid('/sim01a_supervisor')[0]==1:
                    break
            except OSError:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError('ROS master startup timeout')
        if not args.fixture:
            observer=spawn('observer',[sys.executable,str(root/'tests/check_sim01_live.py'),str(run),run_id])
        state_command=[sys.executable,'/opt/ros/noetic/bin/roslaunch',str(run/launch),'run_id:='+run_id]
        if args.fixture:
            state_command += ['publish_odom:=true','broadcast_tf:=true'] if args.t14_compat else []
        else:
            state_command += ['config:='+str(run/'sim01_state.yaml')]
        spawn('state_nodes',state_command)
        if args.fixture:
            observer_args=['--t14-compat'] if args.t14_compat else []
            observer=spawn('observer',[sys.executable,str(root/'tests/check_sim01_ros_fixture.py'),str(run),run_id]+observer_args)
        else:
            spawn('bridge',[str(runtime/'build/jsbsim-bridge-init01/jsbsim_bridge'),'rascal','-s',
                            str(runtime/'src/px4-v1.13.3/Tools/jsbsim_bridge/scene/LSZH.xml')])
            time.sleep(1)
            spawn('px4',[str(runtime/'build/px4-v1.13.3/bin/px4'),'-d',str(runtime/'build/px4-v1.13.3/etc'),
                         '-s','etc/init.d-posix/rcS'],run/'rootfs')
            spawn('mavros',[sys.executable,'/opt/ros/noetic/bin/roslaunch',str(run/'sim00b_mavros.launch')])
        configured=args.fixture
        while time.monotonic()-started<180:
            if 'python_process_audit' not in manifest and time.monotonic()-started>=3:
                manifest['python_process_audit']=python_process_audit()
                if not manifest['python_process_audit']['passed']:
                    raise RuntimeError('a Python descendant does not use configured Conda environment')
            if observer.poll() is not None:
                result=observer.returncode
                break
            for name,process in children:
                if name!='observer' and process.poll() is not None:
                    raise RuntimeError(name+' exited: '+str(process.returncode))
            if not configured and 'Startup script returned successfully' in (run/'px4.log').read_text(errors='replace'):
                for stream,rate in (('HIGHRES_IMU','50'),('ODOMETRY','20')):
                    command=[str(runtime/'build/px4-v1.13.3/bin/px4-mavlink'),'stream','-u','14580','-s',stream,'-r',rate]
                    with (run/('stream-'+stream+'.log')).open('x') as handle:
                        code=subprocess.run(command,cwd=run/'rootfs',env=env,stdout=handle,stderr=subprocess.STDOUT,timeout=5).returncode
                    manifest['commands'].append(dict(name='stream-'+stream,args=command,exit=code))
                    if code:
                        raise RuntimeError('stream configuration failed')
                configured=True
            time.sleep(.05)
        else:
            raise RuntimeError('light test wall time safety limit')
    except Exception as exc:
        manifest['errors'].append(str(exc))
    finally:
        ordered=[item for item in children if item[0]=='observer']+[item for item in reversed(children) if item[0]!='observer']
        for name,process in ordered:
            if process.poll() is None:
                try:
                    os.killpg(process.pid,signal.SIGINT)
                except ProcessLookupError:
                    pass
        for name,process in ordered:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL)
                    process.wait()
            manifest.setdefault('exits',{})[name]=process.returncode
        for handle in handles:
            handle.close()
        after=probe_ports()
        cleanup=dict(passed=all(item['free'] for item in after) and all(p.poll() is not None for _,p in children),
                     ports=after,children=[dict(name=n,pid=p.pid,exit=p.returncode) for n,p in children])
        (run/'cleanup-audit.json').write_text(json.dumps(cleanup,indent=2)+'\n')
        if not cleanup['passed']:
            result=1
            manifest['errors'].append('cleanup audit failed')
        manifest.update(exit=result,wall_seconds=time.monotonic()-started)
        (run/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        print(json.dumps(dict(run=str(run),exit=result,errors=manifest['errors'],cleanup=cleanup['passed'])),flush=True)
    return result


if __name__=='__main__':
    sys.exit(main())
