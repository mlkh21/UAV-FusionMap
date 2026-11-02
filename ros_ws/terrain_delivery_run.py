"""Short isolated client/record/replay/RViz acceptance; no research or flight runtime."""
import argparse
import copy
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import yaml
from sim01b_runtime import (Processes,configure_environment,install_interrupt_handler,probe_ports,
                           python_process_audit,start_master,write_json)
from ufm_mapping.terrain_dataset import from_private_fixture
from ufm_mapping.terrain_recording import replay_recording


def validate_pixels(directory):
    from PIL import Image
    rows=[]
    for label in ('01-current','02-stale','03-unavailable','04-recorded'):
        path=directory/(label+'.png')
        im=Image.open(path).convert('RGB')
        pixels=list(im.getdata())
        green=sum(g>80 and g>r*1.5 and g>b*1.1 for r,g,b in pixels)
        blue=sum(b>90 and b>r*1.4 and b>g*1.15 for r,g,b in pixels)
        orange=sum(r>100 and r>g*1.2 and g>b*1.4 for r,g,b in pixels)
        if im.width<600 or im.height<400:raise ValueError('terrain viewport too small')
        if label in ('01-current','04-recorded') and (green<30 or blue<30):raise ValueError('terrain current/missing quality pixels absent')
        if label=='02-stale' and orange<30:raise ValueError('terrain stale pixels absent')
        if label=='03-unavailable' and green+blue+orange>30:raise ValueError('terrain unavailable retains colored geometry')
        rows.append(dict(path=str(path),size=list(im.size),green=green,blue=blue,orange=orange))
    return dict(passed=True,figures=rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=11691)
    parser.add_argument('--with-rviz',action='store_true')
    parser.add_argument('--display',default=':0')
    parser.add_argument('--xauthority',default='/run/user/%d/gdm/Xauthority'%os.getuid())
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('invalid port')
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':raise RuntimeError('wrong Python')
    root=Path(__file__).resolve().parents[1]
    identity='terrain-delivery-'+datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run=root/'.runtime/runs'/identity
    run.mkdir(parents=True,exist_ok=False)
    for name in ('ros-home','ros-logs','figures','gui-home'):(run/name).mkdir()
    env=configure_environment(run,args.port)
    manifest=dict(run_id=identity,python=sys.executable,commands=[],errors=[],with_rviz=args.with_rviz)
    processes=Processes(run,env,manifest)
    install_interrupt_handler()
    passed=False
    def start_provider(name,record):
        return processes.spawn(name,[sys.executable,'/opt/ros/noetic/bin/roslaunch',str(root/'ros_ws/launch/terrain_fixture.launch'),
            'enabled:=true','dataset:='+str(run/'dataset.json'),'run_id:='+identity,'clock_id:=sim:'+identity,
            'clock_publisher:=/terrain_delivery_checker','recording_directory:='+str(run/'recording') if record else 'recording_directory:='])
    try:
        manifest['ports_before']=probe_ports('TERRAIN',args.port)
        if not all(p['free'] for p in manifest['ports_before']):raise RuntimeError('port occupied; existing processes preserved')
        private=yaml.safe_load((root/'configs/m5_terrain_fixture.yaml').read_text())
        for key in ('registration','eligibility'):private[key].update(run_id=identity,clock_id='sim:'+identity)
        private['grid']['height_quality'][1]=dict(status='unavailable',kind='',value=None,unit='',source='fixture_missing_quality')
        write_json(run/'dataset.json',from_private_fixture(private))
        master=start_master(processes,args.port,time.monotonic()+15.)
        if args.with_rviz:
            library=run/'rviz-capture.so'
            flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','OGRE','Qt5Widgets'],text=True))
            build=['g++','-shared','-fPIC','-std=c++14',str(root/'ros_ws/rviz_capture.cpp'),'-I/opt/ros/noetic/include',
                '-L/opt/ros/noetic/lib','-lrviz']+flags+['-o',str(library)]
            with (run/'capture-build.log').open('x') as log:subprocess.run(build,check=True,stdout=log,stderr=subprocess.STDOUT)
            manifest['capture_build']=build
            gui_env=dict(DISPLAY=args.display,XAUTHORITY=args.xauthority,HOME=str(run/'gui-home'),
                LD_PRELOAD='/usr/lib/x86_64-linux-gnu/libtiff.so.5',
                LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:'+env.get('LD_LIBRARY_PATH',''),
                QT_QPA_PLATFORM_PLUGIN_PATH='/usr/lib/x86_64-linux-gnu/qt5/plugins',QT_X11_NO_MITSHM='1',
                LIBGL_ALWAYS_SOFTWARE='1',__GLX_VENDOR_LIBRARY_NAME='mesa',LP_NUM_THREADS='2')
            processes.spawn('rviz',[sys.executable,'-B',str(root/'tests/terrain_rviz_capture.py'),str(run),'--library',str(library)],extra_env=gui_env)
            deadline=time.monotonic()+15.
            while not master.hasParam('/terrain_delivery_launcher','/terrain_capture/ready')[2]:
                processes.check()
                if time.monotonic()>deadline:raise RuntimeError('RViz ready deadline')
                time.sleep(.1)
        start_provider('terrain-recorded',True)
        processes.spawn('markers',[sys.executable,'/opt/ros/noetic/bin/roslaunch',str(root/'ros_ws/launch/terrain_rviz_fixture.launch'),
            'enabled:=true','run_id:='+identity,'clock_id:=sim:'+identity])
        checker=processes.spawn('checker',[sys.executable,'-B',str(root/'tests/check_terrain_delivery_ros.py'),str(run),identity]+(['--with-rviz'] if args.with_rviz else []))
        restarted,stopped=False,False
        deadline=time.monotonic()+65.
        while checker.poll() is None:
            processes.check(allowed=('checker',))
            if time.monotonic()>deadline:raise RuntimeError('terrain delivery safety deadline')
            if not restarted and (run/'restart-request.json').exists():
                processes.stop('terrain-recorded')
                replay=replay_recording(run/'recording')
                write_json(run/'replay.json',replay)
                processes.spawn('recorded-view',[sys.executable,'-B',str(root/'ros_ws/terrain_recorded_view.py'),
                    '--receipt',str(run/'replay.json')])
                start_provider('terrain-restarted',False)
                restarted=True
            if not stopped and (run/'stop-request.json').exists():
                processes.stop('terrain-restarted')
                stopped=True
            time.sleep(.03)
        validation=json.loads((run/'validation.json').read_text())
        if checker.returncode or not validation['passed']:raise RuntimeError('checker failed: '+str(validation['errors']))
        manifest['python_process_audit']=python_process_audit()
        if not manifest['python_process_audit']['passed']:raise RuntimeError('Python process mismatch')
        if args.with_rviz:write_json(run/'pixel-validation.json',validate_pixels(run/'figures'))
        passed=restarted and stopped
    except Exception as exc:manifest['errors'].append(type(exc).__name__+':'+str(exc))
    finally:
        cleanup=processes.cleanup()
        try:
            cleanup['ports']=probe_ports('TERRAIN',args.port)
            cleanup['passed']=cleanup['passed'] and all(p['free'] for p in cleanup['ports'])
        except OSError as exc:
            cleanup['passed']=False;manifest['errors'].append('cleanup: '+str(exc))
        write_json(run/'cleanup-audit.json',cleanup)
        manifest['passed']=passed and cleanup['passed'] and not manifest['errors']
        write_json(run/'manifest.json',manifest)
        print(json.dumps(dict(run=str(run),passed=manifest['passed'],errors=manifest['errors'],cleanup=cleanup['passed'])),flush=True)
    return int(not manifest['passed'])


if __name__=='__main__':sys.exit(main())
