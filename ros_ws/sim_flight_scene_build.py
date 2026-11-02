"""Explicit isolated flight host and v2 plugin products, leaving legacy products intact."""
import shlex
import shutil
import subprocess
import sys

from sim_flight_initialization_time_build import module_from


def build(root, run, manifest):
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    source=root/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
    output=root/'.runtime/ros/sim-flight-scene-build'/run.name
    output.mkdir(parents=True,exist_ok=False)
    own=root/'simulation/flight_initialization'; timer=root/'simulation/flight_scene'
    for directory in ('include','src'):shutil.copytree(source/directory,output/directory)
    original=module_from(root/'simulation/flight_bridge/adapt.py','scene_observer_adapter')
    integer=module_from(root/'simulation/flight_initialization_time/adapt.py','scene_time_adapter')
    scene=module_from(timer/'adapt.py','scene_host_adapter')
    for name in ('jsbsim_bridge.cpp','mavlink_interface.cpp','actuator_plugin.cpp'):
        p=output/'src'/name;p.write_text(original.adapt(name,p.read_text()))
    for name in ('jsbsim_bridge.cpp','sensor_gps_plugin.cpp'):
        p=output/'src'/name;p.write_text(integer.adapt(name,p.read_text()))
    for name in ('host.cpp','diagnostics.cpp'):
        (output/name).write_text(scene.adapt(name,(own/name).read_text()))
    def compile(name,sources,flags):
        product=output/name
        command=['g++','-std=c++17','-O1','-pthread',*map(str,sources),'-o',str(product),*flags]
        manifest.setdefault('builds',[]).append(dict(product=str(product),command=command))
        with (run/(name+'.build.log')).open('x') as stream:
            result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
        if result.returncode:raise RuntimeError('flight build failed: '+name)
    jsb=root/'.runtime/deps/jsbsim-1.1.13/usr'
    names=('configuration_parser jsbsim_bridge geo_mag_declination mavlink_interface actuator_plugin '
        'sensor_plugin sensor_airspeed_plugin sensor_baro_plugin sensor_imu_plugin sensor_gps_plugin sensor_mag_plugin').split()
    compile('jsbsim_flight_scene',[output/'host.cpp',output/'diagnostics.cpp',
        *[output/'src'/(n+'.cpp') for n in names]],[
        '-Wno-address-of-packed-member','-DJSBSIM_ROOT_DIR="'+str(source)+'"',
        '-I'+str(output/'include'),'-I'+str(timer),'-I'+str(own),'-I'+str(jsb/'include/JSBSim'),
        '-I/usr/include/eigen3','-I'+str(root/'.runtime/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0'),
        str(jsb/'lib/libJSBSim.a'),'-lboost_system','-lboost_thread','-ltinyxml'])
    with (run/'host-offline-guards.json').open('x') as stream:
        result=subprocess.run([str(output/'jsbsim_flight_scene'),'--self-test'],stdout=stream,timeout=5)
    if result.returncode:raise RuntimeError('flight zero-control guards failed')
    def flags(*packages):
        return shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs',*packages],text=True))
    shared=['-fPIC','-shared','-I'+str(root/'.runtime/ros/devel/include')]
    compile('libufm_motion_context.so',[root/'simulation/scene_motion_context.cpp'],shared+flags('roscpp'))
    plugins=shared+['-DUFM_SCENE_MOTION','-DUFM_FLIGHT_SCENE','-L'+str(output),'-lufm_motion_context',
        '-Wl,-rpath,'+str(output)]+flags('gazebo','roscpp','OGRE','OGRE-Paging','OGRE-Terrain','OGRE-RTShaderSystem')
    for name,path,extra in (('libufm_scene_step.so','simulation/gazebo_scene_step.cpp',[]),
            ('libufm_scene_radar.so','sensors/gazebo_scene_radar.cpp',[]),
            ('libufm_scene_ir.so','sensors/gazebo_scene_ir.cpp',['-lCameraPlugin'])):
        compile(name,[root/path],plugins+extra)
    return output
