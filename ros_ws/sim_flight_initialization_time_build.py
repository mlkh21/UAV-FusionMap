"""Explicit isolated producer-time build; no writes to original bridge or old products."""
import importlib.util
import shutil
import subprocess
import sys
import time


def module_from(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def build(root,run,manifest):
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    source=root/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
    own=root/'simulation/flight_initialization'
    timer=root/'simulation/flight_initialization_time'
    output=root/'.runtime/ros/sim-flight-initialization-time-build'/run.name
    output.mkdir(parents=True)
    for name in ('include','src'):shutil.copytree(source/name,output/name)
    old=module_from(root/'simulation/flight_bridge/adapt.py','original_time_observer_adapter')
    new=module_from(timer/'adapt.py','integer_time_producer_adapter')
    for name in ('jsbsim_bridge.cpp','mavlink_interface.cpp','actuator_plugin.cpp'):
        path=output/'src'/name
        path.write_text(old.adapt(name,path.read_text()))
    for name in ('jsbsim_bridge.cpp','sensor_gps_plugin.cpp'):
        path=output/'src'/name
        path.write_text(new.adapt(name,path.read_text()))
    diagnostics=output/'diagnostics.cpp'
    diagnostics.write_text(new.adapt('diagnostics.cpp',(own/'diagnostics.cpp').read_text()))
    jsb=root/'.runtime/deps/jsbsim-1.1.13/usr'
    names=('configuration_parser jsbsim_bridge geo_mag_declination mavlink_interface actuator_plugin '
        'sensor_plugin sensor_airspeed_plugin sensor_baro_plugin sensor_imu_plugin sensor_gps_plugin sensor_mag_plugin').split()
    product=output/'jsbsim_initialization_time'
    command=['g++','-std=c++17','-O1','-pthread','-Wno-address-of-packed-member',
        '-DJSBSIM_ROOT_DIR="'+str(source)+'"','-I'+str(output/'include'),'-I'+str(own),'-I'+str(timer),
        '-I'+str(jsb/'include/JSBSim'),'-I/usr/include/eigen3',
        '-I'+str(root/'.runtime/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0'),
        str(own/'host.cpp'),str(diagnostics),*[str(output/'src'/(n+'.cpp')) for n in names],
        '-o',str(product),str(jsb/'lib/libJSBSim.a'),'-lboost_system','-lboost_thread','-ltinyxml']
    manifest['builds']=[dict(product=str(product),command=command,isolated_source_copy=True,
        time_policy='source_step_grid_4ms_checked_1ns_before_serialization',source_receipts='diagnostics/time-grid.jsonl')]
    started=time.monotonic_ns()
    with (run/'build.log').open('x') as stream:
        child=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
    manifest['build_wall_ns']=time.monotonic_ns()-started
    if child.returncode or manifest['build_wall_ns']>180000000000:
        raise RuntimeError('integer time build failed; see build.log')
    with (run/'host-offline-guards.json').open('x') as stream:
        child=subprocess.run([str(product),'--self-test'],stdout=stream,stderr=subprocess.STDOUT,timeout=5)
    if child.returncode:raise RuntimeError('host offline guards failed')
    return product
