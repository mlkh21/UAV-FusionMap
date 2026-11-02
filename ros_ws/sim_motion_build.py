"""Isolated products; compile existing bridge sources without changing their tree."""
from pathlib import Path
import shlex
import subprocess
import sys


def build(root, run, manifest, output_directory=None):
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    output = Path(output_directory) if output_directory else root / '.runtime/sim-motion-build'
    output.mkdir(parents=True,exist_ok=True)
    bridge = root / '.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'
    jsb = root / '.runtime/deps/jsbsim-1.1.13/usr'
    generated = root / '.runtime/ros/devel/include'
    def flags(*packages):
        return shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', *packages], text=True))
    headers = list((root / 'simulation').glob('scene_motion*.h')) + [root / 'sensors/scene_motion_capture.h',
        root / 'sensors/radar_measurement_model.h']
    def compile_product(name, sources, arguments):
        product = output / name
        dependencies = [*sources, *headers, Path(__file__)]
        rebuild = not product.exists() or any(p.stat().st_mtime_ns > product.stat().st_mtime_ns for p in dependencies)
        command = ['g++', '-std=c++17', '-O1', '-pthread', *map(str, sources), '-o', str(product), *arguments]
        manifest.setdefault('builds', []).append(dict(product=str(product), command=command, rebuilt=rebuild))
        if rebuild:
            print('Building ' + name, flush=True)
            with (run / (name + '.build.log')).open('x') as stream:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=180)
            if result.returncode:
                raise RuntimeError('build failed: ' + name)
    names = ('configuration_parser jsbsim_bridge geo_mag_declination mavlink_interface actuator_plugin '
             'sensor_plugin sensor_airspeed_plugin sensor_baro_plugin sensor_imu_plugin sensor_gps_plugin sensor_mag_plugin').split()
    sources = [root / 'simulation/jsbsim_scene_host.cpp'] + [bridge / ('src/' + n + '.cpp') for n in names]
    compile_product('jsbsim_scene_host', sources, [
        '-DJSBSIM_ROOT_DIR="' + str(bridge) + '"', '-Wno-address-of-packed-member',
        '-I' + str(bridge / 'include'), '-I' + str(jsb / 'include/JSBSim'), '-I/usr/include/eigen3',
        '-I' + str(root / '.runtime/deps/ros-noetic/opt/ros/noetic/include/mavlink/v2.0'),
        str(jsb / 'lib/libJSBSim.a'), '-lboost_system', '-lboost_thread', '-ltinyxml'])
    common = ['-fPIC', '-shared', '-I' + str(generated)]
    compile_product('libufm_motion_context.so', [root / 'simulation/scene_motion_context.cpp'],
        common + flags('roscpp'))
    plugin_flags = common + ['-DUFM_SCENE_MOTION', '-L' + str(output), '-lufm_motion_context',
        '-Wl,-rpath,' + str(output)] + flags('gazebo', 'roscpp', 'OGRE', 'OGRE-Paging',
                                         'OGRE-Terrain', 'OGRE-RTShaderSystem')
    for name, source, extra in (
            ('libufm_scene_step.so', 'simulation/gazebo_scene_step.cpp', []),
            ('libufm_scene_radar.so', 'sensors/gazebo_scene_radar.cpp', []),
            ('libufm_scene_ir.so', 'sensors/gazebo_scene_ir.cpp', ['-lCameraPlugin'])):
        compile_product(name, [root / source], plugin_flags + extra)
    return output
