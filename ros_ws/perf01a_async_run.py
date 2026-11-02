"""独立Radar/IR异步短时实验；预登记期望、实际ROS核账、独立保存证据。"""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import xmlrpc.client


from perf01a_async_report import (diagnose_oracle_reasons, state_drain_ready,
                                  summarize_async_wire, summarize_timing, transport_accounting,
                                  validate_maps, validate_motion)
from perf01a_metrics import PerfAggregator, percentile_set
from perf01a_resources import ResourceSampler
from online_graph_audit import EXPECTED_ONLINE_NODES, validate_online_graph


def write_json(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def ros_param_profile(profile):
    """ROS XML-RPC不支持None；省略可选空字段以保留消费端默认语义。"""
    def without_none(value):
        if isinstance(value, dict):
            return {key: without_none(item) for key, item in value.items() if item is not None}
        if isinstance(value, list):
            return [without_none(item) for item in value]
        return value

    return without_none(profile)


def _ir_row(msg, receive_monotonic_ns):
    return dict(sample_id=msg.header.sample_id, timestamp=msg.header.timestamp,
                run_id=msg.header.run_id, clock_id=msg.header.clock_id,
                frame_id=msg.header.frame_id, status=msg.header.status,
                width=msg.width, height=msg.height, encoding=msg.encoding,
                value_unit=msg.value_unit, image=list(msg.image),
                exposure_start=msg.exposure_start, exposure_end=msg.exposure_end,
                calibration_id=msg.calibration_id,
                receive_monotonic_ns=receive_monotonic_ns)


def _radar_row(msg, receive_monotonic_ns):
    from ufm_ros_contract.perf01a_codec import from_ros_radar
    return dict(from_ros_radar(msg), receive_monotonic_ns=receive_monotonic_ns)


def verify_radar_value_transport(raw_frames, bundles, profile, expected_sample_ids):
    """Compare captured RadarFrame values with every adopted Bundle; fixture-only."""
    errors, checks = [], []
    tolerance = 1e-6  # ROS RadarPoint values are float32; times and identity stay exact.
    raw_by_id = {row['header']['sample_id']: row for row in raw_frames}
    if len(raw_by_id) != len(raw_frames):
        errors.append('raw radar sample_id is duplicated')
    expected_ids = set(expected_sample_ids)
    if len(expected_ids) != len(expected_sample_ids):
        errors.append('expected radar sample_id is duplicated')
    if set(raw_by_id) != expected_ids:
        errors.append('raw radar sample_id coverage differs from expected publication')
    duration = profile.get('fake_radar', {}).get('scan_duration_ns', 0)
    for raw in raw_frames:
        header = raw['header']
        sample_id = header['sample_id']
        if (header['clock_id'] != 'sim:' + header['run_id'] or
                header['frame_id'] != 'radar' or header['source_type'] != 'fixture' or
                header['status'] != 'valid' or
                raw['scan_end'] - raw['scan_start'] != duration or
                raw['scan_start'] + raw['scan_end'] != 2 * header['timestamp']):
            errors.append('raw radar identity, status or scan midpoint differs: ' + sample_id)
        if (raw['power_quantity'], raw['power_unit'], raw['doppler_reference']) != (
                'uncalibrated_intensity', 'arbitrary', 'sensor_relative'):
            errors.append('raw radar fixture quantity, unit or doppler_reference differs: ' + sample_id)
        if (raw['quality']['confidence'] is not None or
                raw['quality']['uncertainty']['status'] != 'unavailable'):
            errors.append('raw radar quality availability differs: ' + sample_id)
    if not bundles:
        errors.append('no SensorBundle samples available for Radar value verification')
    for bundle in bundles:
        sample_id = bundle['radar_id']
        raw = raw_by_id.get(sample_id)
        if raw is None:
            errors.append('bundle radar sample_id missing from raw publication: ' + sample_id)
            continue
        adopted = bundle['radar']
        for field in ('timestamp', 'run_id', 'clock_id'):
            if bundle[field] != raw['header'][field]:
                errors.append('Radar bundle %s differs from raw: %s' % (field, sample_id))
        for field in ('schema_version', 'timestamp', 'run_id', 'clock_id', 'sample_id',
                      'frame_id', 'source_type', 'status', 'reason'):
            if adopted['header'].get(field) != raw['header'].get(field):
                errors.append('Radar raw/Bundle header %s differs: %s' % (field, sample_id))
        for field in ('scan_start', 'scan_end', 'power_quantity', 'power_unit', 'doppler_reference'):
            if adopted.get(field) != raw.get(field):
                errors.append('Radar raw/Bundle %s differs: %s' % (field, sample_id))
        if adopted.get('quality') != raw.get('quality'):
            for field in ('confidence', 'uncertainty'):
                if adopted['quality'].get(field) != raw['quality'].get(field):
                    errors.append('Radar raw/Bundle quality %s differs: %s' % (field, sample_id))
        raw_points, chosen_points = raw['points'], adopted['points']
        if len(raw_points) != len(chosen_points):
            errors.append('Radar raw/Bundle point count differs: ' + sample_id)
        for index, (before, after) in enumerate(zip(raw_points, chosen_points)):
            for field in ('doppler_available', 'power_available'):
                if before[field] != after[field]:
                    errors.append('Radar point %d %s differs: %s' % (index, field, sample_id))
            for field in ('x', 'y', 'z', 'doppler', 'power'):
                if not (math.isfinite(before[field]) and math.isfinite(after[field]) and
                        math.isclose(before[field], after[field], rel_tol=0, abs_tol=tolerance)):
                    errors.append('Radar point %d %s differs: %s' % (index, field, sample_id))
        checks.append(dict(sample_id=sample_id, timestamp=raw['header']['timestamp'],
                           point_count=len(raw_points)))
    return dict(enabled=True, raw_frames=len(raw_frames), bundle_frames=len(bundles),
                expected_raw_frames=len(expected_ids), checks=checks,
                errors=errors, tolerance=tolerance)


def verify_ir_value_transport(raw_frames, bundles, profile, expected_sample_ids):
    """核对发布IR与采用同一sample_id的Bundle，及已知无噪声oracle。"""
    errors = []
    tolerance = 1e-6  # 32FC1量化后的十进制数值容差。
    raw_by_id = {row['sample_id']: row for row in raw_frames}
    if len(raw_by_id) != len(raw_frames):
        errors.append('raw infrared sample_id is duplicated')
    expected_ids = set(expected_sample_ids)
    if len(expected_ids) != len(expected_sample_ids):
        errors.append('expected infrared sample_id is duplicated')
    if set(raw_by_id) != expected_ids:
        errors.append('raw infrared sample_id coverage differs from expected publication')
    fake = profile.get('fake_infrared', {})
    width, height = profile['ir_resolution']
    background = float(fake.get('background_value', 0.5))
    hotspots = fake.get('hotspots', [])
    if fake.get('noise_std', 0.0) != 0 or width < 2 or height < 2:
        errors.append('IR value oracle requires zero noise and at least 2x2 image')
    def expected_pixel(x, y):
        return background + sum(float(item['value']) for item in hotspots
            if (x - item['x_px']) ** 2 + (y - item['y_px']) ** 2 <= item['radius_px'] ** 2)
    expected_center = expected_pixel(1, 1)
    expected_background = expected_pixel(0, 0)
    if not hotspots or expected_center == background or expected_background != background:
        errors.append('value oracle needs a (1,1) hotspot and unchanged (0,0) background')
    center_index = width + 1  # 按行优先: y=1, x=1。
    background_index = 0
    for raw in raw_frames:
        sample_id = raw['sample_id']
        if (raw['width'], raw['height'], raw['encoding'], raw['value_unit']) != (
                width, height, '32FC1', 'fixture_intensity') or len(raw['image']) != width * height:
            errors.append('raw IR dimensions, encoding, unit or pixel count differ: ' + sample_id)
            continue
        if (raw['clock_id'] != 'sim:' + raw['run_id'] or
                raw['frame_id'] != 'thermal_optical' or raw['status'] != 0 or
                raw['exposure_end'] - raw['exposure_start'] != fake['exposure_duration_ns'] or
                (raw['exposure_start'] + raw['exposure_end']) // 2 != raw['timestamp']):
            errors.append('raw IR identity, status or exposure midpoint differs: ' + sample_id)
        if not math.isclose(raw['image'][center_index], expected_center, rel_tol=0, abs_tol=tolerance):
            errors.append('IR raw hotspot center oracle differs: ' + sample_id)
        if not math.isclose(raw['image'][background_index], expected_background,
                            rel_tol=0, abs_tol=tolerance):
            errors.append('IR raw background oracle differs: ' + sample_id)
    checks = []
    if not bundles:
        errors.append('no SensorBundle samples available for IR value verification')
    for bundle in bundles:
        sample_id = bundle['infrared_id']
        raw = raw_by_id.get(sample_id)
        if raw is None:
            errors.append('bundle infrared sample_id missing from raw publication: ' + sample_id)
            continue
        fields = ('sample_id', 'timestamp', 'run_id', 'clock_id', 'frame_id', 'status', 'width', 'height',
                  'encoding', 'value_unit', 'exposure_start', 'exposure_end', 'calibration_id')
        for field in fields:
            if bundle['infrared'].get(field) != raw.get(field):
                errors.append('IR raw/Bundle field differs: %s (%s)' % (field, sample_id))
        raw_image = raw['image']
        bundle_image = bundle['infrared']['image']
        if len(raw_image) != width * height or len(bundle_image) != len(raw_image):
            errors.append('IR raw/Bundle image length differs: ' + sample_id)
            continue
        mismatches = [index for index, (left, right) in enumerate(zip(raw_image, bundle_image))
                      if not math.isclose(left, right, rel_tol=0, abs_tol=tolerance)]
        if mismatches:
            errors.append('IR raw/Bundle pixel differs at index %d: %s' %
                          (mismatches[0], sample_id))
        if not math.isclose(bundle_image[center_index], expected_center,
                            rel_tol=0, abs_tol=tolerance):
            errors.append('IR bundle hotspot center oracle differs: ' + sample_id)
        if not math.isclose(bundle_image[background_index], expected_background,
                            rel_tol=0, abs_tol=tolerance):
            errors.append('IR bundle background oracle differs: ' + sample_id)
        checks.append(dict(sample_id=sample_id, timestamp=raw['timestamp'], frame_id=raw['frame_id'],
                           exposure_start=raw['exposure_start'], exposure_end=raw['exposure_end'],
                           width=width, height=height, hotspot_center=dict(index=center_index,
                               raw_value=raw_image[center_index], bundle_value=bundle_image[center_index],
                               expected=expected_center),
                           background_pixel=dict(index=background_index,
                               raw_value=raw_image[background_index],
                               bundle_value=bundle_image[background_index], expected=expected_background)))
    return dict(enabled=True, raw_frames=len(raw_frames), bundle_frames=len(bundles),
                expected_raw_frames=len(expected_ids), checks=checks, errors=errors,
                tolerance=tolerance, expected_background=expected_background,
                expected_hotspot_center=expected_center)


def resolve_profile(args):
    """使用业务层同一解析器：defaults、场景、显式CLI覆盖。"""
    from ufm_sensors.perf01a_async import load_profile
    overrides = {}
    if args.full_ir:
        overrides['ir_resolution'] = [640, 512]
    if args.speed_mps is not None:
        overrides['speed_mps'] = args.speed_mps
    if args.pairing_policy is not None:
        overrides['pairing_policy'] = args.pairing_policy
    if args.boundary_obstacles:
        overrides['obstacles_odom'] = [[1.25, 4.25, .25], [-2.25, 6.25, .75]]
    profile = load_profile(args.scenario, args.config, overrides)
    if args.boundary_obstacles and not profile['speed_mps']:
        raise ValueError('boundary-obstacles requires nonzero speed')
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', default='normal')
    parser.add_argument('--config', type=Path, help='async defaults and named scenarios')
    parser.add_argument('--duration-s', type=float, default=3.)
    parser.add_argument('--port', type=int, default=11431)
    parser.add_argument('--full-ir', action='store_true')
    parser.add_argument('--speed-mps', type=int, choices=(0, 35, 50, 70))
    parser.add_argument('--pairing-policy', choices=('deadline', 'exact'))
    parser.add_argument('--wire-profile', action='store_true', help='audit actual ROS IR/bundle wire stages')
    parser.add_argument('--ir-tcp-nodelay', action='store_true',
                        help='request TCP_NODELAY on the IR subscriber connection')
    parser.add_argument('--ir-borrow-image', action='store_true',
                        help='matcher borrows IR message pixels until its owned cache copy')
    parser.add_argument('--match-trace', action='store_true',
                        help='record matcher callback/worker lock and decision provenance')
    parser.add_argument('--endpoint-probe', action='store_true',
                        help='record input capture availability and downstream endpoint latencies')
    parser.add_argument('--boundary-obstacles', action='store_true',
                        help='run the recorded 4.25/6.25m grid-boundary fixture')
    parser.add_argument('--verify-ir-values', action='store_true',
                        help='capture raw IR and verify pixel values against SensorBundle')
    parser.add_argument('--verify-radar-values', action='store_true',
                        help='capture raw RadarFrame and compare every point and status with adopted bundles')
    parser.add_argument('--audit-online-graph', action='store_true',
                        help='sample the live online graph and reject training/LiDAR leakage')
    args = parser.parse_args()
    if not 2 <= args.duration_s <= 60:
        parser.error('duration-s must be in [2, 60]')
    if args.verify_ir_values and (args.scenario != 'ir_value_transport' or args.full_ir):
        parser.error('verify-ir-values requires the dedicated ir_value_transport small-image scenario')
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    from ufm_sensors.perf01a_async import make_schedule, expected_matches
    try:
        profile = resolve_profile(args)
    except (KeyError, ValueError) as exc:
        parser.error(str(exc))
    args.speed_mps = profile['speed_mps']
    args.pairing_policy = profile['pairing_policy']
    duration_ns = round(args.duration_s * 1e9)
    schedule = make_schedule(profile, duration_ns)
    if args.pairing_policy == 'exact':
        for stream in ('radar', 'infrared'):
            stamps = [row['timestamp_ns'] for row in schedule[stream]]
            if len(set(stamps)) != len(stamps):
                parser.error('exact pairing requires unique sampling times in ' + stream)
    expected = expected_matches(profile, duration_ns)
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', args.port))
    run_id = 'perf01a-async-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    write_json(run / 'scenario.json', dict(name=args.scenario, profile=profile, duration_ns=duration_ns))
    write_json(run / 'schedule.json', schedule)
    write_json(run / 'expected.json', expected)
    os.environ.update(ROS_MASTER_URI='http://127.0.0.1:%d' % args.port,
                      ROS_IP='127.0.0.1', ROS_HOME=str(run / 'ros-home'),
                      ROS_LOG_DIR=str(run / 'ros-logs'))
    report = dict(run_id=run_id, scenario=args.scenario, passed=False, errors=[],
                  python=sys.executable, profile=profile, expected=expected,
                  ir_tcp_nodelay=args.ir_tcp_nodelay,
                  ir_borrow_image=args.ir_borrow_image,
                  match_trace=args.match_trace,
                  endpoint_probe=args.endpoint_probe,
                  verify_ir_values=args.verify_ir_values,
                  verify_radar_values=args.verify_radar_values,
                  audit_online_graph=args.audit_online_graph,
                  scope='motion spatiotemporal fixture' if args.speed_mps else 'stationary asynchronous fixture')
    processes, handles, subscribers = [], [], []
    records = {key: [] for key in ('bundle', 'occupancy', 'map')}
    if args.verify_ir_values:
        records['infrared'] = []
    if args.verify_radar_values:
        records['radar'] = []
    clock_records = []
    aggregator = PerfAggregator(run_id)
    lock = threading.RLock()
    sampler = ResourceSampler()
    sampler.start()

    def spawn(name, command):
        handle = (run / (name + '.log')).open('x')
        handles.append(handle)
        process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        processes.append((name, process))

    def check_processes():
        for name, process in processes:
            if process.poll() is not None:
                raise RuntimeError('%s exited %s' % (name, process.returncode))

    def wait_for(predicate, timeout, description):
        deadline = time.monotonic() + timeout
        while not predicate():
            check_processes()
            if 'rospy' in sys.modules:
                import rospy
                for role in ('source', 'radar', 'infrared', 'sensor'):
                    error = rospy.get_param('/perf01a_' + role + '/error', {})
                    if error.get('run_id') == run_id:
                        raise RuntimeError(role + ': ' + error['message'])
            if time.monotonic() >= deadline:
                raise RuntimeError(description + ' timeout')
            time.sleep(.02)

    try:
        spawn('master', [sys.executable, '/opt/ros/noetic/bin/rosmaster', '-p', str(args.port)])
        master = xmlrpc.client.ServerProxy(os.environ['ROS_MASTER_URI'])

        def master_ready():
            try:
                return master.getPid('/perf01a_async_runner')[0] == 1
            except OSError:
                return False

        wait_for(master_ready, 15, 'master startup')
        import rospy
        from rosgraph_msgs.msg import Clock
        from uav_fusionmap_msgs.msg import SensorBundle, OccupancyObservation, MapSnapshot, PerfEvent
        rospy.init_node('perf01a_async_runner', disable_signals=True)
        rospy.set_param('/use_sim_time', True)
        rospy.set_param('/perf01a_async_profile', ros_param_profile(profile))
        rospy.set_param('/perf01a_async_duration_ns', str(duration_ns))
        rospy.set_param('/perf01a_async_run_directory', str(run))
        if args.wire_profile:
            rospy.set_param('/perf01a_wire_audit_directory', str(run))
        if args.speed_mps:
            rospy.set_param('/perf01a_map_audit_directory', str(run))
        rospy.set_param('/perf01a_segmented_timing', True)
        rospy.set_param('/perf01a_observer_mode', 'light')
        rospy.set_param('/perf01a_image_buff_size', 65536)
        rospy.set_param('/perf01a_ir_tcp_nodelay', args.ir_tcp_nodelay)
        rospy.set_param('/perf01a_ir_borrow_image', args.ir_borrow_image)
        rospy.set_param('/perf01a_match_trace', args.match_trace)
        rospy.set_param('/perf01a_endpoint_probe', args.endpoint_probe)
        rospy.set_param('/perf01a_receive_backend', 'standard')

        def receive_event(msg):
            with lock:
                aggregator.record({key: getattr(msg, key) for key in msg.__slots__})

        def receive_clock(msg):
            with lock:
                clock_records.append(dict(timestamp=msg.clock.to_nsec(),
                                          receive_monotonic_ns=time.monotonic_ns()))

        def receive(msg, kind):
            entered = time.monotonic_ns()
            row = dict(sample_id=msg.header.sample_id, timestamp=msg.header.timestamp,
                       run_id=msg.header.run_id, clock_id=msg.header.clock_id,
                       status=msg.header.status, receive_monotonic_ns=entered)
            if kind == 'bundle':
                row.update(radar_id=msg.radar.header.sample_id, infrared_id=msg.infrared.header.sample_id,
                           radar_ir_delta_ns=msg.radar_ir_delta_ns, pose_age_ns=msg.pose_age_ns,
                           infrared_timestamp=msg.infrared.header.timestamp,
                           radar_timestamp=msg.radar.header.timestamp,
                           state_timestamp=msg.state.header.timestamp,
                           image_shape=[msg.infrared.width, msg.infrared.height],
                           pixel_count=len(msg.infrared.image))
                if args.verify_ir_values:
                    row['infrared'] = _ir_row(msg.infrared, entered)
                if args.verify_radar_values:
                    row['radar'] = _radar_row(msg.radar, entered)
                if args.speed_mps or profile.get('map_oracle') == 'radar_points':
                    row.update(state_position=list(msg.state.position),
                        state_velocity=list(msg.state.linear_velocity),
                        radar_to_odom=list(msg.context.T_mapping_source),
                        radar_points=[[p.x, p.y, p.z] for p in msg.radar.points])
            if kind == 'map':
                row.update(revision=msg.revision, cells=[dict(index=[c.x, c.y, c.z],
                    probability=c.probability, observed=c.observed, timestamp=c.last_observed_timestamp)
                    for c in msg.cells])
            if kind == 'occupancy' and args.speed_mps:
                row['voxels'] = [[v.x, v.y, v.z] for v in msg.voxels]
            with lock:
                records[kind].append(row)

        def receive_infrared(msg):
            if args.verify_ir_values:
                with lock:
                    records['infrared'].append(_ir_row(msg, time.monotonic_ns()))

        def receive_radar(msg):
            if args.verify_radar_values:
                with lock:
                    records['radar'].append(_radar_row(msg, time.monotonic_ns()))

        subscribers.append(rospy.Subscriber('/uav/perf/events', PerfEvent, receive_event, queue_size=4000))
        subscribers.append(rospy.Subscriber('/clock', Clock, receive_clock, queue_size=4000))
        if args.verify_ir_values:
            from uav_fusionmap_msgs.msg import InfraredFrame
            subscribers.append(rospy.Subscriber('/uav/sensors/infrared', InfraredFrame,
                receive_infrared, queue_size=1000, buff_size=65536))
        if args.verify_radar_values:
            from uav_fusionmap_msgs.msg import RadarFrame
            subscribers.append(rospy.Subscriber('/uav/sensors/radar', RadarFrame,
                receive_radar, queue_size=1000, buff_size=65536))
        for kind, topic, msg_type in (
                ('bundle', '/uav/sensors/bundle', SensorBundle),
                ('occupancy', '/uav/perception/occupancy', OccupancyObservation),
                ('map', '/uav/map/snapshot', MapSnapshot)):
            subscribers.append(rospy.Subscriber(topic, msg_type, lambda msg, key=kind: receive(msg, key),
                queue_size=1000, buff_size=65536))
        spawn('nodes', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
                       str(root / 'ros_ws/launch/perf01a_async.launch'), 'run_id:=' + run_id,
                       'duration_s:=' + str(args.duration_s),
                       'max_delta_ns:=' + str(profile['max_delta_ns']),
                       'max_pose_age_ns:=' + str(profile['max_pose_age_ns'])])
        if args.audit_online_graph:
            graph_snapshot = {}

            def online_graph_ready():
                code, _, graph = master.getSystemState('/perf01a_async_runner')
                if code != 1:
                    return False
                publishers, subscriptions, _ = graph
                observed_nodes = {
                    node
                    for topic, nodes in publishers + subscriptions
                    for node in nodes
                }
                if not set(EXPECTED_ONLINE_NODES).issubset(observed_nodes):
                    return False
                graph_snapshot['publishers'] = publishers
                graph_snapshot['subscribers'] = subscriptions
                return True

            wait_for(online_graph_ready, 10, 'online graph readiness')
            report['online_graph'] = validate_online_graph(
                graph_snapshot['publishers'], graph_snapshot['subscribers'])
            report['errors'].extend('online_graph: ' + error
                                    for error in report['online_graph']['errors'])
        wait_for(lambda: rospy.get_param('/perf01a_source/done', '') == run_id,
                 args.duration_s * 3 + 25, 'source completion')
        publishers = master.getSystemState('/perf01a_async_runner')[2][0]
        report['clock_publishers'] = next((nodes for topic, nodes in publishers if topic == '/clock'), [])
        if report['clock_publishers'] != ['/perf01a_source']:
            report['errors'].append('clock publisher is not unique source')
        for kind in ('radar', 'infrared'):
            wait_for(lambda k=kind: (run / (k + '-audit.json')).exists(), 5, kind + ' audit')
        source = json.loads((run / 'source-audit.json').read_text())
        if source['errors']:
            raise RuntimeError('source publication failed')
        # Cross-topic state/clock delivery is not ordered; wait for actual coverage.
        wait_for(lambda: state_drain_ready(source,
                 rospy.get_param('/perf01a_sensor/state_drain', {}), run_id),
                 8, 'source state and clock drain')
        report['state_drain_before_finish'] = rospy.get_param('/perf01a_sensor/state_drain')
        # Finish only after real state/clock coverage and independent producer receipts.
        wait_for(lambda: all(rospy.get_param('/perf01a_sensor/received_' + kind, -1) ==
                    sum(not row['drop'] for row in schedule[kind]) for kind in ('radar', 'infrared')),
                 8, 'sensor receipts')
        rospy.set_param('/perf01a_async_finish', run_id)
        wait_for(lambda: rospy.get_param('/perf01a_sensor/done', '') == run_id, 5, 'matcher drain')
        matcher = json.loads((run / 'matcher-audit.json').read_text())
        expected_maps = sum(not d['reason'] for d in matcher['decisions'])
        wait_for(lambda: len(records['map']) >= expected_maps and
                 sum(e['stage'] == 'map_snapshot_publish' for e in aggregator.events) >= expected_maps,
                 8, 'map drain')
        # 同一发布者事件队列尾部的timing.map_publish也必须送达后再关闭观察器。
        wait_for(lambda: sum(e['stage'] == 'timing.map_publish' for e in aggregator.events) >= expected_maps,
                 5, 'timing drain')
        if args.verify_ir_values:
            expected_raw = sum(not row['drop'] for row in schedule['infrared'])
            wait_for(lambda: len(records['infrared']) >= expected_raw, 5, 'raw infrared drain')
        if args.verify_radar_values:
            expected_raw = sum(not row['drop'] for row in schedule['radar'])
            wait_for(lambda: len(records['radar']) >= expected_raw, 5, 'raw radar drain')
        for subscriber in subscribers:
            subscriber.unregister()
        subscribers.clear()
        with lock:
            setup_errors = report['errors']
            report.update(aggregator.report())
            report['errors'].extend(setup_errors)
            report['errors'].extend(matcher.get('errors', []))
            report['matcher'] = matcher
            report['topic_counts'] = {k: len(v) for k, v in records.items()}
            report['errors'].extend(validate_maps(records, matcher['decisions'], run_id,
                motion=bool(args.speed_mps), map_oracle=profile.get('map_oracle')))
            report['transport'] = {}
            for kind in ('radar', 'infrared'):
                producer = json.loads((run / (kind + '-audit.json')).read_text())
                adopted = [d[kind + '_id'] for d in matcher['decisions'] if not d['reason']]
                account = transport_accounting(schedule[kind], producer, matcher['receipts'][kind], adopted)
                producer_stats = producer['stats']
                account['producer_buffer'] = producer_stats
                if (producer_stats['pending_high_water'] > producer_stats['producer_capacity'] or
                        producer_stats['producer_overflow']):
                    account['errors'].append('producer payload capacity exceeded or dropped input')
                report['transport'][kind] = account
                report['errors'].extend(kind + ': ' + error for error in account['errors'] + producer.get('errors', []))
            received_ir = {r['sample_id']: r for r in matcher['receipts']['infrared']}
            for row in records['bundle']:
                if row['infrared_timestamp'] != received_ir.get(row['infrared_id'], {}).get('timestamp'):
                    report['errors'].append('bundle infrared sampling timestamp differs from received input')
                if (row['image_shape'] != profile['ir_resolution'] or
                        row['pixel_count'] != profile['ir_resolution'][0] * profile['ir_resolution'][1]):
                    report['errors'].append('bundle image shape differs from profile')
            if args.verify_ir_values:
                expected_raw_ids = [row['sample_id'] for row in json.loads(
                    (run / 'infrared-audit.json').read_text())['rows'] if not row['drop']]
                report['ir_value_verification'] = verify_ir_value_transport(
                    records['infrared'],
                    [dict(infrared_id=row['infrared_id'], infrared=row['infrared'])
                     for row in records['bundle']], profile, expected_raw_ids)
                report['errors'].extend('ir_values: ' + error for error in
                                        report['ir_value_verification']['errors'])
            radar_audit = json.loads((run / 'radar-audit.json').read_text())
            if args.verify_radar_values:
                expected_raw_ids = [row['sample_id'] for row in radar_audit['rows'] if not row['drop']]
                report['radar_value_verification'] = verify_radar_value_transport(
                    records['radar'], [dict(radar_id=row['radar_id'], radar=row['radar'],
                        timestamp=row['timestamp'], run_id=row['run_id'], clock_id=row['clock_id'])
                        for row in records['bundle']], profile, expected_raw_ids)
                report['errors'].extend('radar_values: ' + error for error in
                                        report['radar_value_verification']['errors'])
            report['segmented'] = summarize_timing(aggregator.events, matcher['decisions'],
                                                   radar_audit['rows'], matcher['receipts']['radar'],
                                                   endpoint_probe=args.endpoint_probe)
            report['errors'].extend(report['segmented']['errors'])
            report['matching_metrics_ns'] = {key: percentile_set([d[key] for d in matcher['decisions']])
                                              for key in ('wait_ns', 'data_age_ns')}
            report['receive_cost_ns'] = {kind: {field: percentile_set([
                row[field] for row in matcher['receipts'][kind] if field in row])
                for field in ('lock_wait_ns', 'decode_ns', 'cache_and_emit_ns')}
                for kind in ('radar', 'infrared')}
            report['radar_nonclosure_rate'] = report.pop('drop_rate')
            report['radar_nonclosure_semantics'] = report.pop('drop_rate_semantics')
            report['unexpected_transport_losses'] = sum(a['unexpected_lost'] for a in report['transport'].values())
            stats = matcher['stats']
            for kind in ('radar', 'infrared', 'state'):
                if stats['cache_sizes'][kind] != 0 or stats['high_water'][kind] > profile[kind + '_capacity']:
                    report['errors'].append(kind + ': cache capacity or EOF drain failure')
                counts = stats['counts'][kind]
                if counts['received'] != counts['adopted'] + counts['not_adopted'] or counts['pending']:
                    report['errors'].append(kind + ': terminal accounting failure')
            actual = {int(d['radar_id'].rsplit(':', 1)[1]):
                      dict(infrared_sequence=(int(d['infrared_id'].rsplit(':', 1)[1])
                                              if d.get('infrared_id') else None), reason=d['reason'])
                      for d in matcher['decisions']}
            report['actual_matches'] = actual
            expected_rows = list(expected.values())
            oracle = {sequence: dict(infrared_sequence=row['infrared_sequence'], reason=row['reason'])
                      for sequence, row in expected.items()}
            report['expected_rejections'] = sum(bool(r['reason']) for r in expected_rows)
            report['oracle_reason_diagnostic'] = diagnose_oracle_reasons(
                expected, matcher['decisions'], list(stats['records']['infrared'].values()),
                profile['max_wait_ns'], profile['max_wall_wait_ns'], profile['max_delta_ns'])
            if actual != oracle or len(actual) != len(matcher['decisions']):
                report['errors'].append('matching decisions differ from preregistered oracle')
            expected_accepted = sum(not row['reason'] for row in expected_rows)
            if report['closed_samples'] != expected_accepted or report['explicit_rejections'] != report['expected_rejections']:
                report['errors'].append('event closure differs from preregistered oracle')
            clock_values = [r['timestamp'] for r in clock_records]
            if not clock_values or any(a >= b for a, b in zip(clock_values, clock_values[1:])):
                report['errors'].append('clock is empty or not strictly increasing')
            report['clock'] = dict(received=len(clock_values), first=clock_values[0] if clock_values else None,
                                   last=clock_values[-1] if clock_values else None)
            source_audit_path = run / 'source-audit.json'
            if source_audit_path.exists():
                source = json.loads(source_audit_path.read_text())
                report['source_audit'] = source
                report['errors'].extend(source.get('errors', []))
                clock_expected = list(range(0, duration_ns + profile['source_drain_ns'] + 1,
                                            profile['clock_period_ns']))
                if (source['run_id'] != run_id or source['python'] != sys.executable or
                        source['clock_count'] != len(clock_expected) or clock_values != clock_expected or
                        source['first_ns'] != clock_expected[0] or source['last_ns'] != clock_expected[-1]):
                    report['errors'].append('source publication/clock receipt sequence differs')
                state_period = 1_000_000_000 // profile['state_frequency_hz']
                state_expected = list(range(0, clock_expected[-1] + 1, state_period))
                states = stats['records']['state']
                state_actual = {row['sample_id']: row['timestamp_ns'] for row in states.values()}
                state_identities = {'sensors.state:fixture.state:%s:%d' % (run_id, index): stamp
                                    for index, stamp in enumerate(state_expected)}
                if source['state_count'] != len(state_expected) or state_actual != state_identities:
                    report['errors'].append('source publication/adapted state receipts differ')
            else:
                report['errors'].append('source publication audit missing')
            recovery = {sequence: row for sequence, row in oracle.items()
                        if expected[sequence]['timestamp_ns'] >= profile['recovery_start_ns']}
            report['recovery_verified'] = bool(recovery and any(not r['reason'] for r in recovery.values()) and
                                               all(actual.get(seq) == row for seq, row in recovery.items()))
            if not report['recovery_verified']:
                report['errors'].append('registered recovery interval not verified')
            p99 = report['latency_percentiles']['sensor_to_occupancy_ns']['p99']
            report['timing_budget_diagnostic'] = dict(threshold_ms=20, passed=p99 is not None and p99 <= 20_000_000,
                p99_ns=p99, scope='actual radar callback to occupancy; pairing wait included; development host only')
            report['passed'] = not report['errors']
    except Exception as exc:
        report['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        for subscriber in subscribers:
            subscriber.unregister()
        sampler.stop()
        starts = [e['monotonic_ns'] for e in aggregator.events if e['stage'] == 'radar_receive']
        ends = [e['monotonic_ns'] for e in aggregator.events if e['stage'] == 'map_snapshot_publish']
        report['chain_resources'] = sampler.report((min(starts), max(ends)) if starts and ends else None)
        roles = {p['role'] for p in report['chain_resources']['processes'] if p['samples'] >= 2}
        report['chain_resources']['missing_roles'] = sorted(set(report['chain_resources']['missing_roles']) |
            ({'perf01a_radar', 'perf01a_infrared'} - roles))
        if report['chain_resources']['errors'] or report['chain_resources']['missing_roles']:
            report['errors'].append('resource sampling failed or process coverage incomplete')
        cleanup = []
        for name, process in reversed(processes):
            forced = False
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    forced = True
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            try:
                os.killpg(process.pid, 0)
                remaining = True
            except ProcessLookupError:
                remaining = False
            cleanup.append(dict(name=name, pid=process.pid, exit=process.returncode, forced=forced,
                                process_group_remaining=remaining))
        for handle in handles:
            handle.close()
        if args.speed_mps:
            aging_path = run / 'map-aging.json'
            if aging_path.exists() and 'matcher' in report:
                aging = json.loads(aging_path.read_text())
                report['motion'] = validate_motion(records, report['matcher']['decisions'], profile, aging)
                report['errors'].extend(report['motion']['errors'])
                if args.scenario in ('missing', 'recovery') and not (
                        report['motion']['stale_during_fault'] and report['motion']['fresh_after_recovery']):
                    report['errors'].append('motion: fault gap stale and recovery not observed')
            else:
                report['errors'].append('motion: map clock-aging audit missing')
        report['cleanup'] = cleanup
        if args.wire_profile:
            names = ('infrared', 'sensor', 'perception')
            if 'matcher' in report and all((run / (name + '-wire.json')).exists() for name in names):
                audits = {name: json.loads((run / (name + '-wire.json')).read_text()) for name in names}
                report['wire'] = summarize_async_wire(audits, report['matcher']['receipts']['infrared'],
                                                       report['matcher']['decisions'])
                report['errors'].extend(report['wire']['errors'])
            else:
                report['errors'].append('wire: audit missing')
        with socket.socket() as probe:
            report['master_port_closed'] = probe.connect_ex(('127.0.0.1', args.port)) != 0
        if not report['master_port_closed'] or any(r['forced'] or r['process_group_remaining'] for r in cleanup):
            report['errors'].append('process cleanup failed')
        report['passed'] = report['passed'] and not report['errors']
        for name, value in (('events.json', aggregator.events), ('receipts.json', records),
                            ('clocks.json', clock_records), ('resources.json', sampler.rows),
                            ('perf-report.json', report)):
            write_json(run / name, value)
        print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors']), ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
