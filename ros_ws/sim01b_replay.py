"""SIM-01B独立B1成品消息回放或B2新sensors复算；保留原始采样时钟。"""
import argparse
import collections
import os
from pathlib import Path
import shutil
import sys
import time

from sim01b_runtime import (BUSINESS_TOPICS, Processes, Recorder, audit_matches,
    check_clock_publishers, configure_environment, create_session, expected_sequences,
    install_interrupt_handler, load_settings, master_port, probe_ports, publishers,
    python_process_audit, read_json, setting, source_sensor_complete, start_master,
    state_config, write_json, rpc_proxy)


def playback_ready(master, recorder, mode, sensor_audit):
    """核对播放器真实TCP连接，不把Master登记或延迟当成就绪。"""
    import xmlrpc.client
    published, subscribed = publishers(master)
    clock_nodes = check_clock_publishers(master)
    if not clock_nodes:
        return False
    player = clock_nodes[0]
    topics = BUSINESS_TOPICS if mode == 'B1' else BUSINESS_TOPICS[:2]
    recorder_name = __import__('rospy').get_name()
    try:
        uri = master.lookupNode('/sim01b_supervisor', player)
        stats = rpc_proxy(uri[2]).getBusInfo('/sim01b_supervisor')
        outgoing = {(item[1], item[4]) for item in stats[2] if item[2] == 'o' and item[5]}
        if any((recorder_name, topic) not in outgoing for topic in topics):
            return False
        if mode == 'B2':
            if any(('/state_adapter', topic) not in outgoing for topic in BUSINESS_TOPICS[:2]):
                return False
            if not Path(str(sensor_audit) + '.ready.json').exists():
                return False
            if recorder.subscribers['/uav/sensors/state'].get_num_connections() < 1:
                return False
    except (OSError, xmlrpc.client.Error, IndexError):
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('live', help='已通过的LIVE运行目录')
    parser.add_argument('mode', choices=('B1', 'B2'))
    parser.add_argument('--config', help='B会话配置')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    live = Path(args.live).resolve()
    live_manifest = read_json(live / 'manifest.json')
    if live_manifest.get('exit') != 0 or live_manifest.get('mode') != 'LIVE':
        parser.error('必须使用已通过的SIM-01B LIVE目录')
    sys.path.insert(0, str(root / 'tests'))
    from check_sim01b_recording import validate_live
    checked_live = validate_live(live)
    if not checked_live['passed']:
        parser.error('LIVE归档重检失败：' + ';'.join(checked_live['errors']))
    config_path, values = load_settings(root, args.config)
    mode = args.mode
    run, session_id = create_session(root, mode)
    run_id = live_manifest['run_id']
    port = master_port(values, mode)
    env = configure_environment(run, port)
    manifest = dict(mode=mode, run_id=run_id, replay_session_id=session_id, run=str(run), live_run=str(live),
                    python=sys.executable, supervisor_pid=os.getpid(), ros_master_uri=env['ROS_MASTER_URI'],
                    commands=[], errors=[], armed_commands=False, phase='PREPARING', rate=1.0,
                    clock_source='recorded /clock; no generated clock')
    processes = Processes(run, env, manifest)
    recorder = None
    started = time.monotonic()
    wall_deadline = started + setting(values, 'wall_limit_s', 900.)
    startup_deadline = started + setting(values, 'startup_timeout_s', 60.)
    drain_s = setting(values, 'drain_timeout_s', 5.)
    progress_s = setting(values, 'replay_progress_timeout_s', 2.)
    sensor_audit = run / 'sensor-audit.jsonl'
    player_namespace = values.get('native_player_namespace', '/sim01b_native')
    if not isinstance(player_namespace, str) or not player_namespace.startswith('/') or player_namespace == '/':
        parser.error('native_player_namespace必须为非根的绝对namespace')
    topics = BUSINESS_TOPICS if mode == 'B1' else BUSINESS_TOPICS[:2]
    expected = expected_sequences(live, BUSINESS_TOPICS)
    install_interrupt_handler()
    passed = False
    try:
        manifest['ports_before'] = probe_ports(mode, port)
        if any(not p['free'] for p in manifest['ports_before']):
            raise RuntimeError('回放Master端口被占用，保留既有进程')
        for path in (config_path, live / 'sim01_state.yaml', root / 'ros_ws/launch/sim01b_sensors.launch'):
            shutil.copy2(path, run / path.name)
        shutil.copy2(live / 'window.json', run / 'window.json')
        master = start_master(processes, port, startup_deadline)
        import rospy
        rospy.init_node('sim01b_replay_recorder', disable_signals=True)
        recorder = Recorder(run, 'replay.bag', setting(values, 'writer_queue_limit', 10000), mode=mode,
                            source_limit_ns=setting(values, 'source_limit_ns', 600000000000))
        from rosgraph_msgs.msg import Clock
        private_clock_count = [0]

        def unexpected_clock(msg):
            with recorder.lock:
                private_clock_count[0] += 1
                recorder.errors.append('原生播放器生成了额外clock')

        private_clock_subscriber = rospy.Subscriber(player_namespace.rstrip('/') + '/clock',
            Clock, unexpected_clock, queue_size=1)
        if mode == 'B2':
            processes.spawn('sensors', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
                str(run / 'sim01b_sensors.launch'), 'run_id:=' + run_id,
                'config:=' + str(run / 'sim01_state.yaml'), 'audit_path:=' + str(sensor_audit)])
            while True:
                processes.check()
                published, subscribed = publishers(master)
                if all('/state_adapter' in subscribed.get(topic, []) for topic in topics) and \
                        recorder.subscribers['/uav/sensors/state'].get_num_connections() >= 1:
                    break
                if time.monotonic() >= startup_deadline:
                    raise RuntimeError('新sensors订阅登记超时')
                time.sleep(.02)
        # delay仅提供建连机会；下方实际TCP闸门及首receipt审计决定能否通过。
        player = processes.spawn('player', [sys.executable, str(root / 'ros_ws/sim01b_native_player.py'),
            '--rate', '1.0', '--wait-for-subscribers', '--delay', '2.0', '--queue', '1000',
            '--topics'] + list(topics) + ['--bags', str(live / 'live.bag')],
            extra_env={'ROS_NAMESPACE': player_namespace})
        while not playback_ready(master, recorder, mode, sensor_audit):
            processes.check()
            recorder.raise_errors()
            if recorder.snapshot()['business_last_receipt_ns'] is not None:
                raise RuntimeError('首业务消息先于全部实际TCP连接就绪')
            if time.monotonic() >= startup_deadline:
                raise RuntimeError('播放器实际TCP连接就绪超时')
            time.sleep(.01)
        gate_ns = time.monotonic_ns()
        first_snapshot = recorder.snapshot()
        if first_snapshot['business_last_receipt_ns'] is not None:
            raise RuntimeError('首业务receipt早于就绪闸门；本轮失败保留')
        published, subscribed = publishers(master)
        transport_queues = {topic: dict(impl_queue=sub.impl.queue_size,
            connections=[dict(queue=connection.protocol.queue_size)
                         for connection in sub.impl.connections])
            for topic, sub in recorder.subscribers.items()}
        write_json(run / 'connections-ready.json', dict(passed=True, gate_monotonic_ns=gate_ns,
                   publishers=published, subscribers=subscribed, selected_topics=list(topics), mode=mode,
                   transport_queues=transport_queues))
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise RuntimeError('回放Python进程未全部使用指定Conda')
        manifest['phase'] = 'ACTIVE'
        while time.monotonic() < wall_deadline:
            processes.check(allowed=('player',))
            recorder.raise_errors()
            if player.poll() is not None:
                if player.returncode != 0:
                    raise RuntimeError('播放器非零退出：' + str(player.returncode))
                processes.stopped.add('player')
                break
            if not check_clock_publishers(master):
                # C++可先注销ROS话题再退出；不能把正常EOF的短暂交接当作断流。
                eof_deadline = min(wall_deadline, time.monotonic() + progress_s)
                while player.poll() is None and time.monotonic() < eof_deadline:
                    processes.check(allowed=('player',))
                    recorder.raise_errors()
                    time.sleep(.01)
                if player.poll() != 0:
                    raise RuntimeError('clock注销后未在期限内正常EOF')
                processes.stopped.add('player')
                break
            snapshot = recorder.snapshot()
            last = snapshot['business_last_receipt_ns']
            if last is None and time.monotonic() >= startup_deadline:
                raise RuntimeError('回放首业务消息启动超时')
            if last is not None and time.monotonic_ns() - last > int(progress_s * 1000000000):
                raise RuntimeError('回放超过2墙秒无业务进展')
            for topic in topics:
                actual = snapshot['sequences'].get(topic, [])
                if len(actual) > len(expected[topic]) or actual != expected[topic][:len(actual)]:
                    raise RuntimeError('回放话题出现重复、额外或字节/序列不一致：' + topic)
            time.sleep(.05)
        else:
            raise RuntimeError('回放900墙秒安全截止')
        manifest['phase'] = 'DRAINING'
        deadline = min(wall_deadline, time.monotonic() + drain_s)
        while time.monotonic() < deadline:
            processes.check()
            recorder.raise_errors()
            snapshot = recorder.snapshot()
            complete = all(snapshot['sequences'].get(topic, []) == expected[topic] for topic in topics)
            if mode == 'B2':
                complete = complete and source_sensor_complete(recorder) and \
                    len(snapshot['adapted']) == len(expected['/uav/sensors/state'])
            if complete:
                break
            time.sleep(.02)
        else:
            raise RuntimeError('EOF后计数、序列或sensors身份未完整')
        if mode == 'B2':
            processes.stop('sensors', timeout=drain_s)
            deadline = min(wall_deadline, time.monotonic() + drain_s)
            while not audit_matches(sensor_audit, recorder):
                processes.check()
                recorder.raise_errors()
                if time.monotonic() >= deadline:
                    raise RuntimeError('B2 sensor封存台账与接收不一致')
                time.sleep(.02)
        closed = recorder.close(drain_s)
        private_clock_subscriber.unregister()
        manifest['private_clock_messages'] = private_clock_count[0]
        recorder = None
        if not closed['passed']:
            raise RuntimeError('回放writer关闭/重读失败：' + ';'.join(closed['errors']))
        from check_sim01b_replay import validate_replay
        validation = validate_replay(live, run, mode)
        write_json(run / 'validation.json', validation)
        if not validation['passed']:
            raise RuntimeError('回放验收失败：' + ';'.join(validation['errors']))
        manifest['phase'] = 'COMPLETE'
        passed = True
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
        cleanup['ports'] = probe_ports(mode, port)
        cleanup['passed'] = cleanup['passed'] and all(p['free'] for p in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        if not cleanup['passed']:
            manifest['errors'].append('本次回放进程/端口清理未通过')
        passed = passed and not manifest['errors'] and cleanup['passed']
        manifest.update(exit=0 if passed else 1, wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
        print(__import__('json').dumps(dict(run=str(run), mode=mode, exit=manifest['exit'],
              errors=manifest['errors'], cleanup=cleanup['passed'])), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
