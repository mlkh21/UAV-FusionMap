"""Native RViz and standalone figure for a previously verified static real elevation crop."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import numpy as np
import yaml
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from sim01b_runtime import Processes,configure_environment,install_interrupt_handler,probe_ports,start_master,write_json


def main():
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':raise RuntimeError('wrong Python')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--port',type=int,default=11821)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    run=args.input.resolve()
    if (run/'view-manifest.json').exists() or (run/'capture-request.json').exists():
        raise ValueError('view evidence already exists; prepare a new elevation run')
    meta=json.loads((run/'metadata.json').read_text())
    if meta['schema_version']!='ufm.elevation.preview.v1':raise ValueError('unsupported elevation export')
    data=np.load(run/'terrain.npz')
    east,north,height,valid=[data[k] for k in ('east','north','height','valid')]
    origin=meta['height_min_m']
    fig,ax=plt.subplots(figsize=(9,7),layout='constrained')
    image=ax.pcolormesh(east/1000,north/1000,height,cmap='terrain',shading='nearest',rasterized=True)
    ax.set_aspect('equal');ax.set(xlabel='Local UTM easting (km)',ylabel='Local UTM northing (km)',
        title='Copernicus GLO-30 DSM | Sichuan, China\n30.75 N, 103.25 E | source pixel elevations')
    fig.colorbar(image,ax=ax,label='EGM2008 orthometric height (m)')
    fig.savefig(run/'elevation-map.png',dpi=180);plt.close(fig)
    for name in ('ros-home','ros-logs','figures','gui-home'):(run/name).mkdir(exist_ok=True)
    env=configure_environment(run,args.port)
    manifest=dict(python=sys.executable,commands=[],errors=[],source='static real elevation export')
    processes=Processes(run,env,manifest)
    install_interrupt_handler()
    passed=False
    try:
        if not all(p['free'] for p in probe_ports('TERRAIN',args.port)):raise RuntimeError('port busy')
        master=start_master(processes,args.port,time.monotonic()+15)
        master.setParam('/real_elevation_view','/use_sim_time',False)
        import rospy
        from geometry_msgs.msg import Point
        from std_msgs.msg import ColorRGBA
        from visualization_msgs.msg import Marker,MarkerArray
        from ufm_application.elevation_visualization import surface_triangles
        rospy.init_node('real_elevation_view',disable_signals=True)
        points,colours=surface_triangles(east,north,height,valid,display_height_origin_m=origin)
        marker=Marker();marker.header.frame_id='terrain_display_local';marker.ns='real_dsm_surface';marker.id=0
        marker.type=Marker.TRIANGLE_LIST;marker.action=Marker.ADD
        marker.pose.orientation.w=1.;marker.scale.x=marker.scale.y=marker.scale.z=1.
        marker.color.a=1.;marker.points=[Point(*p) for p in points];marker.colors=[ColorRGBA(*c) for c in colours]
        publisher=rospy.Publisher('/uav/terrain_demo/markers',MarkerArray,queue_size=1,latch=True)
        publisher.publish(MarkerArray(markers=[marker]))
        config=yaml.safe_load((root/'configs/terrain.rviz').read_text())
        manager=config['Visualization Manager'];manager['Global Options']['Fixed Frame']='terrain_display_local'
        manager['Displays'][0].update({'Cell Size':500,'Plane Cell Count':20})
        manager['Displays'][1].update({'Name':'Copernicus real DSM','Marker Topic':'/uav/terrain_demo/markers'})
        manager['Views']['Current'].update({'Distance':13000,'Focal Point':{'X':0,'Y':0,'Z':650},'Pitch':.75,'Yaw':.8})
        (run/'real-elevation.rviz').write_text(yaml.safe_dump(config,sort_keys=False))
        library=run/'rviz-capture.so'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','OGRE','Qt5Widgets'],text=True))
        subprocess.run(['g++','-shared','-fPIC','-std=c++14',str(root/'ros_ws/rviz_capture.cpp'),
            '-I/opt/ros/noetic/include','-L/opt/ros/noetic/lib','-lrviz',*flags,'-o',str(library)],check=True,timeout=60)
        native=dict(DISPLAY=':0',XAUTHORITY='/run/user/%d/gdm/Xauthority'%os.getuid(),
            LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:'+env.get('LD_LIBRARY_PATH',''),
            QT_QPA_PLATFORM_PLUGIN_PATH='/usr/lib/x86_64-linux-gnu/qt5/plugins',QT_X11_NO_MITSHM='1',
            LIBGL_ALWAYS_SOFTWARE='1',__GLX_VENDOR_LIBRARY_NAME='mesa',LP_NUM_THREADS='2',
            LD_PRELOAD='/usr/lib/x86_64-linux-gnu/libtiff.so.5')
        processes.spawn('rviz',[sys.executable,'-B',str(root/'tests/terrain_rviz_capture.py'),str(run),
            '--library',str(library),'--config',str(run/'real-elevation.rviz')],extra_env=native)
        deadline=time.monotonic()+30
        while not master.hasParam('/real_elevation_view','/terrain_capture/ready')[2]:
            processes.check()
            if time.monotonic()>deadline:raise RuntimeError('RViz startup timeout')
            time.sleep(.1)
        time.sleep(2)
        write_json(run/'capture-request.json',dict(label='real-elevation',topic='/uav/terrain_demo/markers'))
        while not (run/'capture-real-elevation.json').exists():
            processes.check()
            if time.monotonic()>deadline:raise RuntimeError('RViz capture timeout')
            time.sleep(.1)
        from PIL import Image
        pixels=np.asarray(Image.open(run/'figures/real-elevation.png').convert('RGB'))
        if pixels.std()<10:raise RuntimeError('elevation render blank')
        manifest.update(triangles=len(points)//3,display_height_origin_m=origin,display_frame='terrain_display_local',
            source_query_checks=49,render_pixel_std=float(pixels.std()))
        passed=True
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__+': '+str(exc))
    finally:
        if 'publisher' in locals():publisher.unregister()
        cleanup=processes.cleanup();write_json(run/'view-cleanup.json',cleanup)
        manifest['passed']=passed and cleanup['passed'] and not manifest['errors']
        write_json(run/'view-manifest.json',manifest)
    print(json.dumps(dict(run=str(run),passed=manifest['passed'],errors=manifest['errors'])))
    return int(not manifest['passed'])


if __name__=='__main__':raise SystemExit(main())
