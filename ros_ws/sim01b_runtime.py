"""SIM-01B传输、记录及进程管理；业务转换仍由所属模块执行。"""
import collections
import datetime
import io
import json
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
import xmlrpc.client

BUSINESS_TOPICS = ('/clock', '/uav/sim/state', '/uav/sensors/state')
RAW_TOPIC = '/mavlink/from'
DIAGNOSTIC_TOPIC = '/uav/diagnostics'


class BoundedTransport(xmlrpc.client.Transport):
    """只约束监督查询，不改变ROS业务socket的超时。"""
    def make_connection(self, host):
        connection = super().make_connection(host)
        connection.timeout = 1.0
        return connection


def rpc_proxy(uri):
    return xmlrpc.client.ServerProxy(uri, transport=BoundedTransport())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def read_json(path):
    return json.loads(Path(path).read_text())


def read_lines(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def load_settings(root, config=None):
    import yaml
    path = Path(config or root / 'configs/sim01b_recording.yaml').resolve()
    values = yaml.safe_load(path.read_text())
    if not isinstance(values, dict):
        raise ValueError('B配置必须为映射')
    # 数据验收使用本步冻结门槛；不接受未贯通消费者的自定义质量/窗口配置。
    limits = {'min_valid_span_ns': (300000000000, 300000000000), 'source_limit_ns': (1, 600000000000),
              'wall_limit_s': (1, 900), 'startup_timeout_s': (1, 60), 'drain_timeout_s': (.01, 5),
              'replay_progress_timeout_s': (.01, 2), 'writer_queue_limit': (1, 10000),
              'max_gap_ns': (500000000, 500000000), 'min_clock_hz': (40, 40), 'min_state_hz': (10, 10)}
    for name, (lower, upper) in limits.items():
        if name in values:
            number = float(values[name])
            if not lower <= number or (upper is not None and not number <= upper):
                raise ValueError('B配置必须遵守已确认且已贯通的门槛：' + name)
    return path, values


def setting(values, name, default):
    value = values.get(name, default)
    if isinstance(default, int):
        value = int(value)
    elif isinstance(default, float):
        value = float(value)
    return value


def state_config(root, values):
    path = Path(values.get('state_config', 'configs/sim01_state.yaml'))
    return path if path.is_absolute() else root / path


def master_port(values, mode):
    default = {'LIVE': 11341, 'B1': 11342, 'B2': 11343}[mode]
    return int(values.get(mode.lower() + '_master_port', values.get('master_ports', {}).get(mode, default)))


def create_session(root, mode):
    identity = 'sim01b-' + mode.lower() + '-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True, exist_ok=False)
    for name in ('rootfs', 'ros-home', 'ros-logs'):
        (run / name).mkdir()
    return run, identity


def probe_ports(mode, port):
    ports = [(socket.SOCK_STREAM, [port])]
    if mode == 'LIVE':
        ports += [(socket.SOCK_STREAM, [4560]),
                  (socket.SOCK_DGRAM, [14540, 14580, 18570, 14280, 13030])]
    result = []
    for kind, numbers in ports:
        for number in numbers:
            with socket.socket(socket.AF_INET, kind) as probe:
                if kind == socket.SOCK_STREAM:
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(('0.0.0.0', number))
                    result.append(dict(port=number, free=True))
                except OSError as exc:
                    result.append(dict(port=number, free=False, error=str(exc)))
    return result


def reject_existing_px4():
    for path in Path('/proc').glob('[0-9]*/comm'):
        try:
            if path.read_text().strip() == 'px4':
                raise RuntimeError('既有PX4进程保留，本会话停止')
        except (FileNotFoundError, ProcessLookupError):
            pass


def python_process_audit():
    parents = {}
    for entry in Path('/proc').glob('[0-9]*'):
        try:
            value = (entry / 'stat').read_text()
            fields = value[value.rfind(')') + 2:].split()
            parents[int(entry.name)] = int(fields[1])
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    owned = {os.getpid()}
    while True:
        expanded = owned | {pid for pid, parent in parents.items() if parent in owned}
        if expanded == owned:
            break
        owned = expanded
    expected = str(Path(os.environ['UFM_PYTHON']).resolve())
    records = []
    for pid in sorted(owned):
        try:
            executable = (Path('/proc') / str(pid) / 'exe').resolve(strict=True)
            if executable.name.startswith('python'):
                args = (Path('/proc') / str(pid) / 'cmdline').read_bytes().decode().split('\0')
                stat = (Path('/proc') / str(pid) / 'stat').read_text()
                fields = stat[stat.rfind(')') + 2:].split()
                records.append(dict(pid=pid, executable=str(executable), args=[a for a in args if a],
                                    start_ticks=int(fields[19])))
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return dict(passed=bool(records) and all(r['executable'] == expected for r in records),
                expected=expected, processes=records)


class Processes:
    """每个进程使用独立进程组，仅向本会话创建的进程组发信号。"""
    def __init__(self, run, env, manifest):
        self.run, self.env, self.manifest = run, env, manifest
        self.children, self.handles, self.stopped, self.forced = {}, [], set(), []

    def spawn(self, name, command, cwd=None, extra_env=None):
        handle = (self.run / (name + '.log')).open('x')
        self.handles.append(handle)
        child_env = dict(self.env, **(extra_env or {}))
        process = subprocess.Popen(command, cwd=cwd or self.run, env=child_env,
                                   stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        self.children[name] = process
        self.manifest['commands'].append(dict(name=name, args=list(command), pid=process.pid,
                                             environment_overrides=extra_env or {}))
        write_json(self.run / 'manifest.json', self.manifest)
        return process

    def check(self, allowed=()):
        for name, process in self.children.items():
            if name not in self.stopped and name not in allowed and process.poll() is not None:
                raise RuntimeError(name + '意外退出：' + str(process.returncode))

    def stop(self, name, timeout=5.):
        process = self.children.get(name)
        if process is None or name in self.stopped:
            return
        if process.poll() is not None:
            self.stopped.add(name)
            raise RuntimeError(name + '正常关闭前已经退出：' + str(process.returncode))
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.forced.append(name)
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=2.)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2.)
        self.stopped.add(name)
        if name in self.forced:
            raise RuntimeError(name + '未正常关闭，使用了强制信号')
        if process.returncode not in (0, -signal.SIGINT):
            raise RuntimeError(name + '关闭退出码不正常：' + str(process.returncode))

    def cleanup(self):
        for name in reversed(list(self.children)):
            process = self.children[name]
            if name not in self.stopped and process.poll() is None:
                try:
                    self.stop(name)
                except (RuntimeError, ProcessLookupError) as exc:
                    self.manifest['errors'].append('cleanup: ' + str(exc))
            self.manifest.setdefault('exits', {})[name] = process.poll()
        for handle in self.handles:
            handle.close()
        remaining = []
        for item in self.manifest.get('python_process_audit', {}).get('processes', []):
            if item['pid'] == os.getpid():
                continue
            try:
                stat = (Path('/proc') / str(item['pid']) / 'stat').read_text()
                fields = stat[stat.rfind(')') + 2:].split()
                if fields[0] != 'Z' and int(fields[19]) == item.get('start_ticks'):
                    remaining.append(item['pid'])
            except (FileNotFoundError, ProcessLookupError):
                pass
        return dict(children=[dict(name=n, pid=p.pid, exit=p.poll()) for n, p in self.children.items()],
                    forced=list(self.forced), remaining_audited_python_pids=remaining,
                    passed=not self.forced and not remaining and
                    all(p.poll() is not None for p in self.children.values()))


