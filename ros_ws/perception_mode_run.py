"""Short online disabled/research mode failure-chain supervisor; use sim01_env.sh."""
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
    parser.add_argument('--mode', choices=('disabled', 'research'), required=True)
    parser.add_argument('--port', type=int, default=11487)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    identity = 'perception-mode-' + args.mode + '-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
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
    started = time.monotonic()
    try:
        manifest['ports_before'] = probe_ports('PERCEPTION', args.port)
        if any(not row['free'] for row in manifest['ports_before']):
            raise RuntimeError('port occupied; existing process preserved')
        launch = root / 'ros_ws/launch/perf01a_placeholder.launch'
        shutil.copy2(launch, run / launch.name)
        start_master(processes, args.port, time.monotonic() + 15)
        processes.spawn('nodes', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
                        str(run / launch.name), 'run_id:=' + identity, 'mode:=' + args.mode,
                        'enable_query:=true', 'duration_s:=1', 'frequency_hz:=20'])
        observer = processes.spawn('observer', [sys.executable,
            str(root / 'tests/check_perception_mode_ros.py'), str(run), identity, args.mode])
        deadline = started + 45
        while time.monotonic() < deadline:
            processes.check(allowed=('observer',))
            if observer.poll() is not None:
                if observer.returncode:
                    raise RuntimeError('mode observer failed: ' + str(observer.returncode))
                with (run / 'validation.json').open() as handle:
                    passed = json.load(handle)['passed']
                break
            time.sleep(.02)
        else:
            raise RuntimeError('mode fixture wall-clock safety limit')
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise RuntimeError('Python environment audit failed')
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        cleanup = processes.cleanup()
        cleanup['ports'] = probe_ports('PERCEPTION', args.port)
        cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        passed = passed and cleanup['passed'] and not manifest['errors']
        manifest.update(passed=passed, wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=passed,
                              cleanup=cleanup['passed'], errors=manifest['errors'])), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
