"""Build diagnostic-only copied bridge sources in a new .runtime/ros directory."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


def build(root, run, manifest):
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    source = root/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
    own = root/'simulation/flight_bridge'
    output = root/'.runtime/ros/sim-flight-build'/run.name
    output.mkdir(parents=True)
    shutil.copytree(source/'include', output/'include')
    shutil.copytree(source/'src', output/'src')
    spec = importlib.util.spec_from_file_location('flight_adapt', own/'adapt.py')
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for name in ('jsbsim_bridge.cpp','mavlink_interface.cpp','actuator_plugin.cpp'):
        path=output/'src'/name
        path.write_text(module.adapt(name,path.read_text()))
    jsb=root/'.runtime/deps/jsbsim-1.1.13/usr'
    names=('configuration_parser jsbsim_bridge geo_mag_declination mavlink_interface actuator_plugin '
        'sensor_plugin sensor_airspeed_plugin sensor_baro_plugin sensor_imu_plugin sensor_gps_plugin sensor_mag_plugin').split()
    sources=[own/'host.cpp',own/'diagnostics.cpp']+[output/'src'/(name+'.cpp') for name in names]
    product=output/'jsbsim_flight_diagnostics'
    command=['g++','-std=c++17','-O1','-pthread','-Wno-address-of-packed-member',
        '-DJSBSIM_ROOT_DIR="'+str(source)+'"','-I'+str(output/'include'),'-I'+str(own),
        '-I'+str(jsb/'include/JSBSim'),'-I/usr/include/eigen3',
        '-I'+str(root/'.runtime/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0'),
        *map(str,sources),'-o',str(product),str(jsb/'lib/libJSBSim.a'),
        '-lboost_system','-lboost_thread','-ltinyxml']
    manifest['builds']=[dict(product=str(product),command=command,isolated_source_copy=True)]
    with (run/'build.log').open('x') as stream:
        result=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
    if result.returncode:raise RuntimeError('flight diagnostic build failed')
    return product