def configure_environment(run, port):
    if sys.executable != os.environ.get('UFM_PYTHON'):
        raise RuntimeError('必须使用已配置Conda解释器：' + str(sys.executable))
    env = dict(os.environ, ROS_MASTER_URI='http://127.0.0.1:' + str(port), ROS_IP='127.0.0.1',
               ROS_HOME=str(run / 'ros-home'), ROS_LOG_DIR=str(run / 'ros-logs'),
               HEADLESS='1', PX4_SIM_MODEL='rascal', PX4_SIM_SPEED_FACTOR='1', MAVLINK20='1')
    # rospy.init_node在本监督器中执行，必须与所有子进程连接同一新Master。
    os.environ.update({k: env[k] for k in ('ROS_MASTER_URI', 'ROS_IP', 'ROS_HOME', 'ROS_LOG_DIR')})
    return env


def start_master(processes, port, deadline):
    processes.spawn('roscore', [sys.executable, '/opt/ros/noetic/bin/roscore', '-p', str(port)])
    master = rpc_proxy(processes.env['ROS_MASTER_URI'])
    while time.monotonic() < deadline:
        processes.check()
        try:
            if master.getPid('/sim01b_supervisor')[0] == 1:
                master.setParam('/sim01b_supervisor', '/use_sim_time', True)
                return master
        except (OSError, xmlrpc.client.Error):
            pass
        time.sleep(.05)
    raise RuntimeError('ROS Master启动超时')


def publishers(master):
    response = master.getSystemState('/sim01b_supervisor')
    if response[0] != 1:
        raise RuntimeError('无法读取ROS连接状态')
    return dict(response[2][0]), dict(response[2][1])


