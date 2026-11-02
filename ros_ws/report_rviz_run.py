"""Isolated native RViz workbench launcher, demo/live/public snapshot replay."""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import shlex
import subprocess
import sys
import time
import yaml

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, start_master, write_json, python_process_audit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('demo', 'live', 'replay'), default='demo')
    parser.add_argument('--master-uri', help='required existing master for live mode')
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--port', type=int, default=11701)
    parser.add_argument('--display', default=':0')
    parser.add_argument('--xauthority', default='/run/user/%d/gdm/Xauthority' % os.getuid())
    parser.add_argument('--render-backend', choices=('software', 'system'), default='software',
                        help='explicit Mesa software rendering for repeatable report sessions')
    parser.add_argument('--duration-s', type=float, default=0., help='0: until window closes')
    parser.add_argument('--ttl-ns', type=int)
    parser.add_argument('--clock-id', help='explicit ROS clock domain for live mode')
    parser.add_argument('--free-threshold', type=float)
    parser.add_argument('--occupied-threshold', type=float)
    parser.add_argument('--exercise', action='store_true', help='bounded native GUI acceptance; demo or replay')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if not 1024 <= args.port <= 65535 or args.duration_s < 0:
        parser.error('invalid port or duration')
    if args.mode == 'live' and (not args.master_uri or args.ttl_ns is None or not args.clock_id):
        parser.error('live requires explicit --master-uri, --clock-id and --ttl-ns matching the map')
    if args.mode != 'live' and args.master_uri:
        parser.error('--master-uri is only for live; existing masters are never replaced')
    if (args.mode == 'replay') != bool(args.receipt):
        parser.error('--receipt is required only for replay')
    if args.exercise and args.mode == 'live':parser.error('--exercise requires demo or replay')
    if args.mode != 'demo' and args.ttl_ns is None:parser.error('explicit --ttl-ns required')
    if args.receipt:
        args.receipt = args.receipt.resolve()
        if not args.receipt.is_file():parser.error('public receipt file does not exist')
    root = Path(__file__).resolve().parents[1]
    identity = 'report-rviz-' + datetime.datetime.now(datetime.timezone(
        datetime.timedelta(hours=8))).strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True)
    for name in ('ros-home', 'ros-logs', 'figures', 'gui-home'):(run / name).mkdir()
    env = configure_environment(run, args.port)
    if args.mode == 'live':env['ROS_MASTER_URI'] = args.master_uri
    manifest = dict(run_id=identity, mode=args.mode, render_backend=args.render_backend,
        python=sys.executable, commands=[], errors=[],
        scope='ROS/RViz engineering presentation; not model or flight acceptance')
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    try:
        capture_library = run / 'rviz-capture.so'
        flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'OGRE', 'Qt5Widgets'], text=True)
        build = ['g++', '-shared', '-fPIC', '-std=c++14', str(root / 'ros_ws/rviz_capture.cpp'),
                 '-I/opt/ros/noetic/include', '-L/opt/ros/noetic/lib', '-lrviz'] + shlex.split(flags) + [
                 '-o', str(capture_library)]
        subprocess.run(build, check=True, stdout=(run / 'capture-build.log').open('x'), stderr=subprocess.STDOUT)
        manifest['capture_build_command'] = build
        if args.mode != 'live':
            manifest['ports_before'] = probe_ports('REPORT', args.port)
            if any(not item['free'] for item in manifest['ports_before']):
                raise RuntimeError('port busy; existing processes preserved')
            start_master(processes, args.port, time.monotonic() + 15.)
        if args.mode == 'demo':
            spec = yaml.safe_load((root / 'configs/m4_fixture.yaml').read_text())
            spec['registration'].update(run_id=identity, clock_id='sim:' + identity)
            (run / 'm4-config.yaml').write_text(yaml.safe_dump(spec, sort_keys=False))
            arithmetic = spec['local_map']['arithmetic']
            args.ttl_ns = arithmetic['evidence_ttl_ns']
            args.clock_id = 'sim:' + identity
            args.free_threshold, args.occupied_threshold = arithmetic['free_threshold'], arithmetic['occupied_threshold']
            # This fixture does not require diagnostic observers or invent a model source.
            import xmlrpc.client
            master = xmlrpc.client.ServerProxy(env['ROS_MASTER_URI'])
            master.setParam('/report_supervisor', '/perf01a_require_observers', False)
            master.setParam('/report_supervisor', '/ufm_diagnostics_enabled', False)
            processes.spawn('mapping', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
                str(root / 'ros_ws/launch/m4_fixture.launch'), 'run_id:=' + identity,
                'clock_id:=sim:' + identity, 'm4_fixture_config:=' + str(run / 'm4-config.yaml')])
            processes.spawn('scene', [sys.executable, '-B', str(root / 'tests/report_scene_fixture.py'), str(run), identity],
                            extra_env={'PYTHONPATH':str(root / 'tests') + ':' + env.get('PYTHONPATH', '')})
        gui_env = dict(DISPLAY=args.display, XAUTHORITY=args.xauthority,
            HOME=str(run / 'gui-home'), XDG_CONFIG_HOME=str(run / 'gui-home/config'),
            XDG_CACHE_HOME=str(run / 'gui-home/cache'),
            LD_PRELOAD='/usr/lib/x86_64-linux-gnu/libtiff.so.5',
            LD_LIBRARY_PATH='/usr/lib/x86_64-linux-gnu:' + env.get('LD_LIBRARY_PATH', ''),
            QT_QPA_PLATFORM_PLUGIN_PATH='/usr/lib/x86_64-linux-gnu/qt5/plugins',
            QT_X11_NO_MITSHM='1')
        if args.render_backend == 'software':
            gui_env.update(LIBGL_ALWAYS_SOFTWARE='1', __GLX_VENDOR_LIBRARY_NAME='mesa', LP_NUM_THREADS='2')
        command = [sys.executable, '-X', 'faulthandler', '-B', str(root / 'ros_ws/report_rviz.py'), '--output', str(run / 'figures'),
                   '--ttl-ns', str(args.ttl_ns), '--clock-id', args.clock_id or 'recorded-snapshot',
                   '--capture-library', str(capture_library)]
        for flag, value in (('--free-threshold', args.free_threshold), ('--occupied-threshold', args.occupied_threshold),
                            ('--receipt', args.receipt)):
            if value is not None:command += [flag, str(value)]
        if args.exercise:command.append('--exercise')
        gui = processes.spawn('rviz-ui', command, extra_env=gui_env)
        print(json.dumps(dict(run=str(run), window='RViz', mode=args.mode)), flush=True)
        started = time.monotonic()
        audit_done = False
        while gui.poll() is None:
            processes.check(allowed=('rviz-ui',))
            if args.exercise and args.mode == 'demo' and 'mapping' not in processes.stopped and master.getParam(
                    '/report_supervisor', '/uav/report_fixture/stop_mapping')[2] is True:
                manifest['graph_before_mapping_stop'] = master.getSystemState('/report_supervisor')[2]
                processes.stop('mapping')
                manifest['mapping_stopped_for_service_loss_test'] = True
            elapsed = time.monotonic() - started
            if not audit_done and elapsed > 3.:
                manifest['python_process_audit'] = python_process_audit()
                if not manifest['python_process_audit']['passed']:raise RuntimeError('Python audit failed')
                audit_done = True
            if args.exercise and elapsed > 45.:raise RuntimeError('GUI acceptance safety timeout')
            if args.duration_s and elapsed >= args.duration_s:
                gui.send_signal(signal.SIGINT)
                break
            time.sleep(.1)
        if gui.poll() not in (None, 0):raise RuntimeError('RViz process failed: ' + str(gui.returncode))
        if args.exercise:
            result = json.loads((run / 'figures/ui-validation.json').read_text())
            manifest['ui_validation'] = result
            if not result['passed']:raise RuntimeError('GUI acceptance failed: ' + str(result))
            pixels = processes.spawn('figure-check', [sys.executable, '-B',
                str(root / 'tests/check_rviz_figures.py'), str(run / 'figures')])
            if pixels.wait(timeout=15.):raise RuntimeError('RViz figure pixel validation failed')
        passed = True
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        cleanup = processes.cleanup()
        if args.mode != 'live':
            cleanup['ports'] = probe_ports('REPORT', args.port)
            cleanup['passed'] = cleanup['passed'] and all(item['free'] for item in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        manifest['passed'] = passed and cleanup['passed'] and not manifest['errors']
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=manifest['passed'], errors=manifest['errors'])), flush=True)
    return int(not manifest['passed'])


if __name__ == '__main__':
    sys.exit(main())
