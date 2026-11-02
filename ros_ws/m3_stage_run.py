"""Bounded independent M3 synthetic ROS and public occupancy replay acceptance."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys
import time

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, python_process_audit, start_master, write_json)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=11651)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be in [1024, 65535]')
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    identity = 'm3-stage-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True, exist_ok=False)
    for name in ('ros-home', 'ros-logs'):
        (run / name).mkdir()
    env = configure_environment(run, args.port)
    manifest = dict(run_id=identity, python=sys.executable, commands=[], errors=[],
                    map_backend='m3_fixture', rolling=True, ros_master_uri=env['ROS_MASTER_URI'],
                    scope='synthetic ROS software acceptance, not calibrated quality or PERF-01')
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    try:
        manifest['ports_before'] = probe_ports('M3', args.port)
        if any(not row['free'] for row in manifest['ports_before']):
            raise RuntimeError('port unavailable; existing processes preserved')
        shutil.copy2(root / 'configs/m3_fixture.yaml', run / 'm3-config.yaml')
        shutil.copy2(root / 'ros_ws/launch/m3_fixture.launch', run / 'm3_fixture.launch')
        start_master(processes, args.port, time.monotonic() + 15.)
        processes.spawn('mapping', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
            str(run / 'm3_fixture.launch'), 'run_id:=' + identity, 'clock_id:=sim:' + identity,
            'm3_fixture_config:=' + str(run / 'm3-config.yaml')])
        observer = processes.spawn('observer', [sys.executable, '-B',
            str(root / 'tests/check_m3_stage_ros.py'), str(run), identity])
        deadline = time.monotonic() + 45.
        while observer.poll() is None:
            processes.check(allowed=('observer',))
            if time.monotonic() > deadline:
                raise RuntimeError('M3 ROS acceptance wall-clock safety limit')
            time.sleep(.02)
        validation = json.loads((run / 'validation.json').read_text())
        if observer.returncode or not validation['passed']:
            raise RuntimeError('M3 ROS checker failed: ' + str(validation['errors']))
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise RuntimeError('Python process audit failed')
        replay = processes.spawn('replay', [sys.executable, '-B', str(root / 'ros_ws/local_map_replay.py'),
            '--input', str(run / 'receipts.json'), '--run-id', identity, '--clock-id', 'sim:' + identity,
            '--map-backend', 'm3_fixture', '--m3-fixture-config', str(run / 'm3-config.yaml'), '--rolling'])
        deadline = time.monotonic() + 15.
        while replay.poll() is None:
            processes.check(allowed=('observer', 'replay'))
            if time.monotonic() > deadline:
                raise RuntimeError('M3 replay safety limit')
            time.sleep(.02)
        if replay.returncode:
            raise RuntimeError('M3 public occupancy replay failed')
        replay_receipt = json.loads((run / 'replay.log').read_text().strip())
        manifest['replay'] = replay_receipt
        passed = replay_receipt['passed']
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ':' + str(exc))
    finally:
        cleanup = processes.cleanup()
        try:
            cleanup['ports'] = probe_ports('M3', args.port)
            cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        except OSError as exc:
            cleanup.update(passed=False, ports=[])
            manifest['errors'].append('cleanup port probe: ' + str(exc))
        write_json(run / 'cleanup-audit.json', cleanup)
        passed = passed and cleanup['passed'] and not manifest['errors']
        manifest['passed'] = passed
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=passed, cleanup=cleanup['passed'], errors=manifest['errors'])))
    return int(not passed)


if __name__ == '__main__':
    sys.exit(main())