def check_clock_publishers(master, required=False):
    published, _ = publishers(master)
    nodes = published.get('/clock', [])
    if len(nodes) > 1 or (required and len(nodes) != 1):
        raise RuntimeError('必须只有一个/clock发布者：' + repr(nodes))
    return nodes


def wait_ready(master, recorder, processes, topics, deadline, require_sensor=False):
    import rospy
    while time.monotonic() < deadline:
        processes.check()
        recorder.raise_errors()
        published, subscribed = publishers(master)
        check_clock_publishers(master)
        ready = all(recorder.subscribers[t].get_num_connections() >= 1 for t in topics)
        if require_sensor:
            ready = ready and '/state_adapter' in subscribed.get('/clock', []) and \
                '/state_adapter' in subscribed.get('/uav/sim/state', [])
            # 从源节点XML-RPC读取实际TCP连接，订阅注册本身不代表联通。
            try:
                uri = master.lookupNode('/sim01b_supervisor', '/state_clock')
                stats = rpc_proxy(uri[2]).getBusInfo('/sim01b_supervisor')
                outgoing = {(item[1], item[4]) for item in stats[2] if item[2] == 'o' and item[5]}
                ready = ready and ('/state_adapter', '/clock') in outgoing and \
                    ('/state_adapter', '/uav/sim/state') in outgoing
            except (OSError, xmlrpc.client.Error, IndexError):
                ready = False
        if ready:
            write_json(recorder.run / 'connections-ready.json', dict(passed=True, publishers=published,
                       subscribers=subscribed, timestamp_monotonic_ns=time.monotonic_ns()))
            return
        if rospy.is_shutdown():
            raise RuntimeError('就绪前ROS停止')
        time.sleep(.05)
    raise RuntimeError('ROS真实连接就绪超时')


