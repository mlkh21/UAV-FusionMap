"""Build a new preparation host using copies of the original bridge sources."""
import importlib.util
import shutil
import subprocess
import sys
import time


def build(root,run,manifest):
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    source=root/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
    own=root/'simulation/flight_initialization'
    output=root/'.runtime/ros/sim-flight-initialization-build'/run.name
    output.mkdir(parents=True)
    for directory in ('include','src'):shutil.copytree(source/directory,output/directory)
    spec=importlib.util.spec_from_file_location('preparation_exact_adapt',root/'simulation/flight_bridge/adapt.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for name in ('jsbsim_bridge.cpp','mavlink_interface.cpp','actuator_plugin.cpp'):
        path=output/'src'/name
        path.write_text(module.adapt(name,path.read_text()))
    jsb=root/'.runtime/deps/jsbsim-1.1.13/usr'
    names=('configuration_parser jsbsim_bridge geo_mag_declination mavlink_interface actuator_plugin '
        'sensor_plugin sensor_airspeed_plugin sensor_baro_plugin sensor_imu_plugin sensor_gps_plugin sensor_mag_plugin').split()
    product=output/'jsbsim_initialization'
    command=['g++','-std=c++17','-O1','-pthread','-Wno-address-of-packed-member',
        '-DJSBSIM_ROOT_DIR="'+str(source)+'"','-I'+str(output/'include'),'-I'+str(own),
        '-I'+str(jsb/'include/JSBSim'),'-I/usr/include/eigen3',
        '-I'+str(root/'.runtime/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0'),
        str(own/'host.cpp'),str(own/'diagnostics.cpp'),*[str(output/'src'/(n+'.cpp')) for n in names],
        '-o',str(product),str(jsb/'lib/libJSBSim.a'),'-lboost_system','-lboost_thread','-ltinyxml']
    manifest['builds']=[dict(product=str(product),command=command,isolated_source_copy=True)]
    start=time.monotonic_ns()
    with (run/'build.log').open('x') as stream:
        result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
    manifest['build_wall_ns']=time.monotonic_ns()-start
    if result.returncode or manifest['build_wall_ns']>180000000000:
        raise RuntimeError('preparation build failed; see build.log')
    with (run/'host-offline-guards.json').open('x') as stream:
        result=subprocess.run([str(product),'--self-test'],stdout=stream,stderr=subprocess.STDOUT,timeout=5)
    if result.returncode:raise RuntimeError('host offline guards failed')
    return product
