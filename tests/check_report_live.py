"""Native RViz attaches read-only to the existing Radar/IR placeholder ROS chain."""
import datetime
import json
from pathlib import Path
import sys
import time

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, start_master, write_json)


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    identity = 'report-live-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True)
    for name in ('ros-home', 'ros-logs'):(run / name).mkdir()
    env = configure_environment(run, 11703)
    manifest = dict(run_id=identity, commands=[], errors=[])
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    try:
        if not all(row['free'] for row in probe_ports('REPORT', 11703)):
            raise RuntimeError('live acceptance port busy; existing processes preserved')
        master = start_master(processes, 11703, time.monotonic() + 15.)
        processes.spawn('legacy-chain', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
            str(root / 'ros_ws/launch/inference_fixture.launch'), 'run_id:=' + identity, 'duration_s:=15'])
        ui = processes.spawn('live-ui', [sys.executable, '-B', str(root / 'ros_ws/report_rviz_run.py'),
            '--mode', 'live', '--master-uri', env['ROS_MASTER_URI'], '--clock-id', 'sim:' + identity,
            '--ttl-ns', '100000000', '--duration-s', '7'])
        deadline = time.monotonic() + 35.
        while ui.poll() is None:
            processes.check(allowed=('live-ui',))
            if time.monotonic() > deadline:raise RuntimeError('live GUI safety timeout')
            time.sleep(.1)
        if ui.returncode:raise RuntimeError('live GUI launcher failed')
        lines = [json.loads(line) for line in (run / 'live-ui.log').read_text().splitlines() if line.startswith('{')]
        gui_run = Path(lines[-1]['run'])
        gui_manifest = json.loads((gui_run / 'manifest.json').read_text())
        session = json.loads((gui_run / 'figures/ui-session.json').read_text())
        if not gui_manifest['passed'] or session['sampled_frames'] == 0 or not session['frame']['available']:
            raise RuntimeError('live public snapshots unavailable: ' + str(session))
        frame = session['frame']
        if frame['header']['run_id'] != identity or frame['header']['frame_id'] != 'odom':
            raise RuntimeError('live identity/frame rewritten')
        if frame['sources'] != ['fixture'] or frame['counts']['free'] or frame['counts']['occupied']:
            raise RuntimeError('unconfigured legacy classification must remain unknown')
        if any(command['name'] != 'rviz-ui' for command in gui_manifest['commands']):
            raise RuntimeError('live mode started a fixture or another master')
        manifest.update(gui_run=str(gui_run), session=session, graph=master.getSystemState('/live_checker')[2],
            checks=['legacy source/sensor/placeholder/map chain', 'actual public snapshot received',
                    'frame/run preserved', 'unconfigured thresholds remain unknown',
                    'live starts no master or fixture', 'GUI normal close and child cleanup'])
        passed = True
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        cleanup = processes.cleanup()
        cleanup['ports'] = probe_ports('REPORT', 11703)
        cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        manifest['passed'] = passed and cleanup['passed'] and not manifest['errors']
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=manifest['passed'], errors=manifest['errors'])))
    return int(not manifest['passed'])


if __name__ == '__main__':
    sys.exit(main())
