"""Bounded Local Map query ROS fixture supervisor; use sim01_env.sh."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import time

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, python_process_audit, start_master, write_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=11451)
    parser.add_argument('--mode', choices=('enabled', 'disabled', 'unclassified', 'rolling'), default='enabled')
    parser.add_argument('--sample-resources', action='store_true',
                        help='optional fixture-only mapping RSS samples; not M1 acceptance')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be in [1024, 65535]')
    root = Path(__file__).resolve().parents[1]
    identity = 'local-map-query-' + args.mode + '-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True, exist_ok=False)
    for name in ('ros-home', 'ros-logs'):
        (run / name).mkdir()
    env = configure_environment(run, args.port)
    manifest = dict(run_id=identity, mode=args.mode, python=sys.executable,
                    supervisor_pid=os.getpid(), commands=[], errors=[], armed_commands=False,
                    ros_master_uri=env['ROS_MASTER_URI'])
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    sampler = None
    started = time.monotonic()
    try:
        manifest['ports_before'] = probe_ports('QUERY', args.port)
        if any(not row['free'] for row in manifest['ports_before']):
            raise RuntimeError('port occupied; existing process preserved')
        if args.sample_resources:
            from perf01a_resources import ResourceSampler
            sampler = ResourceSampler(interval_s=.1)
            sampler.start()
        launch = root / ('ros_ws/launch/local_map_rolling_fixture.launch' if args.mode == 'rolling'
                         else 'ros_ws/launch/local_map_query_fixture.launch')
        shutil.copy2(launch, run / launch.name)
        start_master(processes, args.port, time.monotonic() + 15)
        processes.spawn('mapping', [sys.executable, '/opt/ros/noetic/bin/roslaunch', str(run / launch.name),
                                   'run_id:=' + identity,
                                   'enable_query:=' + str(args.mode != 'disabled').lower(),
                                   'classify:=' + str(args.mode != 'unclassified').lower()])
        checker = ('check_local_map_rolling_ros.py' if args.mode == 'rolling'
                   else 'check_local_map_query_ros.py')
        observer = processes.spawn('observer', [sys.executable, str(root / 'tests' / checker),
                                               str(run), identity, '--mode', args.mode])
        deadline = started + 45
        while time.monotonic() < deadline:
            processes.check(allowed=('observer',))
            if 'python_process_audit' not in manifest and time.monotonic() - started >= 2:
                manifest['python_process_audit'] = python_process_audit()
                if not manifest['python_process_audit']['passed']:
                    raise RuntimeError('Python environment audit failed')
            if observer.poll() is not None:
                if observer.returncode:
                    raise RuntimeError('query observer failed: ' + str(observer.returncode))
                if 'python_process_audit' not in manifest:
                    manifest['python_process_audit'] = python_process_audit()
                    if not manifest['python_process_audit']['passed']:
                        raise RuntimeError('Python environment audit failed')
                with (run / 'validation.json').open() as handle:
                    passed = json.load(handle)['passed']
                break
            time.sleep(.02)
        else:
            raise RuntimeError('query fixture wall-clock safety limit')
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        if sampler is not None:
            try:
                from m1_resource_observer import mapping_resource_report
                sampler.stop()
                write_json(run / 'resources.json', mapping_resource_report(sampler.rows, sampler.errors))
            except Exception as exc:
                manifest['errors'].append('fixture resource sampling: %s: %s'
                                          % (type(exc).__name__, exc))
        cleanup = processes.cleanup()
        cleanup['ports'] = probe_ports('QUERY', args.port)
        cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        passed = passed and cleanup['passed'] and not manifest['errors']
        manifest.update(passed=passed, wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=passed, cleanup=cleanup['passed'],
                              errors=manifest['errors'])), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
