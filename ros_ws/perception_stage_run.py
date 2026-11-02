"""Isolated P3 software fault/recovery ROS fixture; no research backend or hardware."""
import argparse
import datetime
import json
import os
from pathlib import Path
import sys
import time

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, python_process_audit, start_master, write_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=11623)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be in [1024,65535]')
    root = Path(__file__).resolve().parents[1]
    run_id = 'p3-software-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    for name in ('ros-home', 'ros-logs'):
        (run / name).mkdir()
    env = configure_environment(run, args.port)
    manifest = dict(run_id=run_id, python=sys.executable, commands=[], errors=[],
                    supervisor_pid=os.getpid(), scope='CPU software fixture; no research forward')
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    started = time.monotonic()
    try:
        if any(not row['free'] for row in probe_ports('P3', args.port)):
            raise RuntimeError('port occupied; existing process preserved')
        start_master(processes, args.port, time.monotonic() + 15.)
        import rospy
        rospy.init_node('p3_stage_runner', disable_signals=True)
        for key, value in {'/use_sim_time': True, '/perf01a_require_observers': False,
                '/perf01a_perception/worker_enabled': True,
                '/perf01a_perception/worker_deadline_s': .8}.items():
            rospy.set_param(key, value)
        manifest['worker'] = dict(enabled=True, deadline_s=.8, active_capacity=1, waiting_capacity=0)
        processes.spawn('mapping', [sys.executable,
            str(root / 'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'),
            '__name:=perf01a_mapping', '_run_id:=' + run_id, '_enable_query:=true',
            '_free_threshold:=0.3', '_occupied_threshold:=0.7'])
        processes.spawn('perception', [sys.executable, str(root / 'tests/p3_backend_fixture_node.py'),
            '__name:=perf01a_perception', '_run_id:=' + run_id])
        observer = processes.spawn('observer', [sys.executable,
            str(root / 'tests/check_perception_stage_ros.py'), str(run), run_id])
        while time.monotonic() - started < 45.:
            processes.check(allowed=('observer',))
            if observer.poll() is not None:
                if observer.returncode:
                    raise RuntimeError('P3 fixture observer failed')
                passed = json.loads((run / 'validation.json').read_text())['passed']
                break
            time.sleep(.02)
        else:
            raise RuntimeError('P3 fixture wall-clock safety limit')
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise RuntimeError('Python environment audit failed')
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ':' + str(exc))
    finally:
        cleanup = processes.cleanup()
        try:
            cleanup['ports'] = probe_ports('P3', args.port)
            cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        except OSError as exc:
            manifest['errors'].append('port audit unavailable: ' + str(exc))
            cleanup['passed'] = False
        write_json(run / 'cleanup-audit.json', cleanup)
        passed = passed and cleanup['passed'] and not manifest['errors']
        manifest.update(passed=passed, wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=passed, errors=manifest['errors'])), flush=True)
    return int(not passed)


if __name__ == '__main__':
    sys.exit(main())
