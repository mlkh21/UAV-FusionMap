"""SIM-01C故障场景与bridge倍速矩阵的独立会话监督器。"""
import argparse
import collections
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
    probe_ports, python_process_audit, read_json, reject_existing_px4, rpc_proxy,
    start_master, write_json)


FAULT_SCENARIOS = tuple('C-F%d' % index for index in range(8))
SPEED_SCENARIOS = ('SPEED_2', 'SPEED_05', 'SPEED_1')
DEFAULT_ORDER = FAULT_SCENARIOS + SPEED_SCENARIOS
SPEED_CASES = {'SPEED_05': 'half', 'SPEED_1': 'nominal', 'SPEED_2': 'double'}
MATRIX_ORDER = (
    (1, 'A', 1, 'SPEED_05', 0.5),
    (2, 'A', 2, 'SPEED_1', 1.0),
    (3, 'A', 3, 'SPEED_2', 2.0),
    (4, 'B', 1, 'SPEED_2', 2.0),
    (5, 'B', 2, 'SPEED_1', 1.0),
    (6, 'B', 3, 'SPEED_05', 0.5),
    (7, 'C', 1, 'SPEED_1', 1.0),
    (8, 'C', 2, 'SPEED_05', 0.5),
    (9, 'C', 3, 'SPEED_2', 2.0),
)
SELECTION_RULE = ('first_clock_at_or_after_first_valid_source_plus_warmup_then_'
                  'first_clock_at_or_after_c0_plus_measurement_span')


def file_identity(path):
    """返回可复核文件身份；矩阵运行期间使用同一冻结对象逐项比较。"""
    resolved = Path(path).resolve(strict=True)
    stat = resolved.stat()
    digest = hashlib.sha256()
    with resolved.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return dict(path=str(resolved), size=stat.st_size, mtime_ns=stat.st_mtime_ns,
                sha256=digest.hexdigest())


def _available_read(path, transform=lambda value: value):
    try:
        return dict(available=True, value=transform(Path(path).read_text(errors='replace').strip()))
    except (OSError, ValueError) as exc:
        return dict(available=False, reason=type(exc).__name__ + ': ' + str(exc))


def boot_id():
    evidence = _available_read('/proc/sys/kernel/random/boot_id')
    if not evidence['available'] or not evidence['value']:
        raise RuntimeError('无法封存主机boot_id，不能证明九次矩阵处于同一启动周期')
    return evidence['value']


def _glob_values(pattern, transform=lambda value: value):
    rows = []
    for path in sorted(Path('/').glob(pattern.lstrip('/'))):
        evidence = _available_read(path, transform)
        evidence['path'] = str(path)
        rows.append(evidence)
    return dict(available=bool(rows) and all(row['available'] for row in rows), values=rows,
                reason='no matching host interface' if not rows else None)


def host_resource_evidence():
    """尽可能记录主机调度环境；缺失接口显式为available=false。"""
    load = _available_read('/proc/loadavg', lambda value: [float(item) for item in value.split()[:3]])
    governors = _glob_values('/sys/devices/system/cpu/cpu*/cpufreq/scaling_governor')
    frequencies = _glob_values('/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq', int)
    temperatures = _glob_values('/sys/class/thermal/thermal_zone*/temp', int)
    throttle_paths = tuple(sorted(Path('/').glob(
        'sys/devices/system/cpu/cpu*/thermal_throttle/*'))) + (
        Path('/sys/devices/platform/soc/soc:firmware/get_throttled'),)
    throttle = []
    for path in throttle_paths:
        if path.is_file():
            value = _available_read(path)
            value['path'] = str(path)
            throttle.append(value)
    return dict(load=load, governors=governors, frequencies_khz=frequencies,
                temperatures_millidegree_c=temperatures,
                throttle=dict(available=bool(throttle) and
                              all(item['available'] for item in throttle), values=throttle,
                              reason='no host throttle interface' if not throttle else None))


def process_resource_evidence(pid):
    """读取一个受管进程的/proc资源快照，不用缺失字段伪造0。"""
    base = Path('/proc') / str(pid)
    result = dict(pid=pid, available=False)
    try:
        stat = (base / 'stat').read_text().split()
        status = {}
        for line in (base / 'status').read_text(errors='replace').splitlines():
            if ':' in line:
                key, value = line.split(':', 1)
                status[key] = value.strip()
        io_values = {}
        try:
            for line in (base / 'io').read_text(errors='replace').splitlines():
                key, value = line.split(':', 1)
                io_values[key] = int(value.strip())
            io_evidence = dict(available=True, values=io_values)
        except (OSError, ValueError) as exc:
            io_evidence = dict(available=False, reason=type(exc).__name__ + ': ' + str(exc))
        ticks = os.sysconf('SC_CLK_TCK')
        result.update(available=True, user_ticks=int(stat[13]), system_ticks=int(stat[14]),
                      clock_ticks_per_second=ticks,
                      user_seconds=int(stat[13]) / ticks,
                      system_seconds=int(stat[14]) / ticks,
                      voluntary_context_switches=int(status['voluntary_ctxt_switches']),
                      nonvoluntary_context_switches=int(status['nonvoluntary_ctxt_switches']),
                      allowed_cpus=status['Cpus_allowed_list'], io=io_evidence)
    except (OSError, ValueError, IndexError, KeyError) as exc:
        result['reason'] = type(exc).__name__ + ': ' + str(exc)
    return result


def managed_process_resources(processes):
    if processes is None:
        return dict(available=False, reason='process manager was not created', processes=[])
    rows = []
    for name, process in processes.children.items():
        row = process_resource_evidence(process.pid)
        row['name'] = name
        rows.append(row)
    return dict(available=bool(rows) and all(row['available'] for row in rows), processes=rows,
                reason='one or more managed processes exited before snapshot'
                if rows and not all(row['available'] for row in rows) else None)


def cpu_environment():
    """记录可复核的轻量CPU调度环境，不宣称它是性能验收。"""
    model = 'unknown'
    try:
        for line in Path('/proc/cpuinfo').read_text(errors='replace').splitlines():
            if line.lower().startswith('model name'):
                model = line.split(':', 1)[1].strip()
                break
    except OSError:
        pass
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except AttributeError:
        affinity = list(range(os.cpu_count() or 0))
    return dict(model=model, logical_count=os.cpu_count(), affinity=affinity,
                host=host_resource_evidence())


def canonical_scenario(value):
    raw = value.strip().upper()
    if raw in ('ALL', '*'):
        return 'ALL'
    if raw in SPEED_SCENARIOS:
        return raw
    token = raw.replace('-', '_')
    if token.startswith('C_'):
        token = token[2:]
    if token.startswith('F') and token[1:].isdigit() and 0 <= int(token[1:]) <= 7:
        return 'C-F%d' % int(token[1:])
    raise ValueError('未知SIM-01C场景：' + value)


def _same_frozen_value(actual, required):
    if isinstance(actual, bool) or isinstance(required, bool):
        return actual is required
    try:
        return math.isclose(float(actual), float(required), rel_tol=0., abs_tol=0.)
    except (TypeError, ValueError):
        return actual == required


