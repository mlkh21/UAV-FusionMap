"""SIM-01B独立LIVE会话：300源秒、发布台账及有界ROS bag记录。"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from sim01b_runtime import (BUSINESS_TOPICS, Processes, Recorder, audit_matches,
    check_clock_publishers, configure_environment, create_session, install_interrupt_handler,
    load_settings, master_port, probe_ports, python_process_audit, read_json, read_lines,
    reject_existing_px4, setting, source_sensor_complete, start_master, state_config,
    wait_ready, write_json)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', help='B记录配置；不改变已冻结门槛')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    config_path, values = load_settings(root, args.config)
    run, run_id = create_session(root, 'LIVE')
    port = master_port(values, 'LIVE')
    env = configure_environment(run, port)
    manifest = dict(mode='LIVE', run_id=run_id, run=str(run), python=sys.executable,
                    supervisor_pid=os.getpid(), ros_master_uri=env['ROS_MASTER_URI'], commands=[],
                    errors=[], armed_commands=False, phase='PREPARING',
                    px4_commit='1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa',
                    bridge_commit='68de2cc63ded9a0d6641d45e9eb3ed2b43454cba', patch='SIM00B-INIT-01')
    processes = Processes(run, env, manifest)
    recorder = None
    started = time.monotonic()
    wall_deadline = started + setting(values, 'wall_limit_s', 900.)
    startup_deadline = started + setting(values, 'startup_timeout_s', 60.)
    drain_s = setting(values, 'drain_timeout_s', 5.)
    source_audit, sensor_audit = run / 'source-audit.jsonl', run / 'sensor-audit.jsonl'
    install_interrupt_handler()
    passed = False
    try:
        manifest['ports_before'] = probe_ports('LIVE', port)
        if any(not p['free'] for p in manifest['ports_before']):
            raise RuntimeError('必要端口被占用，保留既有进程')
        reject_existing_px4()
        for path in (config_path, state_config(root, values), root / 'ros_ws/launch/sim01b_source.launch',
                     root / 'ros_ws/launch/sim01b_sensors.launch', root / 'ros_ws/launch/sim00b_mavros.launch'):
            shutil.copy2(path, run / path.name)
        master = start_master(processes, port, startup_deadline)
        import rospy
        rospy.init_node('sim01b_live_recorder', disable_signals=True)
        recorder = Recorder(run, 'live.bag', setting(values, 'writer_queue_limit', 10000),
                            source_limit_ns=setting(values, 'source_limit_ns', 600000000000))
        for name, launch, audit in (('source', 'sim01b_source.launch', source_audit),
                                   ('sensors', 'sim01b_sensors.launch', sensor_audit)):
            processes.spawn(name, [sys.executable, '/opt/ros/noetic/bin/roslaunch', str(run / launch),
                'run_id:=' + run_id, 'config:=' + str(run / state_config(root, values).name),
                'audit_path:=' + str(audit)])
        wait_ready(master, recorder, processes, BUSINESS_TOPICS, startup_deadline, require_sensor=True)
        for path in (source_audit, sensor_audit):
            while not Path(str(path) + '.ready.json').exists():
                processes.check()
                recorder.raise_errors()
                if time.monotonic() >= startup_deadline:
                    raise RuntimeError('发布台账就绪超时：' + str(path))
                time.sleep(.02)
        runtime = root / '.runtime'
        processes.spawn('bridge', [str(runtime / 'build/jsbsim-bridge-init01/jsbsim_bridge'), 'rascal', '-s',
                                  str(runtime / 'src/px4-v1.13.3/Tools/jsbsim_bridge/scene/LSZH.xml')])
        # 以监听端口为动力学连接就绪条件，不使用固定等待时长。
        while True:
            processes.check()
            if not probe_ports('LIVE', port)[1]['free']:
                break
            if time.monotonic() >= startup_deadline:
                raise RuntimeError('bridge TCP监听启动超时')
            time.sleep(.05)
        processes.spawn('px4', [str(runtime / 'build/px4-v1.13.3/bin/px4'), '-d',
            str(runtime / 'build/px4-v1.13.3/etc'), '-s', 'etc/init.d-posix/rcS'], run / 'rootfs')
        processes.spawn('mavros', [sys.executable, '/opt/ros/noetic/bin/roslaunch', str(run / 'sim00b_mavros.launch')])
        configured, window = False, None
        span_ns = setting(values, 'min_valid_span_ns', 300000000000)
        while time.monotonic() < wall_deadline:
            processes.check()
            recorder.raise_errors()
            check_clock_publishers(master, required=True)
            if not configured and 'Startup script returned successfully' in (run / 'px4.log').read_text(errors='replace'):
                for stream, rate in (('HIGHRES_IMU', '50'), ('ODOMETRY', '20')):
                    command = [str(runtime / 'build/px4-v1.13.3/bin/px4-mavlink'), 'stream', '-u', '14580',
                               '-s', stream, '-r', rate]
                    with (run / ('stream-' + stream + '.log')).open('x') as handle:
                        code = subprocess.run(command, cwd=run / 'rootfs', env=env,
                            stdout=handle, stderr=subprocess.STDOUT, timeout=5.).returncode
                    manifest['commands'].append(dict(name='stream-' + stream, args=command, exit=code))
                    if code:
                        raise RuntimeError('遥测流配置失败：' + stream)
                configured = True
                manifest['python_process_audit'] = python_process_audit()
                if not manifest['python_process_audit']['passed']:
                    raise RuntimeError('本次Python进程未全部使用指定Conda')
            snapshot = recorder.snapshot()
            if snapshot['source']:
                if window is None:
                    first = snapshot['source'][0]['header']
                    window = dict(t0_ns=first['timestamp'], first_sample_id=first['sample_id'])
                    manifest['phase'] = 'ACTIVE'
                for state in snapshot['source']:
                    header = state['header']
                    if header['timestamp'] - window['t0_ns'] >= span_ns:
                        window.update(t1_ns=header['timestamp'], last_sample_id=header['sample_id'])
                        break
                if 't1_ns' in window and snapshot['clocks'] and snapshot['clocks'][-1] >= window['t1_ns']:
                    write_json(run / 'window.json', window)
                    break
            elif time.monotonic() >= startup_deadline:
                raise RuntimeError('首条有效状态启动超时')
            time.sleep(.05)
        else:
            raise RuntimeError('LIVE 900墙秒安全截止')
        manifest['phase'] = 'DRAINING'
        processes.stop('source', timeout=drain_s)
        deadline = min(wall_deadline, time.monotonic() + drain_s)
        while time.monotonic() < deadline:
            processes.check()
            recorder.raise_errors()
            if audit_matches(source_audit, recorder) and source_sensor_complete(recorder):
                marker = read_json(Path(str(source_audit) + '.closed.json'))
                if marker.get('phase') != 'ACTIVE':
                    raise RuntimeError('源正常关闭时未处于ACTIVE')
                # 接收侧首帧必须与发布端首valid一致，不能事后选择成功子窗口。
                published = [r for r in read_lines(source_audit) if r['topic'] == '/uav/sim/state']
                if not published or published[0]['sample_id'] != window['first_sample_id']:
                    raise RuntimeError('源发布与接收首条有效身份不一致')
                break
            time.sleep(.02)
        else:
            raise RuntimeError('源封存后现场状态/clock排空不完整')
        processes.stop('sensors', timeout=drain_s)
        deadline = min(wall_deadline, time.monotonic() + drain_s)
        while not audit_matches(sensor_audit, recorder):
            processes.check()
            recorder.raise_errors()
            if time.monotonic() >= deadline:
                raise RuntimeError('sensor发布台账排空不完整')
            time.sleep(.02)
        for name in ('mavros', 'px4', 'bridge'):
            processes.stop(name, timeout=drain_s)
        closed = recorder.close(drain_s)
        recorder = None
        if not closed['passed']:
            raise RuntimeError('writer关闭或bag重读未通过：' + ';'.join(closed['errors']))
        sys.path.insert(0, str(root / 'tests'))
        from check_sim01b_recording import validate_live
        write_json(run / 'manifest.json', manifest)
        validation = validate_live(run)
        write_json(run / 'validation.json', validation)
        if not validation['passed']:
            raise RuntimeError('LIVE数据验收失败：' + ';'.join(validation['errors']))
        passed = True
        manifest['phase'] = 'COMPLETE'
    except Exception as exc:
        manifest['errors'].append(str(exc))
        manifest['phase'] = 'FAILED'
    finally:
        cleanup = processes.cleanup()
        if recorder is not None:
            try:
                recorder.close(drain_s)
            except Exception as exc:
                manifest['errors'].append('writer cleanup: ' + str(exc))
        cleanup['ports'] = probe_ports('LIVE', port)
        cleanup['passed'] = cleanup['passed'] and all(p['free'] for p in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        if not cleanup['passed']:
            manifest['errors'].append('本次进程/端口清理未通过')
        passed = passed and not manifest['errors'] and cleanup['passed']
        manifest.update(exit=0 if passed else 1, wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
        print(__import__('json').dumps(dict(run=str(run), exit=manifest['exit'],
              errors=manifest['errors'], cleanup=cleanup['passed'])), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
