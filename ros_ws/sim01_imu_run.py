"""短时隔离ROS IMU fixture：不启动PX4/JSBSim，退出时只清理本次子进程。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--enabled', action='store_true')
    parser.add_argument('--port', type=int, default=12581)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    run_id = 'sim01-imu-%s-%s' % ('enabled' if args.enabled else 'off',
                                datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, MAVLINK20='1', ROS_MASTER_URI='http://127.0.0.1:%d' % args.port,
               ROS_IP='127.0.0.1', ROS_HOME=str(run / 'ros-home'), ROS_LOG_DIR=str(run / 'ros-logs'))
    (run / 'ros-home').mkdir()
    (run / 'ros-logs').mkdir()
    children = []
    handles = []
    errors = []

    def spawn(name, command):
        handle = (run / (name + '.log')).open('x')
        handles.append(handle)
        process = subprocess.Popen(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        children.append((name, process))
        return process

    def free_port():
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', args.port))
                return True
            except OSError:
                return False

    try:
        if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
            raise RuntimeError('wrong_python')
        if not free_port():
            raise RuntimeError('ros_port_occupied')
        spawn('roscore', [sys.executable, '/opt/ros/noetic/bin/roscore', '-p', str(args.port)])
        master = xmlrpc.client.ServerProxy(env['ROS_MASTER_URI'])
        for _ in range(100):
            try:
                if master.getPid('/sim01_imu_supervisor')[0] == 1:
                    break
            except OSError:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError('roscore_startup_timeout')
        launch = root / 'ros_ws/launch/sim01_state.launch'
        command = [sys.executable, '/opt/ros/noetic/bin/roslaunch', str(launch),
                   'run_id:=' + run_id, 'input_topic:=/uav/imu_fixture/mavlink']
        if args.enabled:
            command += ['publish_imu:=true', 'imu_calibration_id:=sim_pilot_virtual_flu_v1']
        nodes = spawn('state_nodes', command)
        observer_cmd = [sys.executable, str(root / 'tests/check_sim01_imu_ros.py'), str(run), run_id]
        if args.enabled:
            observer_cmd.append('--enabled')
        observer = spawn('observer', observer_cmd)
        until = time.monotonic() + 40
        while time.monotonic() < until:
            if observer.poll() is not None:
                if observer.returncode:
                    raise RuntimeError('observer_failed')
                break
            if nodes.poll() is not None:
                raise RuntimeError('state_nodes_exited')
            time.sleep(.05)
        else:
            raise RuntimeError('observer_timeout')
        result = json.loads((run / 'imu-result.json').read_text())
        if not result['passed']:
            raise RuntimeError('imu_result_failed')
    except Exception as exc:
        errors.append(str(exc))
    finally:
        for _, child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
        for _, child in reversed(children):
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=5)
        for handle in handles:
            handle.close()
        cleanup = free_port() and all(child.poll() is not None for _, child in children)
        report = dict(passed=not errors and cleanup, errors=errors, cleanup=cleanup,
                      run=str(run), python=sys.executable,
                      exits={name: p.returncode for name, p in children})
        (run / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