def load_config(root, path=None):
    import yaml
    config_path = Path(path or root / 'configs/sim01c_scenarios.yaml').resolve()
    values = yaml.safe_load(config_path.read_text())
    if not isinstance(values, dict) or values.get('schema_version') != '0.1':
        raise ValueError('SIM-01C配置缺少可识别的schema_version')
    state_path = Path(values.get('state_config', ''))
    state_path = state_path if state_path.is_absolute() else root / state_path
    state_values = yaml.safe_load(state_path.read_text())
    for key, required in values.get('required_production_thresholds', {}).items():
        if key not in state_values or not _same_frozen_value(state_values[key], required):
            raise ValueError('生产状态门槛漂移：%s actual=%r required=%r' %
                             (key, state_values.get(key), required))
    scenarios = values.get('scenarios')
    if not isinstance(scenarios, dict) or set(scenarios) != {'F%d' % i for i in range(8)}:
        raise ValueError('SIM-01C必须精确定义F0—F7')
    speed = values.get('speed_smoke', {})
    if set(speed.get('cases', {})) != {'half', 'nominal', 'double'}:
        raise ValueError('SIM-01C必须精确定义half/nominal/double倍速测量')
    if int(speed.get('warmup_source_span_ns', -1)) != 5000000000:
        raise ValueError('SIM-SPEED-01必须使用固定5源秒warmup')
    matrix = speed.get('matrix', {})
    plan = matrix.get('planned_runs')
    frozen = [(item.get('global_index'), item.get('batch'), item.get('batch_index'),
               item.get('scenario'), float(item.get('requested_factor', -1)))
              for item in plan] if isinstance(plan, list) else []
    if tuple(frozen) != MATRIX_ORDER or matrix.get('selection_rule') != SELECTION_RULE:
        raise ValueError('SIM-SPEED-01九次矩阵计划或端点规则漂移')
    for scenario, case_key in SPEED_CASES.items():
        if not math.isclose(float(speed['cases'][case_key]['requested_factor']),
                            dict((item[3], item[4]) for item in MATRIX_ORDER)[scenario],
                            rel_tol=0., abs_tol=0.):
            raise ValueError('SIM-SPEED-01场景倍率与冻结矩阵不一致：' + scenario)
    ports = [int(item['master_port']) for item in scenarios.values()]
    ports += [int(item['master_port']) for item in speed['cases'].values()]
    if len(ports) != len(set(ports)):
        raise ValueError('SIM-01C每个会话必须使用独立ROS Master端口')
    return config_path, state_path.resolve(), values


def create_suite(root):
    suite_id = 'sim01c-suite-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    suite = root / '.runtime/runs' / suite_id
    suite.mkdir(parents=True, exist_ok=False)
    return suite, suite_id


def create_run(suite, suite_id, scenario, suffix=None):
    name = scenario.lower().replace('_', '-').replace('c-', '')
    if suffix:
        name += '-' + suffix
    run = suite / name
    run.mkdir()
    for directory in ('rootfs', 'ros-home', 'ros-logs'):
        (run / directory).mkdir()
    return run, suite_id + '-' + name


def _copy_inputs(root, run, config_path, state_path, speed=False):
    sources = [config_path, state_path, root / 'ros_ws/launch/sim01b_source.launch',
               root / 'ros_ws/launch/sim01b_sensors.launch']
    if speed:
        sources.append(root / 'ros_ws/launch/sim00b_mavros.launch')
    else:
        sources += [root / 'tests/check_sim01c_scenario.py',
                    root / 'tests/sim01c_mavlink_fault_driver.py']
    for source in sources:
        if source.exists():
            shutil.copy2(source, run / source.name)


def _wait_node(master, processes, name, deadline, allowed=()):
    while time.monotonic() < deadline:
        processes.check(allowed=allowed)
        try:
            response = master.lookupNode('/sim01c_supervisor', name)
            if response[0] == 1:
                return time.monotonic_ns()
        except (OSError, IndexError):
            pass
        time.sleep(.02)
    raise RuntimeError('ROS节点启动超时：' + name)


def _wait_files(paths, processes, deadline, allowed=()):
    paths = [Path(path) for path in paths]
    while time.monotonic() < deadline:
        processes.check(allowed=allowed)
        if all(path.exists() for path in paths):
            return
        time.sleep(.02)
    raise RuntimeError('等待就绪证据超时：' + ', '.join(map(str, paths)))


def _stop_if_running(processes, name, timeout):
    process = processes.children.get(name)
    if process is not None and process.poll() is None:
        processes.stop(name, timeout=timeout)


def _wait_successful_child(processes, name, deadline, allowed=()):
    """有界等待本会话子进程封存自身台账。"""
    process = processes.children[name]
    while time.monotonic() < deadline:
        processes.check(allowed=tuple(set(allowed) | {name}))
        if process.poll() is not None:
            if process.returncode != 0:
                raise RuntimeError(name + '失败：' + str(process.returncode))
            return
        time.sleep(.02)
    raise RuntimeError('等待%s封存超时' % name)


def _trigger_is_valid(trigger, scenario, run_id):
    if trigger.get('run_id') != run_id or canonical_scenario(trigger.get('scenario', '')) != scenario:
        return False
    return trigger.get('passed') is True or trigger.get('observed') is True


def _run_offline_checker(root, run, run_id, scenario, config_path, previous_run, env, manifest):
    command = [sys.executable, str(root / 'tests/check_sim01c_scenario.py'),
               str(run), run_id, scenario, '--config', str(config_path), '--offline']
    if previous_run is not None:
        command += ['--previous-run', str(previous_run)]
    with (run / 'offline-checker.log').open('x') as output:
        completed = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT,
                                   timeout=60.)
    manifest['commands'].append(dict(name='offline-checker', args=command, exit=completed.returncode))
    if completed.returncode:
        raise RuntimeError('SIM-01C离线验收未通过：' + str(completed.returncode))
    result = read_json(run / 'scenario-result.json')
    if result.get('passed') is not True:
        raise RuntimeError('SIM-01C离线验收结果不是passed')
    return result


def _run_speed_checker(root, run, run_id, case_key, config_path, env, manifest,
                       factor_passed):
    command = [sys.executable, str(root / 'tests/check_sim01c_scenario.py'),
               str(run), run_id, 'SPEED-' + case_key, '--config', str(config_path), '--offline']
    with (run / 'offline-checker.log').open('x') as output:
        completed = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT,
                                   timeout=60.)
    manifest['commands'].append(dict(name='offline-checker', args=command,
                                     exit=completed.returncode))
    checked = read_json(run / 'scenario-result.json')
    tolerance_error = 'speed: actual_factor outside requested +/- tolerance'
    unexpected = [error for error in checked.get('errors', []) if error != tolerance_error]
    if unexpected:
        raise RuntimeError('倍速离线验收失败：' + '; '.join(unexpected))
    if checked.get('passed') is not bool(factor_passed):
        raise RuntimeError('倍速离线结果与factor_passed不一致')
    return checked


