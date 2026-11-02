"""Launch an isolated Gazebo scene and standard RViz sensor displays."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import yaml

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, python_process_audit, start_master, write_json)
from ufm_simulation.sensor_scene import create_world
from ufm_sensors.scene_stream import validate_scene_profile


def build_tools(root, run, manifest, output_directory=None):
    build_root = Path(output_directory) if output_directory else root / '.runtime/sensor-scene-build'
    build_root.mkdir(parents=True,exist_ok=True)
    for name, source, packages, extra in (
            ('libufm_scene_radar.so', 'sensors/gazebo_scene_radar.cpp', ('gazebo', 'roscpp'), []),
            ('libufm_scene_ir.so', 'sensors/gazebo_scene_ir.cpp', ('gazebo', 'roscpp'), ['-lCameraPlugin']),
            ('libufm_scene_pose.so', 'simulation/gazebo_scene_pose.cpp', ('gazebo', 'roscpp'), []),
            ('libufm_scene_gui.so', 'simulation/gazebo_scene_gui.cpp', ('gazebo', 'Qt5Widgets'), []),
            ('native_scene_rviz', 'ros_ws/native_scene_rviz.cpp', ('rviz', 'Qt5Widgets', 'roscpp'), [])):
        source, product = root / source, build_root / name
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', *packages,
            'OGRE', 'OGRE-Paging', 'OGRE-Terrain', 'OGRE-RTShaderSystem'], text=True))
        command = ['g++', '-std=c++17', '-O1', '-fPIC']
        if name.endswith('.so'):command.append('-shared')
        command += [str(source), '-o', str(product)] + flags + extra
        dependencies = [source]
        if 'radar' in name:dependencies.append(root/'sensors/radar_measurement_model.h')
        rebuild = not product.is_file() or any(p.stat().st_mtime_ns > product.stat().st_mtime_ns for p in dependencies)
        manifest.setdefault('builds', []).append(dict(command=command, rebuilt=rebuild))
        if rebuild:
            print('Building ' + name, flush=True)
            with (run / (name + '-build.log')).open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
                if result.returncode:raise RuntimeError('build failed: ' + name + '; see ' + log.name)
    return build_root, build_root / 'native_scene_rviz'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='bounded ROS, scene and GUI acceptance')
    parser.add_argument('--debug-rviz', action='store_true', help='parent debugger for owned RViz teardown')
    parser.add_argument('--duration-s', type=float, default=0., help='0: until a window closes or Ctrl-C')
    parser.add_argument('--port', type=int, default=11711)
    parser.add_argument('--gazebo-port', type=int, default=11712)
    parser.add_argument('--display', default=':0')
    parser.add_argument('--xauthority', default='/run/user/%d/gdm/Xauthority' % os.getuid())
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if (args.duration_s < 0 or args.port == args.gazebo_port or
            any(not 1024 <= port <= 65535 for port in (args.port, args.gazebo_port))):
        parser.error('invalid duration or ports')
    root = Path(__file__).resolve().parents[1]
    identity = 'sensor-scene-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True)
    for name in ('ros-home', 'ros-logs', 'gui-home', 'figures'):(run / name).mkdir()
    env = configure_environment(run, args.port)
    manifest = dict(run_id=identity, python=sys.executable, commands=[], errors=[],
        scope='Independent functional sensor scene; not PX4/JSBSim flight or physical sensor acceptance')
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    try:
        manifest['ports_before'] = probe_ports('REPORT', args.port) + probe_ports('REPORT', args.gazebo_port)
        if not all(row['free'] for row in manifest['ports_before']):
            raise RuntimeError('port busy; existing sessions preserved; choose another port pair')
        plugins, rviz = build_tools(root, run, manifest)
        profile = yaml.safe_load((root / 'configs/sensor_scene.yaml').read_text())
        validate_scene_profile(profile)
        (run / 'profile.yaml').write_text(yaml.safe_dump(profile, sort_keys=False))
        create_world(profile, root, run / 'scene.world')
        settings = dict(profile['map'], schema_version='local_map_fixture.v1')
        (run / 'map.yaml').write_text(yaml.safe_dump(settings, sort_keys=False))
        (run / 'sensor_scene.rviz').write_text((root / 'configs/sensor_scene.rviz').read_text())
        master = start_master(processes, args.port, time.monotonic() + 15.)
        for key, value in (('/perf01a_require_observers', False), ('/ufm_diagnostics_enabled', False),
                           ('/ufm_local_map_config', str(run / 'map.yaml')),
                           ('/perf01a_image_buff_size', 4 * 1024 * 1024)):
            master.setParam('/sensor_scene_launcher', key, value)
        processes.spawn('scene-state-source', [sys.executable, '-B', str(root / 'ros_ws/scene_state_source.py'),
            '--run-id', identity])
        processes.spawn('state-adapter', [sys.executable, '-B', str(root /
            'ros_ws/src/uav_fusionmap_sensors/scripts/state_adapter_node.py'),
            '_run_id:=' + identity, '_state_input_mode:=scene_ground_truth',
            '_scene_registration:=' + profile['world_to_odom_registration'],
            '_quaternion_norm_tolerance:=0.001', '_pending_limit:=100', '_pending_timeout_wall_s:=0.5',
            '_broadcast_tf:=true', '_publish_odom:=true'])
        for name, xyz, quaternion in (('radar', profile['radar_mount_xyz'], [0,0,0,1]),
                                     ('thermal_optical', profile['thermal_mount_xyz'], profile['thermal_optical_xyzw'])):
            processes.spawn('mount-' + name, ['/opt/ros/noetic/lib/tf2_ros/static_transform_publisher',
                *map(str, xyz + quaternion), 'base_link', name])
        processes.spawn('sensor-adapter', [sys.executable, '-B', str(root / 'ros_ws/scene_sensor_node.py'),
            '--run-id', identity, '--profile', str(run / 'profile.yaml'), '--audit', str(run / 'sensor-audit.json')])
        processes.spawn('placeholder', [sys.executable, '-B', str(root /
            'ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py'),
            '_run_id:=' + identity, '_mode:=placeholder'])
        processes.spawn('mapping', [sys.executable, '-B', str(root /
            'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'),
            '_run_id:=' + identity, '_enable_query:=true', '_free_threshold:=0.3', '_occupied_threshold:=0.7'])
        processes.spawn('map-visualizer', [sys.executable, '-B', str(root / 'ros_ws/scene_map_viz.py'),
            '--clock-id', 'sim:' + identity, '--ttl-ns', str(profile['map']['staleness_limit_ns'])])
        native_env = dict(DISPLAY=args.display, XAUTHORITY=args.xauthority,
            HOME=str(run / 'gui-home'), XDG_CONFIG_HOME=str(run / 'gui-home/config'),
            XDG_CACHE_HOME=str(run / 'gui-home/cache'),
            LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:' + env.get('LD_LIBRARY_PATH', ''),
            QT_QPA_PLATFORM_PLUGIN_PATH='/usr/lib/x86_64-linux-gnu/qt5/plugins', QT_X11_NO_MITSHM='1',
            QT_AUTO_SCREEN_SCALE_FACTOR='0', QT_SCALE_FACTOR='1', QT_FONT_DPI='96',
            LIBGL_ALWAYS_SOFTWARE='1', __GLX_VENDOR_LIBRARY_NAME='mesa', LP_NUM_THREADS='2',
            GAZEBO_PLUGIN_PATH=str(plugins) + ':/opt/ros/noetic/lib:/usr/lib/x86_64-linux-gnu/gazebo-11/plugins',
            GAZEBO_RESOURCE_PATH=str(root / 'simulation/sensor_scene_media') + ':/usr/share/gazebo-11',
            GAZEBO_MODEL_DATABASE_URI='', GAZEBO_MASTER_URI='http://127.0.0.1:' + str(args.gazebo_port),
            UFM_SCENE_FIGURES=str(run / 'figures'))
        processes.spawn('gazebo-server', ['/usr/bin/gzserver', '--verbose', '--lockstep', '-s',
            'libgazebo_ros_api_plugin.so', str(run / 'scene.world')], extra_env=native_env)
        gui = processes.spawn('gazebo-window', ['/usr/bin/gzclient', '--verbose'], extra_env=native_env)
        rviz_command = [str(rviz), str(run / 'sensor_scene.rviz')]
        if args.debug_rviz:
            rviz_command = ['/usr/bin/gdb', '-q', '-batch', '--return-child-result', '-ex', 'run', '-ex', 'thread apply all bt 15',
                            '--args'] + rviz_command
        display = processes.spawn('rviz-window', rviz_command,
            extra_env=dict(native_env, **({'UFM_RVIZ_CLOSE_AFTER_S':'20'} if args.debug_rviz else {})))
        observer = processes.spawn('scene-check', [sys.executable, '-B', str(root / 'tests/check_sensor_scene_ros.py'),
            '--run', str(run), '--run-id', identity]) if args.check else None
        print(json.dumps(dict(run=str(run), ros_master=env['ROS_MASTER_URI'],
            windows=['Gazebo scene', 'RViz Radar / IR / placeholder map'])), flush=True)
        started = time.monotonic()
        audited = False
        while gui.poll() is None and display.poll() is None:
            processes.check(allowed=('gazebo-window', 'rviz-window', 'scene-check'))
            elapsed = time.monotonic() - started
            if not audited and elapsed > 5.:
                manifest['python_process_audit'] = python_process_audit()
                if not manifest['python_process_audit']['passed']:raise RuntimeError('Python process audit failed')
                audited = True
            if observer and observer.poll() is not None:
                if observer.returncode:raise RuntimeError('scene ROS acceptance failed; see scene-check.log')
                figures = list((run / 'figures').glob('gazebo-scene-*.png'))
                rviz_figures = [p for p in (run / 'figures').glob('rviz-sensors-*.png') if 'viewport' not in p.name]
                if figures and rviz_figures:
                    pixels = processes.spawn('figure-check', [sys.executable, '-B',
                        str(root / 'tests/check_sensor_scene_figures.py'), str(run / 'figures')])
                    if pixels.wait(timeout=15.):raise RuntimeError('native render pixel validation failed')
                    manifest['graph'] = master.getSystemState('/sensor_scene_launcher')[2]
                    forbidden = [name for publishers in manifest['graph'][:2] for topic, nodes in publishers
                                 for name in [topic, *nodes] if any(token in name.lower()
                                 for token in ('lidar', 'training', 'observed_mask', 'target'))]
                    if forbidden:raise RuntimeError('training graph in sensor scene: ' + repr(forbidden))
                    passed = True
                    break
            if args.check and elapsed > 90.:raise RuntimeError('scene acceptance timeout')
            if args.duration_s and elapsed >= args.duration_s:
                passed = not args.check
                break
            time.sleep(.1)
        else:
            if args.check:raise RuntimeError('a GUI closed before acceptance')
            passed = all(p.poll() in (None, 0) for p in (gui, display))
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        cleanup = processes.cleanup()
        cleanup['ports'] = probe_ports('REPORT', args.port) + probe_ports('REPORT', args.gazebo_port)
        cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        manifest['passed'] = passed and cleanup['passed'] and not manifest['errors']
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=manifest['passed'], errors=manifest['errors'])), flush=True)
    return int(not manifest['passed'])


if __name__ == '__main__':
    sys.exit(main())
