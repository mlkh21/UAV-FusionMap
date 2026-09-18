"""SIM-00B单次静止遥测装配；仅管理本次子进程，不调用旧启动器。"""
import datetime
import json
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import time
import xmlrpc.client


def main():
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.runtime'
    run = runtime / 'runs' / ('sim00b-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S'))
    run.mkdir(parents=True, exist_ok=False)
    (run / 'rootfs').mkdir()
    (run / 'ros-home').mkdir()
    (run / 'ros-logs').mkdir()
    shutil.copy2(root / 'ros_ws/launch/sim00b_mavros.launch', run / 'mavros.launch')
    env = dict(os.environ, ROS_MASTER_URI='http://127.0.0.1:11321', ROS_IP='127.0.0.1',
               ROS_HOME=str(run / 'ros-home'), ROS_LOG_DIR=str(run / 'ros-logs'),
               HEADLESS='1', PX4_SIM_MODEL='rascal', PX4_SIM_SPEED_FACTOR='1', MAVLINK20='1')
    children, handles = [], []
    manifest = {'run': str(run), 'commands': [], 'errors': [], 'armed_commands': False, 'supervisor_pid': os.getpid(),
                'px4_commit': '1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa',
                'bridge_commit': '68de2cc63ded9a0d6641d45e9eb3ed2b43454cba',
                'patch': 'SIM00B-INIT-01', 'ros_master_uri': env['ROS_MASTER_URI']}
    started = time.monotonic()

    def spawn(name, args, cwd=None):
        handle = (run / (name + '.log')).open('x')
        handles.append(handle)
        process = subprocess.Popen(args, cwd=cwd or run, env=env, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        children.append((name, process))
        manifest['commands'].append({'name': name, 'args': args, 'pid': process.pid})
        return process

    def interrupt(signum, frame):
        raise RuntimeError('supervisor interrupted: ' + str(signum))

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    result = 1
    try:
        # 检查所有本次已知绑定端口；检查后仍可能发生竞争，子进程失败即停止。
        for kind, ports in [(socket.SOCK_STREAM, (11321, 4560)),
                            (socket.SOCK_DGRAM, (14540, 14580, 18570, 14280, 13030))]:
            for port in ports:
                with socket.socket(socket.AF_INET, kind) as probe:
                    if kind == socket.SOCK_STREAM:
                        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        probe.bind(('0.0.0.0', port))
                    except OSError as exc:
                        raise RuntimeError('port ' + str(port) + ': ' + str(exc)) from exc
        # PX4 instance 0不能与既有PX4共用；不停止现有进程。
        for comm in Path('/proc').glob('[0-9]*/comm'):
            try:
                if comm.read_text().strip() == 'px4':
                    raise RuntimeError('existing PX4 process; stop without modifying it')
            except FileNotFoundError:
                pass
        spawn('roscore', ['/opt/ros/noetic/bin/roscore', '-p', '11321'])
        master = xmlrpc.client.ServerProxy(env['ROS_MASTER_URI'])
        for _ in range(100):
            try:
                if master.getPid('/sim00b_supervisor')[0] == 1:
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError('ROS master startup timeout')
        spawn('observer', ['/usr/bin/python3', str(root / 'simulation/check_sim00b_telemetry.py'), str(run)])
        spawn('bridge', [str(runtime / 'build/jsbsim-bridge-init01/jsbsim_bridge'), 'rascal', '-s',
                         str(runtime / 'src/px4-v1.13.3/Tools/jsbsim_bridge/scene/LSZH.xml')])
        time.sleep(1)
        spawn('px4', [str(runtime / 'build/px4-v1.13.3/bin/px4'), '-d',
                      str(runtime / 'build/px4-v1.13.3/etc'), '-s', 'etc/init.d-posix/rcS'], run / 'rootfs')
        spawn('mavros', ['/opt/ros/noetic/bin/roslaunch', str(run / 'mavros.launch')])
        configured = False
        while time.monotonic() - started < 890:
            observer = next(p for n, p in children if n == 'observer')
            if observer.poll() is not None:
                result = observer.returncode
                break
            for name, process in children:
                if name != 'observer' and process.poll() is not None:
                    raise RuntimeError(name + ' exited: ' + str(process.returncode))
            px4_log = (run / 'px4.log').read_text(errors='replace')
            if not configured and 'Startup script returned successfully' in px4_log:
                for name, rate in [('HIGHRES_IMU', '50'), ('ODOMETRY', '20')]:
                    cmd = [str(runtime / 'build/px4-v1.13.3/bin/px4-mavlink'), 'stream', '-u', '14580', '-s', name, '-r', rate]
                    with (run / ('stream-' + name + '.log')).open('x') as f:
                        code = subprocess.run(cmd, env=env, cwd=run / 'rootfs', stdout=f, stderr=subprocess.STDOUT, timeout=5).returncode
                    manifest['commands'].append({'name': 'stream-' + name, 'args': cmd, 'exit': code})
                    if code:
                        raise RuntimeError('stream configuration failed')
                configured = True
            time.sleep(0.2)
        else:
            raise RuntimeError('wall time safety limit')
    except Exception as exc:
        manifest['errors'].append(str(exc))
    finally:
        # 先关闭观察器，再按逆序关闭本次进程组；保留所有输出。
        ordered = [item for item in children if item[0] == 'observer'] + [item for item in reversed(children) if item[0] != 'observer']
        for name, process in ordered:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
        for name, process in ordered:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            manifest.setdefault('exits', {})[name] = process.returncode
        for handle in handles:
            handle.close()
        manifest['wall_seconds'] = time.monotonic() - started
        manifest['exit'] = result
        (run / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'run': str(run), 'exit': result, 'errors': manifest['errors']}), flush=True)
    return result


if __name__ == '__main__':
    sys.exit(main())