def _run_speed_matrix_checker(root, suite, matrix_id, config_path):
    command = [sys.executable, str(root / 'tests/check_sim01c_scenario.py'),
               str(suite), matrix_id, 'SPEED-MATRIX', '--config', str(config_path), '--offline']
    with (suite / 'speed-matrix-checker.log').open('x') as output:
        completed = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=120.)
    result_path = suite / 'speed-matrix-result.json'
    result = read_json(result_path) if result_path.exists() else {}
    return dict(command=command, exit=completed.returncode, result=result)


def run_fault_scenario(root, suite, suite_id, scenario, config_path, state_path, values,
                       previous_run=None):
    key = scenario[2:]
    settings = values['scenarios'][key]
    safety = values['safety']
    run, run_id = create_run(suite, suite_id, scenario)
    _copy_inputs(root, run, config_path, state_path)
    port = int(settings['master_port'])
    expected = settings['expected']
    expected_reason = expected.get('terminal_code', expected.get('local_error_code', 'normal_run'))
    manifest = dict(schema_version='0.1', suite_run_id=suite_id, scenario=scenario,
                    run_id=run_id, run=str(run), python=sys.executable,
                    supervisor_pid=os.getpid(), ros_master_uri='http://127.0.0.1:' + str(port),
                    expected_reason=expected_reason,
                    allowed_diagnostics=settings.get('allowed_diagnostics', {}), commands=[], errors=[],
                    armed_commands=False, phase='PREPARING', previous_run=str(previous_run) if previous_run else None)
    processes = None
    env = None
    started = time.monotonic()
    checker_started = False
    online_passed = False
    offline_passed = False
    cleanup = dict(passed=False, children=[], forced=[], remaining_audited_python_pids=[], ports=[])
    cleanup_timeout = float(safety['cleanup_timeout_s'])
    wall_deadline = started + float(settings['wall_safety_cutoff_s'])
    source_audit = run / 'source-audit.jsonl'
    sensor_audit = run / 'sensor-audit.jsonl'
    try:
        if scenario == 'C-F7' and previous_run is None:
            raise RuntimeError('F7必须显式引用F3前驱run')
        manifest['ports_before'] = probe_ports('B1', port)
        if any(not item['free'] for item in manifest['ports_before']):
            raise RuntimeError('ROS Master端口被占用，保留既有进程')
        env = configure_environment(run, port)
        processes = Processes(run, env, manifest)
        install_interrupt_handler()
        master = start_master(processes, port, min(wall_deadline, time.monotonic() + 10.))

        checker_command = [sys.executable, str(root / 'tests/check_sim01c_scenario.py'),
                           str(run), run_id, scenario, '--config', str(config_path)]
        if previous_run is not None:
            checker_command += ['--previous-run', str(previous_run)]
        processes.spawn('checker', checker_command)
        checker_started = True
        manifest['checker_start_monotonic_ns'] = time.monotonic_ns()

        processes.spawn('sensors', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
            str(run / 'sim01b_sensors.launch'), 'run_id:=' + run_id,
            'config:=' + str(run / state_path.name), 'audit_path:=' + str(sensor_audit)])
        _wait_node(master, processes, '/state_adapter', min(wall_deadline, time.monotonic() + 10.),
                   allowed=('checker',))

        if scenario != 'C-F6':
            driver_command = [sys.executable, str(root / 'tests/sim01c_mavlink_fault_driver.py'),
                              str(run), run_id, scenario,
                              '--input-topic', values['fixture_input']['topic']]
            processes.spawn('driver', driver_command)
            manifest['driver_start_monotonic_ns'] = time.monotonic_ns()
            processes.spawn('source', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
                str(run / 'sim01b_source.launch'), 'run_id:=' + run_id,
                'config:=' + str(run / state_path.name), 'audit_path:=' + str(source_audit)])
            manifest['source_spawn_monotonic_ns'] = time.monotonic_ns()
            manifest['source_start_monotonic_ns'] = _wait_node(
                master, processes, '/state_clock', min(wall_deadline, time.monotonic() + 10.),
                allowed=('checker', 'driver'))
            ready = [Path(str(source_audit) + '.ready.json'), Path(str(sensor_audit) + '.ready.json')]
        else:
            ready = [Path(str(sensor_audit) + '.ready.json')]
        _wait_files(ready, processes, min(wall_deadline, time.monotonic() + 10.),
                    allowed=('checker', 'driver'))
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise RuntimeError('本会话Python后代未全部使用指定Conda')
        manifest['phase'] = 'OBSERVING'
        write_json(run / 'manifest.json', manifest)

        checker = processes.children['checker']
        trigger_path = run / 'supervisor-trigger.json'
        while time.monotonic() < wall_deadline:
            processes.check(allowed=('checker', 'driver'))
            driver = processes.children.get('driver')
            if driver is not None and driver.poll() not in (None, 0):
                raise RuntimeError('MAVLink故障driver失败：' + str(driver.returncode))
            # checker先以独占文件封存业务触发，再退出。监督器直接观察该文件即可在
            # F6 ERROR后立即进入清理，不把Python进程退出延迟计入0.5秒门槛。
            if trigger_path.exists():
                trigger = read_json(trigger_path)
                if not _trigger_is_valid(trigger, scenario, run_id):
                    raise RuntimeError('supervisor-trigger身份或状态无效')
                if driver is not None:
                    _wait_successful_child(
                        processes, 'driver',
                        min(wall_deadline, time.monotonic() + cleanup_timeout),
                        allowed=('checker',))
                    if not (run / 'driver-result.json').exists():
                        raise RuntimeError('checker收尾时driver注入台账尚未完整')
                    driver_result = read_json(run / 'driver-result.json')
                    if driver_result.get('passed') is not True:
                        raise RuntimeError('driver注入计划未完整')
                    manifest['driver_exit'] = driver.returncode
                manifest['supervisor_trigger'] = trigger
                manifest['cleanup_start_monotonic_ns'] = time.monotonic_ns()
                online_passed = True
                break
            if checker.poll() is not None:
                manifest['checker_exit'] = checker.returncode
                if checker.returncode:
                    raise RuntimeError('在线checker未完整观察到预期事件')
                raise RuntimeError('checker成功退出但缺少supervisor-trigger')
            time.sleep(.02)
        else:
            raise RuntimeError('场景墙钟安全截止：' + scenario)
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
        if 'cleanup_start_monotonic_ns' not in manifest:
            manifest['cleanup_start_monotonic_ns'] = time.monotonic_ns()
    finally:
        manifest['phase'] = 'CLEANING'
        write_json(run / 'manifest.json', manifest)
        if processes is not None:
            for name in ('source', 'sensors'):
                try:
                    _stop_if_running(processes, name, cleanup_timeout)
                except (RuntimeError, ProcessLookupError) as exc:
                    manifest['errors'].append('cleanup: ' + str(exc))
            cleanup = processes.cleanup()
            checker = processes.children.get('checker')
            if checker is not None:
                manifest['checker_exit'] = checker.poll()
                if online_passed and checker.returncode != 0:
                    manifest['errors'].append(
                        'checker封存触发后未正常退出：' + str(checker.returncode))
        cleanup['start_monotonic_ns'] = manifest.get('cleanup_start_monotonic_ns')
        cleanup['ports'] = probe_ports('B1', port)
        cleanup['passed'] = (cleanup.get('passed', False) and
                             all(item['free'] for item in cleanup['ports']))
        write_json(run / 'cleanup-audit.json', cleanup)
        if not cleanup['passed']:
            manifest['errors'].append('本次进程/ROS Master端口清理未通过')
        manifest['phase'] = 'FINALIZING'
        write_json(run / 'manifest.json', manifest)
        if checker_started and env is not None:
            try:
                _run_offline_checker(root, run, run_id, scenario, config_path, previous_run, env, manifest)
                offline_passed = True
            except Exception as exc:
                manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
        passed = online_passed and offline_passed and cleanup['passed'] and not manifest['errors']
        manifest.update(phase='COMPLETE' if passed else 'FAILED', exit=0 if passed else 1,
                        wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
    return manifest


class SpeedObservation:
    """倍速子进程的轻量ROS观察器；不将预期倍率RED冒充为基础设施失败。"""
    def __init__(self, run, run_id, factor, warmup_ns, span_ns, source_limit_ns, tolerance):
        import rospy
        from diagnostic_msgs.msg import DiagnosticArray
        from mavros_msgs.msg import Mavlink
        from rosgraph_msgs.msg import Clock
        from uav_fusionmap_msgs.msg import AircraftState
        self.rospy = rospy
        self.run, self.run_id = run, run_id
        self.factor, self.warmup_ns, self.span_ns = factor, warmup_ns, span_ns
        self.source_limit_ns, self.tolerance = source_limit_ns, tolerance
        self.lock = threading.RLock()
        self.events = (run / 'speed-observations.jsonl').open('x')
        self.event_seq = 0
        self.errors, self.clocks, self.source, self.adapted = [], [], [], []
        self.raw_counts, self.raw_odom_times = collections.Counter(), set()
        self.armed = False
        self.strict_clock_increase = True
        self.terminal_count = 0
        self.node_pythons = {}
        self.complete = threading.Event()
        self.subscribers = [
            rospy.Subscriber('/clock', Clock, self.clock, queue_size=1000),
            rospy.Subscriber('/uav/sim/state', AircraftState, self.state, 'source', queue_size=1000),
            rospy.Subscriber('/uav/sensors/state', AircraftState, self.state, 'adapted', queue_size=1000),
            rospy.Subscriber('/mavlink/from', Mavlink, self.raw, queue_size=10000),
            rospy.Subscriber('/uav/diagnostics', DiagnosticArray, self.diagnostic, queue_size=1000),
        ]

    def record(self, event, **values):
        self.event_seq += 1
        self.events.write(json.dumps(dict(event_seq=self.event_seq,
            receipt_monotonic_ns=time.monotonic_ns(), event=event, **values), separators=(',', ':')) + '\n')
        # 0.5被bridge截断为0时会自由运行；批量刷新避免观察器I/O反过来主导测量。
        if self.event_seq % 100 == 0:
            self.events.flush()

    def clock(self, message):
        with self.lock:
            stamp = message.clock.to_nsec()
            receipt = time.monotonic_ns()
            if self.clocks and stamp <= self.clocks[-1][0]:
                self.strict_clock_increase = False
                self.errors.append('clock不严格递增')
            if stamp >= self.source_limit_ns:
                self.errors.append('clock达到倍速测量源时间安全上限')
            self.clocks.append((stamp, receipt))
            self.record('clock', timestamp_ns=stamp)
            self.maybe_complete()

    def state(self, message, channel):
        from ufm_ros_contract import from_ros_state
        with self.lock:
            receipt = time.monotonic_ns()
            state = from_ros_state(message)
            header = state['header']
            self.record('state', channel=channel, timestamp_ns=header['timestamp'],
                        sample_id=header['sample_id'], status=header['status'], reason=header['reason'])
            if header['run_id'] != self.run_id or header['clock_id'] != 'sim:' + self.run_id:
                self.errors.append(channel + '状态时钟域不符')
            if header['status'] != 'valid':
                self.terminal_count += 1
                self.errors.append(channel + '出现terminal：' + header['reason'])
                self.complete.set()
            target = self.source if channel == 'source' else self.adapted
            if target and header['timestamp'] <= target[-1]['timestamp']:
                self.errors.append(channel + '状态时间不递增')
            target.append(dict(timestamp=header['timestamp'], sample_id=header['sample_id'],
                               status=header['status'], receipt_monotonic_ns=receipt))
            self.maybe_complete()

    def raw(self, message):
        from mavros.mavlink import convert_to_bytes
        from pymavlink.dialects.v20 import common
        with self.lock:
            wire = convert_to_bytes(message)
            self.record('mavlink', msgid=message.msgid, sysid=message.sysid,
                        compid=message.compid, wire_hex=wire.hex())
            if message.framing_status != 1:
                self.errors.append('MAVLink framing错误')
                return
            if (message.sysid, message.compid) != (1, 1):
                return
            self.raw_counts[str(message.msgid)] += 1
            decoded = common.MAVLink(None).decode(wire)
            if message.msgid == 0 and decoded.base_mode & 128:
                self.armed = True
                self.errors.append('倍速测量中出现解锁心跳')
            elif message.msgid == 331:
                self.raw_odom_times.add(int(decoded.time_usec) * 1000)

    def diagnostic(self, message):
        with self.lock:
            for item in message.status:
                values = {value.key: value.value for value in item.values}
                self.record('diagnostic', name=item.name, level=item.level,
                            message=item.message, values=values)
                if 'python' in values:
                    self.node_pythons[item.name] = values['python']
                if item.level >= 2:
                    self.errors.append('ERROR诊断：%s:%s' % (item.name, item.message))
                    self.complete.set()
                elif item.level == 1 and (item.name, item.message) not in (
                        ('simulation/state_clock', 'timeline:PREPARING'),
                        ('simulation/state_clock', 'preparing_estimator_reset')):
                    self.errors.append('非预期WARN诊断：%s:%s' % (item.name, item.message))

    def endpoints(self):
        valid_source = [item for item in self.source if item['status'] == 'valid']
        if not valid_source:
            return None
        first_valid_source_ns = valid_source[0]['timestamp']
        warmup_target_ns = first_valid_source_ns + self.warmup_ns
        candidates = [item for item in self.clocks if item[0] >= warmup_target_ns]
        if not candidates:
            return None
        c0 = candidates[0]
        c1 = next((item for item in candidates if item[0] >= c0[0] + self.span_ns), None)
        return (c0, c1) if c1 else None

    def maybe_complete(self):
        if self.endpoints() is not None:
            self.complete.set()

    def evidence_ready(self):
        """共同窗口固定后等待独立ROS回调追平，不延长测量窗口。"""
        with self.lock:
            endpoints = self.endpoints()
            if endpoints is None:
                return False
            c0, c1 = endpoints[0][0], endpoints[1][0]
            source = [item for item in self.source
                      if item['status'] == 'valid' and c0 <= item['timestamp'] <= c1]
            adapted = [item for item in self.adapted
                       if item['status'] == 'valid' and c0 <= item['timestamp'] <= c1]
            source_ids = [item['sample_id'] for item in source]
            prefix = 'sensors.state:'
            adapted_ids = [item['sample_id'][len(prefix):]
                           for item in adapted if item['sample_id'].startswith(prefix)]
            timestamps = {item['timestamp'] for item in source}
            return bool(source_ids) and source_ids == adapted_ids and \
                bool(timestamps & self.raw_odom_times)

    def finish(self, wall_seconds):
        with self.lock:
            endpoints = self.endpoints()
            actual = None
            if endpoints is not None:
                (c0, r0), (c1, r1) = endpoints
                if r1 > r0:
                    actual = float(c1 - c0) / float(r1 - r0)
                else:
                    self.errors.append('倍速窗口单调receipt无效')
            c0 = endpoints[0][0] if endpoints else None
            c1 = endpoints[1][0] if endpoints else None
            window_source = [item for item in self.source if endpoints and
                             item['status'] == 'valid' and c0 <= item['timestamp'] <= c1]
            window_adapted = [item for item in self.adapted if endpoints and
                              item['status'] == 'valid' and c0 <= item['timestamp'] <= c1]
            source_ids = [item['sample_id'] for item in window_source]
            prefix = 'sensors.state:'
            adapted_ids = [item['sample_id'][len(prefix):] for item in window_adapted
                           if item['sample_id'].startswith(prefix)]
            identity_complete = bool(source_ids) and source_ids == adapted_ids and \
                len(adapted_ids) == len(window_adapted)
            if not identity_complete:
                self.errors.append('共同窗口源/适配sample_id未一一对应')
            # /mavlink/from与/uav/sim/state是两个独立ROS回调；旧init01 bridge曾因0.5->0
            # 自由运行，不能用“raw回调必须先到”证明未改写。源sample_id冻结了真实
            # ODOMETRY time_usec，逐项核对它与timestamp，并要求原始MAVLink集合有交集。
            rewritten = []
            source_timestamps = set()
            for item in window_source:
                source_timestamps.add(item['timestamp'])
                try:
                    time_usec = int(item['sample_id'].rsplit(':', 1)[1])
                except (IndexError, ValueError):
                    rewritten.append(item['timestamp'])
                    continue
                if not item['sample_id'].startswith('sim.odometry:') or \
                        time_usec * 1000 != item['timestamp']:
                    rewritten.append(item['timestamp'])
            raw_odometry_matches = len(source_timestamps & self.raw_odom_times)
            if rewritten:
                self.errors.append('源状态timestamp与ODOMETRY sample_id time_usec不符')
            if not raw_odometry_matches:
                self.errors.append('源状态与真实MAVLink ODOMETRY没有共同timestamp证据')
            expected_python = '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python'
            if len(self.node_pythons) != 2 or any(value != expected_python
                                                  for value in self.node_pythons.values()):
                self.errors.append('两个ROS节点Conda解释器证据不完整')
            if not self.source or not self.adapted or not self.raw_counts.get('0'):
                self.errors.append('倍速测量链路数据不完整')
            clock_window = [item for item in self.clocks if endpoints and c0 <= item[0] <= c1]
            source_sim_intervals = [right['timestamp'] - left['timestamp']
                                    for left, right in zip(window_source, window_source[1:])]
            source_wall_intervals = [right['receipt_monotonic_ns'] - left['receipt_monotonic_ns']
                                     for left, right in zip(window_source, window_source[1:])]
            wall_span = endpoints[1][1] - endpoints[0][1] if endpoints else 0
            source_span = endpoints[1][0] - endpoints[0][0] if endpoints else 0
            clock_wall_hz = ((len(clock_window) - 1) * 1e9 / wall_span
                             if len(clock_window) > 1 and wall_span > 0 else None)
            source_wall_hz = ((len(window_source) - 1) * 1e9 /
                              (window_source[-1]['receipt_monotonic_ns'] -
                               window_source[0]['receipt_monotonic_ns'])
                              if len(window_source) > 1 and
                              window_source[-1]['receipt_monotonic_ns'] >
                              window_source[0]['receipt_monotonic_ns'] else None)
            source_sim_hz = ((len(window_source) - 1) * 1e9 /
                             (window_source[-1]['timestamp'] - window_source[0]['timestamp'])
                             if len(window_source) > 1 and
                             window_source[-1]['timestamp'] > window_source[0]['timestamp'] else None)
            factor_passed = actual is not None and abs(actual - self.factor) <= self.factor * self.tolerance
            measurement = dict(
                first_clock_ns=endpoints[0][0] if endpoints else None,
                last_clock_ns=endpoints[1][0] if endpoints else None,
                first_monotonic_ns=endpoints[0][1] if endpoints else None,
                last_monotonic_ns=endpoints[1][1] if endpoints else None,
                actual_factor=actual,
                strict_clock_increase=self.strict_clock_increase,
                source_timestamp_rewritten=bool(rewritten),
                terminal_count=self.terminal_count,
                static_unarmed=bool(self.raw_counts.get('0')) and not self.armed,
            )
            result = dict(schema_version='0.1', run_id=self.run_id,
                          measurement_complete=endpoints is not None, requested_factor=self.factor,
                          actual_factor=actual, factor_passed=factor_passed,
                          allowed_factor=[self.factor * (1. - self.tolerance),
                                          self.factor * (1. + self.tolerance)],
                          endpoints=(dict(
                                          first_valid_source_ns=next(
                                              item['timestamp'] for item in self.source
                                              if item['status'] == 'valid'),
                                          warmup_target_ns=next(
                                              item['timestamp'] for item in self.source
                                              if item['status'] == 'valid') + self.warmup_ns,
                                          selection_rule=SELECTION_RULE,
                                          c0_ns=endpoints[0][0], c0_receipt_monotonic_ns=endpoints[0][1],
                                          c1_ns=endpoints[1][0], c1_receipt_monotonic_ns=endpoints[1][1])
                                     if endpoints else None),
                          selection_rule=SELECTION_RULE,
                          warmup_source_span_ns=self.warmup_ns,
                          source_states=len(self.source), adapted_states=len(self.adapted),
                          measurement_source_states=len(window_source),
                          measurement_adapted_states=len(window_adapted),
                          window_identity_complete=identity_complete,
                          timestamp_identity_basis=(
                              'measurement_window_sample_id_time_usec_with_raw_overlap'),
                          clocks=len(self.clocks), raw_counts=dict(self.raw_counts), armed=self.armed,
                          raw_odometry_timestamp_matches=raw_odometry_matches,
                          strict_clock_increase=self.strict_clock_increase,
                          terminal_count=self.terminal_count,
                          static_unarmed=bool(self.raw_counts.get('0')) and not self.armed,
                          measurement_clock_samples=len(clock_window),
                          measurement_source_span_ns=source_span,
                          measurement_wall_span_ns=wall_span,
                          clock_receipt_hz=clock_wall_hz,
                          source_receipt_hz=source_wall_hz,
                          source_sim_time_hz=source_sim_hz,
                          max_source_interval_ns=max(source_sim_intervals)
                          if source_sim_intervals else None,
                          max_source_receipt_interval_ns=max(source_wall_intervals)
                          if source_wall_intervals else None,
                          cpu_environment=cpu_environment(),
                          observer_process_resources=process_resource_evidence(os.getpid()),
                          timestamp_rewrite_detected=bool(rewritten), node_pythons=self.node_pythons,
                          observer_python=sys.executable, wall_seconds=wall_seconds,
                          errors=list(dict.fromkeys(self.errors)))
            result['passed'] = result['measurement_complete'] and factor_passed and not result['errors']
            write_json(self.run / 'speed-measurement.json', measurement)
            self.events.close()
            return result

    def close(self):
        for subscriber in self.subscribers:
            subscriber.unregister()
        # unregister后等待已进入回调的线程离开临界区，再由finish封存事件文件。
        with self.lock:
            pass


def speed_observer_main(argv):
    parser = argparse.ArgumentParser(description='SIM-01C内部倍速观察子进程')
    parser.add_argument('run')
    parser.add_argument('run_id')
    parser.add_argument('factor', type=float)
    parser.add_argument('warmup_ns', type=int)
    parser.add_argument('span_ns', type=int)
    parser.add_argument('source_limit_ns', type=int)
    parser.add_argument('tolerance', type=float)
    parser.add_argument('wall_cutoff_s', type=float)
    args = parser.parse_args(argv)
    import rospy
    run = Path(args.run)
    rospy.init_node('sim01c_speed_observer', disable_signals=True)
    observation = SpeedObservation(run, args.run_id, args.factor, args.warmup_ns, args.span_ns,
                                   args.source_limit_ns, args.tolerance)
    started = time.monotonic()
    try:
        observation.complete.wait(args.wall_cutoff_s)
        if observation.complete.is_set():
            drain_deadline = min(started + args.wall_cutoff_s, time.monotonic() + 1.)
            while time.monotonic() < drain_deadline and not observation.evidence_ready():
                time.sleep(.02)
    finally:
        observation.close()
        result = observation.finish(time.monotonic() - started)
        write_json(run / 'speed-result.json', result)
        print(json.dumps(result), flush=True)
        rospy.signal_shutdown('SIM-01C speed measurement complete')
    # 倍率RED由监督器保存；只有未完成测量或链路错误才是观察进程失败。
    infrastructure_ok = result['measurement_complete'] and not result['errors']
    return 0 if infrastructure_ok else 1


def run_speed_scenario(root, suite, suite_id, scenario, config_path, state_path, values,
                       bridge_binary, bridge_identity, tool_identity, config_identity,
                       frozen_boot_id, matrix_entry=None):
    speed = values['speed_smoke']
    case_key = SPEED_CASES[scenario]
    settings = speed['cases'][case_key]
    factor = float(settings['requested_factor'])
    suffix = 'm%02d' % matrix_entry['global_index'] if matrix_entry else None
    run, run_id = create_run(suite, suite_id, scenario, suffix)
    _copy_inputs(root, run, config_path, state_path, speed=True)
    port = int(settings['master_port'])
    started = time.monotonic()
    wall_deadline = started + float(settings['wall_safety_cutoff_s'])
    cleanup_timeout = float(values['safety']['cleanup_timeout_s'])
    factor_env = {'PX4_SIM_SPEED_FACTOR': str(settings['requested_factor'])}
    manifest = dict(schema_version='0.1', suite_run_id=suite_id, scenario=scenario,
                    run_id=run_id, run=str(run), python=sys.executable, supervisor_pid=os.getpid(),
                    ros_master_uri='http://127.0.0.1:' + str(port), requested_factor=factor,
                    warmup_source_span_ns=int(speed['warmup_source_span_ns']),
                    measurement_source_span_ns=int(speed['measurement_min_source_span_ns']),
                    selection_rule=SELECTION_RULE,
                    bridge_binary=bridge_identity, tool_identity=tool_identity,
                    config_identity=config_identity, boot_id=frozen_boot_id,
                    speed_matrix=matrix_entry,
                    commands=[], errors=[], acceptance_failures=[], armed_commands=False, phase='PREPARING',
                    px4_commit='1c8ab2a0d7db2d14a6f320ebd8766b5ffaea28fa',
                    bridge_commit='68de2cc63ded9a0d6641d45e9eb3ed2b43454cba', patch='SIM00B-INIT-01')
    if matrix_entry:
        manifest.update(matrix_id=matrix_entry['matrix_id'],
                        matrix_index=matrix_entry['global_index'],
                        matrix_label='%s%d' % (matrix_entry['batch'], matrix_entry['batch_index']))
    processes = None
    result = None
    offline_checked = False
    env = None
    cleanup = dict(passed=False, children=[], forced=[], remaining_audited_python_pids=[], ports=[])
    try:
        if file_identity(bridge_binary) != bridge_identity:
            raise RuntimeError('bridge候选身份在本run启动前漂移')
        if file_identity(Path(__file__)) != tool_identity:
            raise RuntimeError('倍速运行工具身份在本run启动前漂移')
        if file_identity(config_path) != config_identity:
            raise RuntimeError('冻结场景配置身份在本run启动前漂移')
        if boot_id() != frozen_boot_id:
            raise RuntimeError('主机启动周期在九次矩阵期间发生变化')
        manifest['host_resource_environment_start'] = host_resource_evidence()
        manifest['ports_before'] = probe_ports('LIVE', port)
        if any(not item['free'] for item in manifest['ports_before']):
            raise RuntimeError('倍速会话所需端口被占用，保留既有进程')
        reject_existing_px4()
        env = configure_environment(run, port)
        processes = Processes(run, env, manifest)
        install_interrupt_handler()
        master = start_master(processes, port, min(wall_deadline, time.monotonic() + 10.))
        observer_command = [sys.executable, str(Path(__file__).resolve()), '--speed-observer',
            str(run), run_id, str(factor), str(int(speed['warmup_source_span_ns'])),
            str(int(speed['measurement_min_source_span_ns'])),
            str(int(speed['source_safety_limit_ns'])), str(float(speed['tolerance_fraction'])),
            str(float(settings['wall_safety_cutoff_s']))]
        processes.spawn('speed-observer', observer_command)
        source_audit, sensor_audit = run / 'source-audit.jsonl', run / 'sensor-audit.jsonl'
        processes.spawn('sensors', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
            str(run / 'sim01b_sensors.launch'), 'run_id:=' + run_id,
            'config:=' + str(run / state_path.name), 'audit_path:=' + str(sensor_audit)])
        processes.spawn('source', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
            str(run / 'sim01b_source.launch'), 'run_id:=' + run_id,
            'config:=' + str(run / state_path.name), 'audit_path:=' + str(source_audit)])
        _wait_node(master, processes, '/state_clock', min(wall_deadline, time.monotonic() + 10.),
                   allowed=('speed-observer',))
        _wait_files([Path(str(source_audit) + '.ready.json'),
                     Path(str(sensor_audit) + '.ready.json')], processes,
                    min(wall_deadline, time.monotonic() + 10.), allowed=('speed-observer',))
        runtime = root / '.runtime'
        processes.spawn('bridge', [str(bridge_binary),
            'rascal', '-s', str(runtime / 'src/px4-v1.13.3/Tools/jsbsim_bridge/scene/LSZH.xml')],
            extra_env=factor_env)
        bridge_deadline = min(wall_deadline, time.monotonic() + 10.)
        while time.monotonic() < bridge_deadline:
            processes.check(allowed=('speed-observer',))
            if not probe_ports('LIVE', port)[1]['free']:
                break
            time.sleep(.05)
        else:
            raise RuntimeError('bridge TCP监听启动超时')
        processes.spawn('px4', [str(runtime / 'build/px4-v1.13.3/bin/px4'), '-d',
            str(runtime / 'build/px4-v1.13.3/etc'), '-s', 'etc/init.d-posix/rcS'],
            run / 'rootfs', extra_env=factor_env)
        processes.spawn('mavros', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
            str(run / 'sim00b_mavros.launch')])
        configured = False
        observer = processes.children['speed-observer']
        while time.monotonic() < wall_deadline:
            processes.check(allowed=('speed-observer',))
            if not configured and 'Startup script returned successfully' in \
                    (run / 'px4.log').read_text(errors='replace'):
                for stream, rate in (('HIGHRES_IMU', '50'), ('ODOMETRY', '20')):
                    command = [str(runtime / 'build/px4-v1.13.3/bin/px4-mavlink'), 'stream',
                               '-u', '14580', '-s', stream, '-r', rate]
                    with (run / ('stream-' + stream + '.log')).open('x') as output:
                        completed = subprocess.run(command, cwd=run / 'rootfs', env=env,
                            stdout=output, stderr=subprocess.STDOUT, timeout=5.)
                    manifest['commands'].append(dict(name='stream-' + stream,
                                                     args=command, exit=completed.returncode))
                    if completed.returncode:
                        raise RuntimeError('遥测流配置失败：' + stream)
                configured = True
                manifest['python_process_audit'] = python_process_audit()
                if not manifest['python_process_audit']['passed']:
                    raise RuntimeError('倍速会话Python后代未全部使用指定Conda')
                manifest['streams_configured'] = True
                manifest['phase'] = 'MEASURING'
            if observer.poll() is not None:
                manifest['observer_exit'] = observer.returncode
                if observer.returncode:
                    raise RuntimeError('倍速观察链未完成：' + str(observer.returncode))
                if not configured or manifest.get('streams_configured') is not True:
                    raise RuntimeError('观察器结束前PX4遥测流未完成配置')
                if manifest.get('python_process_audit', {}).get('passed') is not True:
                    raise RuntimeError('观察器结束前Conda后代审计未通过')
                result = read_json(run / 'speed-result.json')
                if result.get('measurement_complete') is not True:
                    raise RuntimeError('倍速观察进程未完成共同窗口')
                manifest['measurement_complete'] = True
                manifest['actual_factor'] = result.get('actual_factor')
                manifest['factor_passed'] = result.get('factor_passed')
                manifest['host_resource_environment_end'] = host_resource_evidence()
                manifest['process_resource_evidence'] = managed_process_resources(processes)
                if result.get('factor_passed') is not True:
                    manifest['acceptance_failures'].append('实际倍率不在目标±15%范围')
                manifest['cleanup_start_monotonic_ns'] = time.monotonic_ns()
                break
            time.sleep(.05)
        else:
            raise RuntimeError('倍速会话墙钟安全截止')
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
        manifest.setdefault('cleanup_start_monotonic_ns', time.monotonic_ns())
    finally:
        if 'host_resource_environment_end' not in manifest:
            manifest['host_resource_environment_end'] = host_resource_evidence()
        if 'process_resource_evidence' not in manifest:
            manifest['process_resource_evidence'] = managed_process_resources(processes)
        for identity_name, path, frozen in (
                ('bridge候选', bridge_binary, bridge_identity),
                ('倍速运行工具', Path(__file__), tool_identity),
                ('冻结场景配置', config_path, config_identity)):
            try:
                if file_identity(path) != frozen:
                    manifest['errors'].append(identity_name + '身份在本run期间漂移')
            except (OSError, RuntimeError) as exc:
                manifest['errors'].append(identity_name + '身份复核失败：' + str(exc))
        try:
            if boot_id() != frozen_boot_id:
                manifest['errors'].append('主机启动周期在本run期间发生变化')
        except RuntimeError as exc:
            manifest['errors'].append(str(exc))
        manifest['phase'] = 'CLEANING'
        write_json(run / 'manifest.json', manifest)
        if processes is not None:
            for name in ('source', 'sensors', 'mavros', 'px4', 'bridge'):
                try:
                    _stop_if_running(processes, name, cleanup_timeout)
                except (RuntimeError, ProcessLookupError) as exc:
                    manifest['errors'].append('cleanup: ' + str(exc))
            cleanup = processes.cleanup()
        cleanup['start_monotonic_ns'] = manifest.get('cleanup_start_monotonic_ns')
        cleanup['ports'] = probe_ports('LIVE', port)
        cleanup['passed'] = cleanup.get('passed', False) and all(item['free'] for item in cleanup['ports'])
        write_json(run / 'cleanup-audit.json', cleanup)
        if not cleanup['passed']:
            manifest['errors'].append('倍速会话进程/端口清理未通过')
        # 离线checker必须读取包含stream、Conda审计、进程退出和清理错误的最新manifest。
        write_json(run / 'manifest.json', manifest)
        if result is not None and env is not None:
            try:
                manifest['offline_validation'] = _run_speed_checker(
                    root, run, run_id, case_key, config_path, env, manifest,
                    result.get('factor_passed') is True)
                offline_checked = True
            except Exception as exc:
                manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
        passed = (bool(result and result.get('passed')) and offline_checked and
                  cleanup['passed'] and not manifest['errors'])
        red = bool(result and result.get('measurement_complete') and not result.get('factor_passed')
                   and not result.get('errors') and offline_checked and cleanup['passed'] and
                   not manifest['errors'])
        manifest.update(phase='COMPLETE' if passed else 'RED' if red else 'FAILED',
                        exit=0 if passed else 1, wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
    return manifest


def parse_selection(values):
    selected = []
    for value in values or ['ALL']:
        scenario = canonical_scenario(value)
        choices = DEFAULT_ORDER if scenario == 'ALL' else (scenario,)
        for choice in choices:
            if choice not in selected:
                selected.append(choice)
    # 普通ALL保持SIM-01C既有2倍、0.5倍顺序，并在其后增加1倍控制组。
    if 'SPEED_2' in selected and 'SPEED_05' in selected:
        selected = [item for item in selected if item not in SPEED_SCENARIOS] + list(SPEED_SCENARIOS)
    return selected


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == '--speed-observer':
        return speed_observer_main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', help='SIM-01C冻结场景配置')
    parser.add_argument('--scenario', action='append',
                        help='F0..F7、SPEED_2、SPEED_05、SPEED_1或all；可重复')
    parser.add_argument('--previous-run', help='单独执行F7时显式指定F3 run目录')
    parser.add_argument('--speed-matrix', action='store_true',
                        help='一次执行预注册的SIM-SPEED-01固定九run矩阵')
    parser.add_argument('--bridge-binary',
                        help='显式bridge可执行文件；默认仍使用既有init01二进制')
    args = parser.parse_args(argv)
    if args.speed_matrix and args.scenario:
        parser.error('--speed-matrix不能与--scenario组合，矩阵顺序由冻结配置唯一决定')
    if args.speed_matrix and args.previous_run:
        parser.error('--speed-matrix不接受故障场景的--previous-run')
    root = Path(__file__).resolve().parents[1]
    config_path, state_path, values = load_config(root, args.config)
    matrix_id = None
    planned_runs = []
    if args.speed_matrix:
        matrix_id = 'sim-speed01-matrix-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
        for item in values['speed_smoke']['matrix']['planned_runs']:
            planned_runs.append(dict(matrix_id=matrix_id,
                                     global_index=int(item['global_index']), batch=item['batch'],
                                     batch_index=int(item['batch_index']), scenario=item['scenario'],
                                     requested_factor=float(item['requested_factor'])))
        selection = [item['scenario'] for item in planned_runs]
    else:
        selection = parse_selection(args.scenario)
    needs_speed = args.speed_matrix or any(item in SPEED_SCENARIOS for item in selection)
    bridge_path = None
    if needs_speed:
        bridge_path = Path(args.bridge_binary or
                           root / '.runtime/build/jsbsim-bridge-init01/jsbsim_bridge').resolve(strict=True)
        if not bridge_path.is_file() or not os.access(str(bridge_path), os.X_OK):
            raise RuntimeError('bridge二进制不存在或不可执行：' + str(bridge_path))
    bridge_identity = file_identity(bridge_path) if needs_speed else None
    tool_identity = file_identity(Path(__file__)) if needs_speed else None
    config_identity = file_identity(config_path) if needs_speed else None
    frozen_boot_id = boot_id() if needs_speed else None
    suite, suite_id = create_suite(root)
    suite_manifest = dict(schema_version='0.1', suite_run_id=suite_id, suite=str(suite),
                          python=sys.executable, config=str(config_path), scenarios=selection,
                          results=[], errors=[], phase='RUNNING', started_monotonic_ns=time.monotonic_ns())
    if needs_speed:
        suite_manifest.update(bridge_binary=bridge_identity, tool_identity=tool_identity,
                              config_identity=config_identity, boot_id=frozen_boot_id,
                              host_resource_environment=host_resource_evidence())
    matrix_manifest = None
    if args.speed_matrix:
        matrix_path = suite / 'speed-matrix-manifest.json'
        suite_manifest.update(matrix_id=matrix_id, speed_matrix_plan=planned_runs)
        suite_manifest['speed_matrix'] = dict(matrix_id=matrix_id, manifest=str(matrix_path),
                                              planned_runs=planned_runs)
        matrix_manifest = dict(schema_version='0.1', matrix_id=matrix_id,
                               suite_run_id=suite_id, suite=str(suite), planned_runs=planned_runs,
                               actual_runs=[], candidate_binary=bridge_identity,
                               tool_identity=tool_identity, config_identity=config_identity,
                               boot_id=frozen_boot_id, errors=[], phase='RUNNING', exit=None,
                               started_monotonic_ns=time.monotonic_ns())
        write_json(matrix_path, matrix_manifest)
    write_json(suite / 'suite-manifest.json', suite_manifest)
    f3_run = Path(args.previous_run).resolve() if args.previous_run else None
    execution = [(item['scenario'], item) for item in planned_runs] if args.speed_matrix else \
                [(scenario, None) for scenario in selection]
    for scenario, matrix_entry in execution:
        if scenario in FAULT_SCENARIOS:
            previous = f3_run if scenario == 'C-F7' else None
            result = run_fault_scenario(root, suite, suite_id, scenario, config_path,
                                        state_path, values, previous)
            if scenario == 'C-F3':
                f3_run = Path(result['run'])
        else:
            result = run_speed_scenario(root, suite, suite_id, scenario, config_path,
                                        state_path, values, bridge_path, bridge_identity,
                                        tool_identity, config_identity, frozen_boot_id, matrix_entry)
        suite_manifest['results'].append(dict(scenario=scenario, run=result['run'],
                                              run_id=result['run_id'], phase=result['phase'],
                                              exit=result['exit']))
        if matrix_manifest is not None:
            actual = dict(matrix_entry)
            actual.update(run=result['run'], run_id=result['run_id'], phase=result['phase'],
                          exit=result['exit'])
            matrix_manifest['actual_runs'].append(actual)
            if result['exit'] != 0:
                matrix_manifest['errors'].append(
                    'global_index=%d run未通过：%s' %
                    (matrix_entry['global_index'], result['phase']))
            write_json(suite / 'speed-matrix-manifest.json', matrix_manifest)
        write_json(suite / 'suite-manifest.json', suite_manifest)
    passed = all(item['exit'] == 0 for item in suite_manifest['results'])
    if matrix_manifest is not None:
        candidate_passed = passed and len(matrix_manifest['actual_runs']) == len(planned_runs) == 9
        matrix_manifest.update(phase='COMPLETE' if candidate_passed else 'INCOMPLETE',
                               exit=0 if candidate_passed else 1)
        write_json(suite / 'speed-matrix-manifest.json', matrix_manifest)
        # 整批checker读取候选封存态；最终状态只有在其独立复算通过后才保持COMPLETE。
        suite_manifest.update(phase='COMPLETE' if candidate_passed else 'INCOMPLETE',
                              exit=0 if candidate_passed else 1,
                              finished_monotonic_ns=time.monotonic_ns())
        write_json(suite / 'suite-manifest.json', suite_manifest)
        try:
            matrix_validation = _run_speed_matrix_checker(root, suite, matrix_id, config_path)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            matrix_validation = dict(command=None, exit=None, result={},
                                     error=type(exc).__name__ + ': ' + str(exc))
        matrix_manifest['offline_validation'] = matrix_validation
        matrix_passed = (candidate_passed and matrix_validation.get('exit') == 0 and
                         matrix_validation.get('result', {}).get('passed') is True)
        if not matrix_passed and not matrix_manifest['errors']:
            matrix_manifest['errors'].append('整批离线checker未通过')
        matrix_manifest.update(phase='COMPLETE' if matrix_passed else 'INCOMPLETE',
                               exit=0 if matrix_passed else 1,
                               finished_monotonic_ns=time.monotonic_ns())
        write_json(suite / 'speed-matrix-manifest.json', matrix_manifest)
        passed = matrix_passed
    suite_manifest.update(phase='COMPLETE' if passed else 'INCOMPLETE', exit=0 if passed else 1,
                          finished_monotonic_ns=time.monotonic_ns())
    write_json(suite / 'suite-manifest.json', suite_manifest)
    print(json.dumps(dict(suite=str(suite), exit=suite_manifest['exit'],
                          results=suite_manifest['results'])), flush=True)
    return suite_manifest['exit']


if __name__ == '__main__':
    sys.exit(main())