class Recorder:
    """回调串行分配接收序号；有界队列、单写线程同时写bag与sidecar。"""
    def __init__(self, run, bag_name, queue_limit, mode='LIVE', source_limit_ns=600000000000):
        import rosbag
        import rospy
        from diagnostic_msgs.msg import DiagnosticArray
        from mavros_msgs.msg import Mavlink
        from rosgraph_msgs.msg import Clock
        from uav_fusionmap_msgs.msg import AircraftState
        self.run, self.mode, self.source_limit_ns = run, mode, source_limit_ns
        self.lock = threading.RLock()
        self.errors, self.topic_sequences = [], collections.defaultdict(list)
        self.source, self.adapted, self.clocks = [], [], []
        self.raw_counts, self.node_pythons = collections.Counter(), {}
        self.received_counts, self.written_counts = collections.Counter(), collections.Counter()
        self.record_seq, self.written_records = 0, 0
        self.start_ns = time.monotonic_ns()
        self.business_last_receipt_ns = None
        self.queue = queue.Queue(maxsize=queue_limit)
        self.subscribers, self.closed = {}, False
        self.bag_path = run / bag_name
        self.bag = rosbag.Bag(str(self.bag_path), 'w')
        self.sidecar = (run / 'records.jsonl').open('x')
        self.worker = threading.Thread(target=self._writer, name='sim01b-bag-writer', daemon=True)
        self.worker.start()
        classes = {'/clock': Clock, '/uav/sim/state': AircraftState, '/uav/sensors/state': AircraftState,
                   DIAGNOSTIC_TOPIC: DiagnosticArray}
        if mode == 'LIVE':
            classes[RAW_TOPIC] = Mavlink
        for topic, klass in classes.items():
            self.subscribers[topic] = rospy.Subscriber(topic, klass, self._receive, topic,
                                                      queue_size=10000 if topic == RAW_TOPIC else 1000)
        write_json(run / 'recorder-ready.json', dict(passed=True, topics=list(classes),
                   record_start_monotonic_ns=self.start_ns, python=sys.executable,
                   writer_queue_limit=queue_limit))

    def _receive(self, message, topic):
        from ufm_ros_contract import from_ros_state
        with self.lock:
            if self.closed:
                self.errors.append('记录器关闭后仍收到消息：' + topic)
                return
            try:
                receipt_ns = time.monotonic_ns()
                buffer = io.BytesIO()
                message.serialize(buffer)
                self.record_seq += 1
                record = dict(record_seq=self.record_seq, topic=topic, receipt_monotonic_ns=receipt_ns,
                              bag_time_ns=receipt_ns - self.start_ns, wire_hex=buffer.getvalue().hex())
                if topic in BUSINESS_TOPICS:
                    self.business_last_receipt_ns = receipt_ns
                    self.topic_sequences[topic].append(record['wire_hex'])
                if topic == '/clock':
                    ns = message.clock.to_nsec()
                    record['timestamp'] = ns
                    if self.clocks and ns <= self.clocks[-1]:
                        self.errors.append('clock回退或重复')
                    self.clocks.append(ns)
                    if ns >= self.source_limit_ns:
                        self.errors.append('600秒绝对源安全截止')
                elif topic in ('/uav/sim/state', '/uav/sensors/state'):
                    state = from_ros_state(message)
                    record.update(state=state, timestamp=state['header']['timestamp'],
                                  sample_id=state['header']['sample_id'])
                    target = self.source if topic == '/uav/sim/state' else self.adapted
                    if state['header']['status'] != 'valid':
                        self.errors.append('上游terminal：' + state['header']['reason'])
                    if target and state['header']['timestamp'] <= target[-1]['header']['timestamp']:
                        self.errors.append(topic + '时间回退或重复')
                    target.append(state)
                elif topic == DIAGNOSTIC_TOPIC:
                    record['items'] = [dict(name=d.name, level=d.level, message=d.message,
                                           values={v.key: v.value for v in d.values}) for d in message.status]
                    for item in record['items']:
                        if item['level'] >= 2:
                            self.errors.append('ERROR诊断：' + item['name'] + ':' + item['message'])
                        for key in ('pending_timeout', 'pending_overflow', 'sample_identity_conflict',
                                    'duplicate_state', 'duplicate_clock', 'old_state', 'clock_regression'):
                            if int(item['values'].get(key, '0')):
                                self.errors.append('诊断中的丢帧/身份/时钟故障：' + key)
                        if 'python' in item['values']:
                            self.node_pythons[item['name']] = item['values']['python']
                            if item['values']['python'] != os.environ['UFM_PYTHON']:
                                self.errors.append('节点解释器不符：' + item['name'])
                elif topic == RAW_TOPIC:
                    from mavros.mavlink import convert_to_bytes
                    from pymavlink.dialects.v20 import common
                    wire = convert_to_bytes(message)
                    record.update(raw_wire_hex=wire.hex(), framing=message.framing_status,
                                  msgid=message.msgid, sysid=message.sysid, compid=message.compid)
                    if message.framing_status != 1:
                        self.errors.append('MAVLink framing错误')
                    else:
                        if message.msgid == 0:
                            decoded = common.MAVLink(None).decode(wire)
                            if decoded.base_mode & 128:
                                self.errors.append('出现解锁心跳')
                        if (message.sysid, message.compid) == (1, 1):
                            self.raw_counts[str(message.msgid)] += 1
                            if message.msgid == 105:
                                decoded = common.MAVLink(None).decode(wire)
                                if decoded.time_usec * 1000 >= self.source_limit_ns:
                                    self.errors.append('原始IMU达到600秒绝对源安全截止')
                self.received_counts[topic] += 1
                self.queue.put_nowait((record, message))
            except queue.Full:
                self.errors.append('记录writer队列满，停止本轮')
            except Exception as exc:
                self.errors.append('记录回调：' + str(exc))

    def _writer(self):
        import genpy
        while True:
            item = self.queue.get()
            try:
                if item is None:
                    return
                record, message = item
                ns = record['bag_time_ns']
                self.bag.write(record['topic'], message, t=genpy.Time(ns // 1000000000, ns % 1000000000))
                self.sidecar.write(json.dumps(record, separators=(',', ':')) + '\n')
                self.written_records += 1
                self.written_counts[record['topic']] += 1
            except Exception as exc:
                with self.lock:
                    self.errors.append('writer写入失败：' + str(exc))
            finally:
                self.queue.task_done()

    def raise_errors(self):
        with self.lock:
            if self.errors:
                raise RuntimeError('; '.join(dict.fromkeys(self.errors)))

    def snapshot(self):
        with self.lock:
            return dict(source=list(self.source), adapted=list(self.adapted), clocks=list(self.clocks),
                        counts=dict(self.received_counts), sequences={k: list(v) for k, v in self.topic_sequences.items()},
                        errors=list(self.errors), node_pythons=dict(self.node_pythons),
                        business_last_receipt_ns=self.business_last_receipt_ns)

    def close(self, timeout=5.):
        import rosbag
        for subscriber in self.subscribers.values():
            subscriber.unregister()
        with self.lock:
            self.closed = True
        deadline = time.monotonic() + timeout
        while self.queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(.01)
        if self.queue.unfinished_tasks:
            self.errors.append('writer排空超时')
        try:
            self.queue.put(None, timeout=max(.01, deadline - time.monotonic()))
            self.worker.join(timeout=max(.01, deadline - time.monotonic()))
        except queue.Full:
            self.errors.append('writer关闭队列满')
        if self.worker.is_alive():
            # 不与仍写入的线程并发关闭文件，也不声称落盘完成。
            self.errors.append('writer未关闭')
            result = dict(passed=False, errors=list(self.errors), queue_empty=False,
                          records=self.written_records, counts=dict(self.written_counts),
                          topic_counts=dict(self.written_counts), record_start_monotonic_ns=self.start_ns)
            write_json(self.run / 'writer-closed.json', result)
            return result
        self.sidecar.close()
        self.bag.close()
        disk_counts = collections.Counter()
        disk_records = 0
        with rosbag.Bag(str(self.bag_path), 'r') as bag, (self.run / 'records.jsonl').open() as sidecar:
            disk = iter(bag.read_messages())
            for line in sidecar:
                record = json.loads(line)
                try:
                    topic, message, stamp = next(disk)
                except StopIteration:
                    self.errors.append('bag少于sidecar')
                    break
                buffer = io.BytesIO()
                message.serialize(buffer)
                if (topic != record['topic'] or stamp.to_nsec() != record['bag_time_ns'] or
                        buffer.getvalue().hex() != record['wire_hex']):
                    self.errors.append('bag重读与sidecar不符')
                disk_records += 1
                disk_counts[topic] += 1
            if next(disk, None) is not None:
                self.errors.append('bag多于sidecar')
        if disk_records != self.record_seq or self.written_records != self.record_seq:
            self.errors.append('接收/写入/重读记录数不符')
        result = dict(passed=not self.errors, errors=list(dict.fromkeys(self.errors)),
                      records=disk_records, counts=dict(disk_counts), topic_counts=dict(disk_counts),
                      received_counts=dict(self.received_counts), queue_empty=not self.queue.unfinished_tasks,
                      record_start_monotonic_ns=self.start_ns, python=sys.executable)
        write_json(self.run / 'writer-closed.json', result)
        return result


def audit_matches(path, recorder):
    marker_path = Path(str(path) + '.closed.json')
    if not marker_path.exists():
        return False
    marker = read_json(marker_path)
    if not marker.get('passed') or marker.get('pending_count', 0) != 0:
        raise RuntimeError('发布审计关闭失败：' + str(path))
    audits = read_lines(path)
    expected = collections.defaultdict(list)
    for index, record in enumerate(audits, 1):
        if record['seq'] != index:
            raise RuntimeError('发布审计seq不连续')
        expected[record['topic']].append(record['wire_hex'])
    observed = recorder.snapshot()['sequences']
    expected_topics = ('/clock', '/uav/sim/state') if 'source' in Path(path).name else ('/uav/sensors/state',)
    return all(observed.get(topic, []) == expected.get(topic, []) for topic in expected_topics) and \
        sum(map(len, expected.values())) == marker['records'] and \
        dict(collections.Counter(a['topic'] for a in audits)) == marker['topic_counts']


def source_sensor_complete(recorder):
    snapshot = recorder.snapshot()
    source = collections.Counter(s['header']['sample_id'] for s in snapshot['source'])
    adapted = collections.Counter(s['header']['sample_id'][len('sensors.state:'):]
                                  for s in snapshot['adapted'] if s['header']['sample_id'].startswith('sensors.state:'))
    return bool(source) and source == adapted and len(snapshot['adapted']) == sum(adapted.values()) and \
        bool(snapshot['clocks']) and all(s['header']['timestamp'] <= snapshot['clocks'][-1]
                                       for s in snapshot['source'])


def expected_sequences(live, topics):
    import rosbag
    result = {topic: [] for topic in topics}
    with rosbag.Bag(str(live / 'live.bag'), 'r') as bag:
        for topic, message, _ in bag.read_messages(topics=topics):
            buffer = io.BytesIO()
            message.serialize(buffer)
            result[topic].append(buffer.getvalue().hex())
    if any(not items for items in result.values()):
        raise RuntimeError('待回放业务话题为空')
    return result


def run_checker(root, command, run, env):
    with (run / 'validation.log').open('x') as output:
        completed = subprocess.run([sys.executable, str(root / 'tests' / command[0])] + command[1:],
                                   env=env, stdout=output, stderr=subprocess.STDOUT, timeout=60.)
    return completed.returncode == 0


def install_interrupt_handler():
    def interrupt(signum, frame):
        raise RuntimeError('监督器收到信号：' + str(signum))
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
