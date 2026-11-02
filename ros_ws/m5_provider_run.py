"""Isolated actual terrain provider/clock/recovery and occupancy compatibility acceptance."""
import argparse
import copy
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

import yaml
from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, python_process_audit, start_master, write_json)
from ufm_mapping.terrain_dataset import from_private_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=11681)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be in [1024,65535]')
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    identity = 'm5-provider-' + datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True, exist_ok=False)
    for name in ('ros-home', 'ros-logs'): (run / name).mkdir()
    env = configure_environment(run, args.port)
    manifest = dict(run_id=identity, python=sys.executable, commands=[], errors=[],
        ros_master_uri=env['ROS_MASTER_URI'], scope='synthetic provider ROS acceptance, no DEM or occupancy fusion')
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    def start_terrain(name, run_id, config):
        return processes.spawn(name, [sys.executable, '/opt/ros/noetic/bin/roslaunch',
            str(root / 'ros_ws/launch/terrain_fixture.launch'), 'enabled:=true', 'dataset:=' + str(config),
            'run_id:=' + run_id, 'clock_id:=sim:' + run_id, 'clock_publisher:=/m5_terrain_checker'])
    try:
        manifest['ports_before'] = probe_ports('TERRAIN', args.port)
        if any(not p['free'] for p in manifest['ports_before']):
            raise RuntimeError('port occupied; existing processes preserved')
        default = subprocess.run([sys.executable, '/opt/ros/noetic/bin/roslaunch', '--nodes',
            str(root / 'ros_ws/launch/terrain_fixture.launch')], capture_output=True, text=True, env=env, timeout=8.)
        manifest['default_off'] = dict(returncode=default.returncode, stdout=default.stdout, stderr=default.stderr)
        if default.returncode or '/terrain_provider' in default.stdout:
            raise RuntimeError('terrain launch not default off')
        private = yaml.safe_load((root / 'configs/m5_terrain_fixture.yaml').read_text())
        for suffix in ('', '-recovery'):
            spec = copy.deepcopy(private)
            run_id = identity + suffix
            for key in ('registration', 'eligibility'): spec[key].update(run_id=run_id, clock_id='sim:' + run_id)
            write_json(run / ('dataset' + suffix + '.json'), from_private_fixture(spec))
        write_json(run / 'independent-expectations.json', json.loads((root / 'tests/fixtures/m5_provider_expectations.json').read_text()))
        start_master(processes, args.port, time.monotonic() + 15.)
        start_terrain('terrain', identity, run / 'dataset.json')
        processes.spawn('old-mapping', [sys.executable, '-B',
            str(root / 'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'),
            '__name:=perf01a_mapping', '_run_id:=' + identity, '_enable_query:=true',
            '_free_threshold:=0.3', '_occupied_threshold:=0.7'])
        observer = processes.spawn('observer', [sys.executable, '-B', str(root / 'tests/check_m5_provider_ros.py'), str(run), identity])
        restarted, stopped = False, False
        deadline = time.monotonic() + 65.
        while observer.poll() is None:
            processes.check(allowed=('observer',))
            if time.monotonic() >= deadline:
                raise RuntimeError('M5 provider ROS acceptance wall deadline')
            if not restarted and (run / 'restart-request.json').exists():
                processes.stop('terrain')
                start_terrain('terrain-recovery', identity + '-recovery', run / 'dataset-recovery.json')
                restarted = True
            if not stopped and (run / 'stop-request.json').exists():
                processes.stop('terrain-recovery')
                stopped = True
            time.sleep(.02)
        manifest['python_process_audit'] = python_process_audit()
        validation = json.loads((run / 'validation.json').read_text())
        if observer.returncode or not validation['passed'] or not manifest['python_process_audit']['passed']:
            raise RuntimeError('M5 checker: ' + str(validation['errors']))
        passed = restarted and stopped
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ':' + str(exc))
    finally:
        cleanup = processes.cleanup()
        try:
            cleanup['ports'] = probe_ports('TERRAIN', args.port)
            cleanup['passed'] = cleanup['passed'] and all(p['free'] for p in cleanup['ports'])
        except OSError as exc:
            cleanup.update(passed=False, ports=[])
            manifest['errors'].append('cleanup: ' + str(exc))
        write_json(run / 'cleanup-audit.json', cleanup)
        passed = passed and cleanup['passed'] and not manifest['errors']
        manifest['passed'] = passed
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=passed, cleanup=cleanup['passed'], errors=manifest['errors'])), flush=True)
    return int(not passed)


if __name__ == '__main__':
    sys.exit(main())
