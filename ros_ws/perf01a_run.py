"""PERF-01-A短时fixture统一运行器，先订阅、后发源、排空后停止。"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import xmlrpc.client
import yaml

from perf01a_metrics import PerfAggregator, resource_snapshot, percentile_set
from perf01a_validation import expected_sequences, validate_receipts
from perf01a_timing import expected_timing, timing_report
from perf01a_wire_report import wire_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration-s', type=float, default=8.)
    parser.add_argument('--port', type=int, default=11421)
    parser.add_argument('--scenario', default='small')
    parser.add_argument('--observer-mode', choices=('full', 'light', 'metadata'), default='full')
    parser.add_argument('--segmented-timing', action='store_true')
    parser.add_argument('--image-buff-size', type=int, default=65536)
    parser.add_argument('--wire-profile', action='store_true')
    parser.add_argument('--sample-resources', action='store_true')
    parser.add_argument('--receive-backend', choices=('standard', 'numpy'), default='standard')
    args = parser.parse_args()
    if not 0 < args.duration_s <= 60:
        parser.error('duration-s must be in (0, 60]')
    if args.image_buff_size <= 0:
        parser.error('image-buff-size must be positive')
    if args.observer_mode == 'metadata' and not args.wire_profile:
        parser.error('metadata observation requires --wire-profile for producer/consumer identity checks')
    if args.wire_profile:
        args.segmented_timing = True
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))
    root = Path(__file__).resolve().parents[1]
    with (root / 'configs/perf01_budget.yaml').open() as handle:
        budget = yaml.safe_load(handle)
    with (root / 'configs/perf01a_scenarios.yaml').open() as handle:
        profiles = yaml.safe_load(handle)['scenarios']
    if args.scenario not in profiles:
        parser.error('unknown scenario: ' + args.scenario)
    profile = profiles[args.scenario]
    frequency = budget['reference_sensors']['radar']['fixture_frequency_hz']
    if frequency != budget['reference_sensors']['infrared']['fixture_frequency_hz']:
        raise ValueError('paired fixture requires equal Radar/IR frequency')
    count = max(1, int(round(args.duration_s * frequency)))
    if profile['fault'] != 'none' and count <= profile['stop_sequence']:
        parser.error('fault scenario requires samples after the injection window')
    expected_by_topic = expected_sequences(count, profile)
    expected_counts = {key: len(value) for key, value in expected_by_topic.items()}
    unsubscribed = {'infrared', 'bundle'} if args.observer_mode == 'metadata' else set()
    rejected_count = count - expected_counts['map']
    run_id = 'perf01a-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    with (run / 'budget.json').open('x') as handle:
        json.dump(budget, handle, ensure_ascii=False, indent=2)
    with (run / 'scenario.json').open('x') as handle:
        json.dump(dict(name=args.scenario, profile=profile, expected_counts=expected_counts),
                  handle, ensure_ascii=False, indent=2)
    os.environ.update(ROS_MASTER_URI='http://127.0.0.1:%d' % args.port,
                      ROS_IP='127.0.0.1', ROS_HOME=str(run / 'ros-home'),
                      ROS_LOG_DIR=str(run / 'ros-logs'))
    processes, handles = [], []
    report = dict(run_id=run_id, passed=False, errors=[], python=sys.executable)
    report['fixture'] = dict(frequency_hz=frequency, radar_points=1, ir_resolution=profile['ir_resolution'],
                            radar_point_m=[4., 0., 0.], grid_shape=[64, 32, 16],
                            resolution_m=.5, origin_m=[-16., -8., -4.],
                            motion='stationary', resource_scope='observer process only')
    report.update(scenario=args.scenario, expected_rejections=rejected_count,
                  observer_mode=args.observer_mode, segmented_timing=args.segmented_timing,
                  image_buff_size=args.image_buff_size,
                  wire_profile=args.wire_profile, observer_unsubscribed=sorted(unsubscribed),
                  receive_backend=args.receive_backend,
                  pixel_validation=('all pixels min/max' if args.observer_mode == 'full' else 'not performed'),
                  timing_origin='fixture generation start captured before IR construction')
    timing_expected = expected_timing(count, profile, run_id)
    expected_event_count = 5 * expected_counts['map'] + 3 * rejected_count
    if args.segmented_timing:
        expected_event_count += sum(len(stages) for stages in timing_expected.values())
    aggregator = PerfAggregator(run_id)
    lock = threading.RLock()
    records = {key: [] for key in ('state', 'radar', 'infrared', 'bundle', 'occupancy', 'map')}
    start_resource = resource_snapshot()
    sampler = None
    observer_audit = None
    if args.sample_resources:
        from perf01a_resources import ResourceSampler
        sampler = ResourceSampler()
        report['fixture']['resource_scope'] = 'runner and its process tree; sampled CPU/RSS and host diagnostics'
        sampler.start()

    def spawn(name, command):
        handle = (run / (name + '.log')).open('x')
        handles.append(handle)
        process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes.append((name, process))
        return process

    def check_processes():
        for name, process in processes:
            if process.poll() is not None:
                raise RuntimeError('%s exited %s' % (name, process.returncode))

    try:
        spawn('master', [sys.executable, '/opt/ros/noetic/bin/rosmaster', '-p', str(args.port)])
        master = xmlrpc.client.ServerProxy(os.environ['ROS_MASTER_URI'])
        deadline = time.monotonic() + 15.
        while True:
            check_processes()
            try:
                if master.getPid('/perf01a_runner')[0] == 1:
                    break
            except OSError:
                pass
            if time.monotonic() > deadline:
                raise RuntimeError('master startup timeout')
            time.sleep(.05)
        import rospy
        from uav_fusionmap_msgs.msg import (AircraftState, RadarFrame, InfraredFrame,
                                          SensorBundle, OccupancyObservation, MapSnapshot, PerfEvent)
        rospy.set_param('/use_sim_time', True)
        rospy.init_node('perf01a_runner', disable_signals=True)
        rospy.set_param('/perf01a_sensor/scenario_profile', profile)
        rospy.set_param('/perf01a_segmented_timing', args.segmented_timing)
        rospy.set_param('/perf01a_image_buff_size', args.image_buff_size)
        rospy.set_param('/perf01a_observer_mode', args.observer_mode)
        rospy.set_param('/perf01a_receive_backend', args.receive_backend)
        rospy.set_param('/perf01a_wire_audit_directory', str(run) if args.wire_profile else '')
        if args.wire_profile:
            from ufm_ros_contract.perf01a_wire import WireAudit
            observer_audit = WireAudit(run / 'observer-wire.json')
            observer_audit.install(InfraredFrame, 'deserialize')
            observer_audit.install(SensorBundle, 'deserialize')

        def receive_event(msg):
            with lock:
                aggregator.record({key: getattr(msg, key) for key in msg.__slots__})

        def receive(msg, key):
            entered = time.monotonic_ns()
            with lock:
                acquired = time.monotonic_ns()
                row = dict(sample_id=msg.header.sample_id, timestamp=msg.header.timestamp,
                           run_id=msg.header.run_id, status=msg.header.status,
                           clock_id=msg.header.clock_id,
                           receive_monotonic_ns=entered, lock_wait_ns=acquired - entered)
                if key == 'map':
                    row.update(revision=msg.revision, cell_count=len(msg.cells),
                               cells=[dict(index=[c.x, c.y, c.z], probability=c.probability,
                                           observed=c.observed, timestamp=c.last_observed_timestamp)
                                      for c in msg.cells])
                if key == 'bundle':
                    row.update(radar_id=msg.radar.header.sample_id,
                               infrared_id=msg.infrared.header.sample_id,
                               radar_ir_delta_ns=msg.radar_ir_delta_ns, pose_age_ns=msg.pose_age_ns)
                if key in ('infrared', 'bundle'):
                    infrared = msg if key == 'infrared' else msg.infrared
                    row.update(image_shape=[infrared.width, infrared.height],
                               pixel_count=len(infrared.image))
                    if args.observer_mode == 'full':
                        row.update(pixel_min=min(infrared.image) if infrared.image else None,
                                   pixel_max=max(infrared.image) if infrared.image else None)
                row['callback_work_ns'] = time.monotonic_ns() - acquired
                records[key].append(row)

        subscribers = [rospy.Subscriber('/uav/perf/events', PerfEvent, receive_event, queue_size=2000)]
        for key, topic, kind in (
            ('state', '/uav/sim/state', AircraftState), ('radar', '/uav/sensors/radar', RadarFrame),
            ('infrared', '/uav/sensors/infrared', InfraredFrame), ('bundle', '/uav/sensors/bundle', SensorBundle),
            ('occupancy', '/uav/perception/occupancy', OccupancyObservation), ('map', '/uav/map/snapshot', MapSnapshot)):
            if key in unsubscribed:
                continue
            subscribers.append(rospy.Subscriber(topic, kind, lambda msg, k=key: receive(msg, k),
                queue_size=1000, buff_size=args.image_buff_size if key in ('infrared', 'bundle') else 65536))
        spawn('nodes', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
                       str(root / 'ros_ws/launch/perf01a_placeholder.launch'),
                       'run_id:=' + run_id, 'duration_s:=' + str(args.duration_s),
                       'frequency_hz:=' + str(frequency),
                       'max_delta_ns:=' + str(int(budget['timing_contract']['max_radar_ir_delta_ms'] * 1e6)),
                       'max_pose_age_ns:=' + str(int(budget['timing_contract']['max_pose_age_ms'] * 1e6)),
                       'staleness_limit_ns:=' + str(int(budget['map_budget']['staleness_limit_ms'] * 1e6))])
        deadline = time.monotonic() + args.duration_s + 25.
        while rospy.get_param('/perf01a_source/done', '') != run_id:
            check_processes()
            if time.monotonic() > deadline:
                raise RuntimeError('source completion timeout')
            time.sleep(.05)
        expected = rospy.get_param('/perf01a_source/expected_samples')
        if expected != count:
            raise RuntimeError('source sample count disagrees with run configuration')
        deadline = time.monotonic() + 5.
        while time.monotonic() < deadline:
            check_processes()
            with lock:
                if (all(len(rows) == (0 if key in unsubscribed else expected_counts[key])
                        for key, rows in records.items()) and
                        len(aggregator.events) == expected_event_count):
                    break
            time.sleep(.05)
        for subscriber in subscribers:
            subscriber.unregister()
        with lock:
            report.update(aggregator.report())
            report['expected_samples'] = expected
            report['topic_counts'] = {key: len(rows) for key, rows in records.items()}
            report['observer_resource_start'] = start_resource
            errors = report['errors']
            errors.extend(validate_receipts({k: v for k, v in records.items() if k not in unsubscribed},
                count, profile, run_id, int(round(1e9 / frequency)),
                'light' if args.observer_mode == 'metadata' else args.observer_mode))
            if len(aggregator.events) != expected_event_count:
                errors.append('event count differs from registered stages')
            if any(r['clock_id'] != 'sim:' + run_id for rows in records.values() for r in rows):
                errors.append('receipt clock mismatch')
            report['observer_callback_ns'] = {key: {
                field: percentile_set([r[field] for r in rows])
                for field in ('callback_work_ns', 'lock_wait_ns')} for key, rows in records.items()}
            if args.segmented_timing:
                report['segmented'] = timing_report(aggregator.events, timing_expected, int(round(1e9 / frequency)))
                errors.extend(report['segmented']['errors'])
            if (report['closed_samples'] != expected_counts['map'] or
                    report['explicit_rejections'] != rejected_count):
                errors.append('event chain differs from registered fault scenario')
            rejected = [e for e in aggregator.events if e['stage'] == 'sensor_bundle_ready' and e['status'] != 'valid']
            if len(rejected) != rejected_count or any(e['reason'] != profile.get('expected_rejection') for e in rejected):
                errors.append('rejection reason/count differs')
            report['sync_metrics_ns'] = {
                key: percentile_set([r[key] for r in records['bundle']])
                for key in ('radar_ir_delta_ns', 'pose_age_ns')}
            report['unexpected_missing_maps'] = max(0, expected_counts['map'] - len(records['map']))
            report['recovery_verified'] = (profile['fault'] == 'none' or
                bool(records['map'] and records['map'][-1]['timestamp'] == (count - 1) * int(round(1e9 / frequency))))
            report['timing_budget_diagnostic'] = dict(
                threshold_ms=budget['timing_contract']['max_p99_latency_ms'],
                passed=report['latency_percentiles']['sensor_to_occupancy_ns']['p99'] is not None and
                    report['latency_percentiles']['sensor_to_occupancy_ns']['p99'] <=
                    budget['timing_contract']['max_p99_latency_ms'] * 1e6,
                scope='development host placeholder; diagnostic only, not airborne acceptance')
            with (run / 'events.json').open('x') as handle:
                json.dump(aggregator.events, handle, ensure_ascii=False, indent=2)
            with (run / 'receipts.json').open('x') as handle:
                json.dump(records, handle, ensure_ascii=False, indent=2)
            report['passed'] = not errors
    except Exception as exc:
        report['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        if sampler is not None:
            sampler.stop()
            starts = [e['monotonic_ns'] for e in aggregator.events if e['stage'] == 'radar_receive']
            ends = [e['monotonic_ns'] for e in aggregator.events if e['stage'] == 'map_snapshot_publish']
            report['chain_resources'] = sampler.report((min(starts), max(ends)) if starts and ends else None)
            if report['chain_resources']['errors'] or report['chain_resources']['missing_roles']:
                report['errors'].append('resource sampling failed or process coverage incomplete')
            with (run / 'resources.json').open('x') as handle:
                json.dump(sampler.rows, handle, indent=2)
        if observer_audit is not None:
            observer_audit.save()
        cleanup = []
        for name, process in reversed(processes):
            forced = False
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=12.)
                except subprocess.TimeoutExpired:
                    forced = True
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5.)
            try:
                os.killpg(process.pid, 0)
                remaining = True
            except ProcessLookupError:
                remaining = False
            cleanup.append(dict(name=name, pid=process.pid, exit=process.returncode,
                                forced=forced, process_group_remaining=remaining))
        for handle in handles:
            handle.close()
        report['cleanup'] = cleanup
        with socket.socket() as probe:
            report['master_port_closed'] = probe.connect_ex(('127.0.0.1', args.port)) != 0
        if not report['master_port_closed']:
            report['errors'].append('master port remains open')
            report['passed'] = False
        if any(r['forced'] or r['process_group_remaining'] for r in cleanup):
            report['errors'].append('process cleanup failed')
            report['passed'] = False
        if args.wire_profile:
            try:
                audits = {role: json.loads((run / (role + '-wire.json')).read_text())
                          for role in ('sensor', 'perception', 'observer')}
                report['wire'] = wire_report(audits, aggregator.events, records, count, profile,
                                             run_id, int(round(1e9 / frequency)), args.observer_mode)
                report['errors'].extend(report['wire']['errors'])
                if args.observer_mode == 'metadata':
                    received = [r for r in audits['perception']['rows'] if r['operation'] == 'callback:SensorBundle']
                    report['sync_metrics_ns'] = {key: percentile_set([r[key] for r in received])
                        for key in ('radar_ir_delta_ns', 'pose_age_ns')}
            except (OSError, ValueError, KeyError) as exc:
                report['errors'].append('wire audit failed: ' + str(exc))
        # 失败路径也保存本次已收到的原始证据，不重建任何历史文件。
        for name, value in (('events.json', aggregator.events), ('receipts.json', records)):
            if not (run / name).exists():
                with (run / name).open('x') as handle:
                    json.dump(value, handle, indent=2)
        report['passed'] = report['passed'] and not report['errors']
        with (run / 'perf-report.json').open('x') as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors']), ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
