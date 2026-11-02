"""Bounded Local Map query ROS fixture supervisor; use sim01_env.sh."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import sys
import time

from runtime_config import load_map_config, normalize_map_config

from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
                           probe_ports, python_process_audit, start_master, write_json)


def check_inference_fixture(run_id, processes):
    """只查询完成后的地图；采样期间没有业务/诊断观察订阅者。"""
    import rospy
    import xmlrpc.client
    from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
    from ufm_ros_contract.query_codec import from_ros_query_result
    deadline = time.monotonic() + 20.
    while rospy.get_param('/perf01a_source/done', '') != run_id:
        processes.check()
        if time.monotonic() >= deadline:
            raise RuntimeError('standalone inference source completion timeout')
        time.sleep(.02)
    expected = rospy.get_param('/perf01a_source/expected_samples')
    rospy.wait_for_service('/uav/map/query', timeout=3.)
    query = rospy.ServiceProxy('/uav/map/query', MapQuery)
    result = None
    while time.monotonic() < deadline:
        result = from_ros_query_result(query(MapQueryRequest(
            map_id='perf01a-local', frame_id='odom', run_id=run_id, clock_id='sim:' + run_id,
            query_timestamp=expected * 50_000_000, point=[.25, 4.25, .25],
            max_age_ns=100_000_000)).result)
        if result['revision'] == expected:
            break
        processes.check()
        time.sleep(.02)
    if (result['revision'] != expected or not result['observed'] or
            result['probability'] is None or abs(result['probability'] - .9) > 1e-6):
        raise RuntimeError('standalone inference map did not close: ' + str(result))
    master = xmlrpc.client.ServerProxy(os.environ['ROS_MASTER_URI'])
    graph = master.getSystemState('/inference_fixture_checker')
    if graph[0] != 1:
        raise RuntimeError('standalone inference graph unavailable')
    publishers, subscribers, _ = graph[2]
    if any(topic == '/uav/perf/events' or 'training' in topic.lower() or 'lidar' in topic.lower()
           for topic, nodes in publishers + subscribers):
        raise RuntimeError('diagnostic or training topics in standalone inference graph')
    configs = {role: normalize_map_config(rospy.get_param('/perf01a_' + role + '/resolved_map_config'))
               for role in ('perception', 'mapping')}
    if configs['perception'] != configs['mapping']:
        raise RuntimeError('perception/mapping resolved configuration differs')
    return dict(passed=True, run_id=run_id, expected=expected, query=result,
                resolved_map_config=configs, graph=graph[2], observer_subscriptions=False)


def start_delayed_mapping(processes, root, run_id, delay_s):
    """测试握手：sensor已连接、mapping尚不存在时，源不能发布首帧。"""
    import rospy
    deadline = time.monotonic() + 10.
    while rospy.get_param('/perf01a_sensor/ready', '') != run_id:
        processes.check()
        if time.monotonic() >= deadline:
            raise RuntimeError('sensor readiness timeout before delayed mapping')
        time.sleep(.02)
    started = time.monotonic()
    while time.monotonic() - started < delay_s:
        processes.check()
        if (rospy.has_param('/perf01a_source/expected_samples') or
                rospy.get_param('/perf01a_perception/ready', '') == run_id):
            raise RuntimeError('source/perception started without mapping business connection')
        time.sleep(.02)
    receipt = dict(delay_s=delay_s, observed_wait_s=time.monotonic() - started,
                   source_started_before_mapping=False, perception_ready_before_mapping=False)
    processes.spawn('delayed-mapping', [sys.executable,
        str(root / 'ros_ws/src/uav_fusionmap_mapping/scripts/perf01a_map_node.py'),
        '__name:=perf01a_mapping', '_run_id:=' + run_id, '_enable_query:=true'])
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=11451)
    parser.add_argument('--mode', choices=('enabled', 'disabled', 'unclassified', 'rolling', 'inference'),
                        default='enabled')
    parser.add_argument('--sample-resources', action='store_true',
                        help='optional fixture-only mapping RSS samples; not M1 acceptance')
    parser.add_argument('--application-client', action='store_true',
                        help='enabled query fixture only: validate public application consumer')
    parser.add_argument('--map-config', type=Path, help='shared inference map fixture configuration')
    parser.add_argument('--mapping-delay-s', type=float, default=0.,
                        help='inference only: test mandatory connection before starting mapping')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('port must be in [1024, 65535]')
    if args.application_client and args.mode != 'enabled':
        parser.error('--application-client requires --mode enabled')
    if not 0 <= args.mapping_delay_s <= 5 or (args.mode != 'inference' and
            (args.mapping_delay_s or args.map_config)):
        parser.error('map config/delay apply to inference; delay must be in [0,5] seconds')
    root = Path(__file__).resolve().parents[1]
    identity = 'local-map-query-' + args.mode + '-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / identity
    run.mkdir(parents=True, exist_ok=False)
    for name in ('ros-home', 'ros-logs'):
        (run / name).mkdir()
    env = configure_environment(run, args.port)
    manifest = dict(run_id=identity, mode=args.mode, python=sys.executable,
                    supervisor_pid=os.getpid(), commands=[], errors=[], armed_commands=False,
                    ros_master_uri=env['ROS_MASTER_URI'])
    processes = Processes(run, env, manifest)
    install_interrupt_handler()
    passed = False
    sampler = None
    started = time.monotonic()
    try:
        if args.mode == 'inference':
            config = args.map_config.resolve() if args.map_config else root / 'configs/local_map_fixture.yaml'
            manifest['resolved_map_config'] = load_map_config(config)
            shutil.copy2(config, run / 'map-config.yaml')
        manifest['ports_before'] = probe_ports('QUERY', args.port)
        if any(not row['free'] for row in manifest['ports_before']):
            raise RuntimeError('port occupied; existing process preserved')
        if args.sample_resources:
            from perf01a_resources import ResourceSampler
            sampler = ResourceSampler(interval_s=.1)
            sampler.start()
        launch = root / ('ros_ws/launch/inference_fixture.launch' if args.mode == 'inference' else
                         'ros_ws/launch/local_map_rolling_fixture.launch' if args.mode == 'rolling'
                         else 'ros_ws/launch/local_map_query_fixture.launch')
        shutil.copy2(launch, run / launch.name)
        start_master(processes, args.port, time.monotonic() + 15)
        if args.mode == 'inference':
            import rospy
            rospy.init_node('inference_fixture_checker', disable_signals=True)
        arguments = (['duration_s:=1', 'map_config:=' + str(run / 'map-config.yaml'),
                      'start_mapping:=' + str(not args.mapping_delay_s).lower()]
                     if args.mode == 'inference' else
                     ['enable_query:=' + str(args.mode != 'disabled').lower(),
                      'classify:=' + str(args.mode != 'unclassified').lower()])
        processes.spawn('mapping', [sys.executable, '/opt/ros/noetic/bin/roslaunch', str(run / launch.name),
                                   'run_id:=' + identity] + arguments)
        if args.mode == 'inference':
            if args.mapping_delay_s:
                manifest['delayed_mapping'] = start_delayed_mapping(
                    processes, root, identity, args.mapping_delay_s)
            validation = check_inference_fixture(identity, processes)
            write_json(run / 'validation.json', validation)
            passed = validation['passed']
            manifest['python_process_audit'] = python_process_audit()
            if not manifest['python_process_audit']['passed']:
                raise RuntimeError('Python environment audit failed')
        else:
            checker = ('check_local_map_rolling_ros.py' if args.mode == 'rolling'
                       else 'check_local_map_query_ros.py')
            observer_command = [sys.executable, str(root / 'tests' / checker),
                                str(run), identity, '--mode', args.mode]
            if args.application_client:
                observer_command.append('--application-client')
            observer = processes.spawn('observer', observer_command)
            deadline = started + 45
            while time.monotonic() < deadline:
                processes.check(allowed=('observer',))
                if 'python_process_audit' not in manifest and time.monotonic() - started >= 2:
                    manifest['python_process_audit'] = python_process_audit()
                    if not manifest['python_process_audit']['passed']:
                        raise RuntimeError('Python environment audit failed')
                if observer.poll() is not None:
                    if observer.returncode:
                        raise RuntimeError('query observer failed: ' + str(observer.returncode))
                    if 'python_process_audit' not in manifest:
                        manifest['python_process_audit'] = python_process_audit()
                        if not manifest['python_process_audit']['passed']:
                            raise RuntimeError('Python environment audit failed')
                    with (run / 'validation.json').open() as handle:
                        passed = json.load(handle)['passed']
                    break
                time.sleep(.02)
            else:
                raise RuntimeError('query fixture wall-clock safety limit')
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        if sampler is not None:
            try:
                from m1_resource_observer import mapping_resource_report
                sampler.stop()
                write_json(run / 'resources.json', mapping_resource_report(sampler.rows, sampler.errors))
            except Exception as exc:
                manifest['errors'].append('fixture resource sampling: %s: %s'
                                          % (type(exc).__name__, exc))
        cleanup = processes.cleanup()
        try:
            cleanup['ports'] = probe_ports('QUERY', args.port)
            cleanup['passed'] = cleanup['passed'] and all(row['free'] for row in cleanup['ports'])
        except OSError as exc:
            cleanup.update(ports=[], passed=False)
            manifest['errors'].append('port cleanup audit unavailable: ' + str(exc))
        write_json(run / 'cleanup-audit.json', cleanup)
        passed = passed and cleanup['passed'] and not manifest['errors']
        manifest.update(passed=passed, wall_seconds=time.monotonic() - started)
        write_json(run / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(run), passed=passed, cleanup=cleanup['passed'],
                              errors=manifest['errors'])), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
