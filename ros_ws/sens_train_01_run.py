"""SENS-TRAIN-01 bounded ROS smoke; launch via bash ros_ws/sim01_env.sh."""
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import xmlrpc.client


def _close(actual, expected):
    if (not math.isfinite(actual) or not math.isfinite(expected)
            or abs(actual - expected) > 1e-6):
        raise ValueError('training numerical oracle mismatch: %r != %r' % (actual, expected))


def _motion_oracle(row, states, config):
    lidar = row['lidar']
    reference = lidar['header']['timestamp']
    points = lidar['points']
    if [point['ray_index'] for point in points] != [0, 2]:
        raise ValueError('motion fixture must retain two echoes and one no-echo time slot')
    if lidar['reference_pose_sample_ids'] != [states[reference]['header']['sample_id']]:
        raise ValueError('scan midpoint pose identity mismatch')
    mount = config['calibration']['T_body_training_lidar']
    # Independent analytic oracle for this northward, fixed-attitude two-box fixture.
    for point, obstacle in zip(points, config['scene']['obstacles_odom']):
        ray_index = point['ray_index']
        acquisition = lidar['scan_start'] + config['lidar']['ray_time_offsets_ns'][ray_index]
        if (point['point_time_ns'] != acquisition
                or point['pose_sample_ids'] != [states[acquisition]['header']['sample_id']]):
            raise ValueError('point acquisition time/pose identity mismatch')
        face_y = obstacle['center_m'][1] - obstacle['size_m'][1] / 2
        raw_x = face_y - .1 * acquisition / 1e9 - mount[3]
        ray = config['lidar']['rays_lidar'][ray_index]
        raw_y = raw_x * ray[1] / ray[0]
        for actual, expected in zip(point['raw_xyz'], [raw_x, raw_y, 0.]):
            _close(actual, expected)
        for axis, expected in zip(('x', 'y', 'z'),
                                  [face_y - .1 * reference / 1e9 - mount[3], raw_y, 0.]):
            _close(point[axis], expected)
    for actual, expected in zip(lidar['first_hit_odom'], [0., 5.75, .2]):
        _close(actual, expected)
    labels = row['supervision']
    shape = labels['grid_shape']
    def flat(index):
        return (index[0] * shape[1] + index[1]) * shape[2] + index[2]
    occupied = []
    for point in points:
        index = [math.floor((point[axis] - labels['grid_origin_m'][i]) /
                            labels['grid_resolution_m'][i])
                 for i, axis in enumerate(('x', 'y', 'z'))]
        occupied.append(flat(index))
    if [i for i, value in enumerate(labels['target']) if value == 'occupied'] != sorted(occupied):
        raise ValueError('motion fixture occupied endpoints mismatch')
    for index, expected in (((4, 4, 4), 'free'), ((4, 3, 4), 'unknown'),
                            ((12, 4, 4), 'unknown')):
        cell = flat(index)
        if (labels['target'][cell] != expected
                or labels['observed_mask'][cell] != (expected != 'unknown')):
            raise ValueError('motion fixture free/no-echo/occlusion oracle mismatch')


def _yaw_oracle(rows, states, config, references, run_id):
    # This acceptance runner reuses the independent test oracle, never a ROS node.
    test_path = str(Path(__file__).resolve().parents[1] / 'tests')
    if test_path not in sys.path:
        sys.path.insert(0, test_path)
    from sens_train_01_scene_suite import audit_case
    profile = config['fixture_motion']
    plan = dict(anchor_timestamp_ns=profile['anchor_timestamp_ns'],
                reference_timestamps_ns=references, numerical_tolerance_m=1e-6)
    case = dict(case_id='ros_yaw', geometry='two', speed_mps=profile['speed_mps'],
                yaw_rate_deg_s=profile['yaw_rate_deg_s'])
    report = audit_case(case, plan, config, states, rows, run_id=run_id)
    if not profile['yaw_rate_deg_s'] or not report['interpolated_echo_count']:
        raise ValueError('yaw fixture must exercise nonzero rotation and interpolated echoes')
    for row in rows:
        grid = row['supervision']
        # Uncovered negative lateral region and a region beyond both first returns.
        for index in ((4, 2, 4), (14, 4, 4)):
            cell = (index[0] * grid['grid_shape'][1] + index[1]) * grid['grid_shape'][2] + index[2]
            if grid['target'][cell] != 'unknown' or grid['observed_mask'][cell]:
                raise ValueError('yaw fixture uncovered/occluded region must remain unknown')
    report['unknown_probe_checks'] = 2 * len(rows)
    return report


def validate_training_run(rows, receipts, config, run_id, count=20):
    """Read-only file/ROS reconciliation and known-fixture geometry checks."""
    from ufm_sensors.training_supervision import validate_training_sample
    references = list(range(100_000_000, (count + 1) * 100_000_000, 100_000_000))
    half = config['lidar']['scan_duration_ns'] // 2
    source_times = list(range(references[0] - half, references[-1] + half + 1, 100_000_000))
    if (len(rows) != count or any(len(receipts[key]) != count
                                  for key in ('radar', 'infrared', 'training'))
            or len(receipts['state']) != len(source_times) or receipts['clock'] != source_times
            or rows != receipts['training']):
        raise ValueError('training file/receipt count, order or payload mismatch')
    states = {}
    profile = config.get('fixture_motion')
    for sequence, (source, stamp) in enumerate(zip(receipts['state'], source_times)):
        header = source['header']
        if (header['timestamp'] != stamp or header['run_id'] != run_id
                or header['clock_id'] != 'sim:' + run_id
                or header['sample_id'] != 'fixture.state:%s:%d' % (run_id, sequence)
                or header['status'] != 'valid' or header['source_type'] != 'simulation'
                or header['frame_id'] != 'world_ned' or source['body_frame_id'] != 'body_frd'
                or source['state_source'] != 'estimated'):
            raise ValueError('training source state identity/order mismatch')
        elapsed = (stamp - profile['anchor_timestamp_ns']) / 1e9 if profile else stamp / 1e9
        speed = profile['speed_mps'] if profile else .1
        yaw = math.radians(profile['yaw_rate_deg_s']) * elapsed if profile else 0.
        for field, expected in (('position', [speed * elapsed, 0., 0.]),
                                ('orientation_xyzw', [0., 0., math.sin(yaw / 2), math.cos(yaw / 2)]),
                                ('linear_velocity', [speed * math.cos(yaw), -speed * math.sin(yaw), 0.])):
            if len(source[field]) != len(expected):
                raise ValueError('source state vector size mismatch')
            for actual, value in zip(source[field], expected):
                _close(actual, value)
        states[stamp] = source
    for row, radar, infrared, reference in zip(rows, receipts['radar'], receipts['infrared'], references):
        validate_training_sample(row, config)
        if (row['run_id'] != run_id or row['clock_id'] != 'sim:' + run_id
                or row['state_sample_id'] != 'sensors.state:' + states[reference]['header']['sample_id']
                or any(row[kind]['header']['timestamp'] != reference
                       for kind in ('radar', 'infrared', 'lidar'))):
            raise ValueError('training record identity/reference mismatch')
        for kind, received, fields in (
                ('radar', radar, ('header', 'scan_start', 'scan_end', 'power_quantity',
                                  'power_unit', 'doppler_reference')),
                ('infrared', infrared, ('header', 'exposure_start', 'exposure_end', 'width',
                                        'height', 'encoding', 'value_unit', 'camera_info'))):
            if any(row[kind][key] != received[key] for key in fields):
                raise ValueError('ROS %s metadata changed' % kind)
        if len(radar['points']) != len(row['radar']['points']):
            raise ValueError('ROS radar point count changed')
        for expected, actual in zip(row['radar']['points'], radar['points']):
            for axis in ('x', 'y', 'z'):
                _close(actual[axis], expected[axis])
            if actual['doppler_available'] or actual['power_available']:
                raise ValueError('fixture radar physical quality must remain unavailable')
        if len(infrared['image']) != len(row['infrared']['image']):
            raise ValueError('ROS infrared pixel count changed')
        for actual, expected in zip(infrared['image'], row['infrared']['image']):
            _close(actual, expected)
        if half and not profile:
            # ROS state IDs are source IDs; the training adapter prefixes them once.
            adapted_ids = {stamp: dict(header=dict(sample_id='sensors.state:' + item['header']['sample_id']))
                           for stamp, item in states.items()}
            _motion_oracle(row, adapted_ids, config)
    report = dict(record_count=len(rows), source_state_count=len(source_times),
                source_clock_count=len(receipts['clock']), schema_version=config['schema_version'],
                scan_duration_ns=config['lidar']['scan_duration_ns'],
                reference_start_ns=references[0], reference_end_ns=references[-1],
                motion_oracle_count=count if half and not profile else 0,
                full_training_payload_match=True, radar_ir_values_match=True)
    if profile:
        report['yaw_oracle'] = _yaw_oracle(rows, list(states.values()), config, references, run_id)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=11447)
    parser.add_argument('--fixture', choices=('single', 'multiray', 'motion', 'yaw'), default='single')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', args.port))
        except OSError as error:
            raise RuntimeError('port occupied; existing process preserved') from error
    run_id = 'sens-train-01-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    (run / 'ros-home').mkdir()
    (run / 'ros-logs').mkdir()
    fixture_name = {'single': 'sens_train_01_fixture.yaml',
                    'multiray': 'sens_train_01_multiray_fixture.yaml',
                    'motion': 'sens_train_01_motion_fixture.yaml',
                    'yaw': 'sens_train_01_yaw_fixture.yaml'}[args.fixture]
    config_file = run / fixture_name
    shutil.copy2(str(root / 'configs' / fixture_name), str(config_file))
    env = dict(os.environ, ROS_MASTER_URI='http://127.0.0.1:%d' % args.port,
               ROS_IP='127.0.0.1', ROS_HOME=str(run/'ros-home'),
               ROS_LOG_DIR=str(run/'ros-logs'))
    os.environ.update({k: env[k] for k in ('ROS_MASTER_URI', 'ROS_IP', 'ROS_HOME', 'ROS_LOG_DIR')})
    processes, streams, records = [], [], {'radar':[], 'infrared':[], 'training':[], 'state':[], 'clock':[]}
    report = dict(run_id=run_id, fixture=args.fixture, python=sys.executable, master_uri=env['ROS_MASTER_URI'],
                  passed=False, errors=[], received={}, graph={}, execution_mode='ros_fixture',
                  hardware_validated=False, model_quality_validated=False, formal_perf_validated=False)

    def spawn(name, command):
        stream = (run / (name+'.log')).open('x', encoding='utf-8')
        streams.append(stream)
        process = subprocess.Popen(command, env=env, cwd=str(run), stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        processes.append((name, process))

    def wait_for(predicate, deadline, label):
        while time.monotonic() < deadline:
            for name, process in processes:
                if process.poll() is not None:
                    raise RuntimeError('%s exited early: %s' % (name, process.returncode))
            if predicate():
                return
            if 'rospy' in sys.modules:
                import rospy
                rejected = rospy.get_param('/sens_train_01_fake_lidar/rejected', '')
                if rejected:
                    raise RuntimeError('training node rejected input: ' + rejected)
            time.sleep(.05)
        raise RuntimeError(label+' timeout')

    result = 1
    try:
        spawn('master', [sys.executable, '/opt/ros/noetic/bin/rosmaster', '-p', str(args.port)])
        master = xmlrpc.client.ServerProxy(env['ROS_MASTER_URI'])
        def master_ready():
            try:
                return master.getPid('/sens_train_01_runner')[0] == 1
            except (OSError, xmlrpc.client.Error):
                return False
        wait_for(master_ready, time.monotonic()+15, 'ROS master')
        import rospy
        from uav_fusionmap_msgs.msg import AircraftState, InfraredFrame, RadarFrame
        from rosgraph_msgs.msg import Clock
        from std_msgs.msg import String
        rospy.init_node('sens_train_01_runner', disable_signals=True)
        subscribers = [
            rospy.Subscriber('/uav/training/radar', RadarFrame, lambda msg: records['radar'].append(msg), queue_size=30),
            rospy.Subscriber('/uav/training/infrared', InfraredFrame, lambda msg: records['infrared'].append(msg), queue_size=30),
            rospy.Subscriber('/uav/training/lidar_supervision', String, lambda msg: records['training'].append(msg), queue_size=30),
            rospy.Subscriber('/uav/sim/state', AircraftState, lambda msg: records['state'].append(msg), queue_size=30),
            rospy.Subscriber('/clock', Clock, lambda msg: records['clock'].append(msg), queue_size=30),
        ]
        spawn('training', [sys.executable, '/opt/ros/noetic/bin/roslaunch',
                           str(root/'ros_ws/launch/sens_train_01.launch'), 'run_id:='+run_id,
                           'output_path:='+str(run/'training-records.jsonl'),
                           'config_path:='+str(config_file)])
        expected_states = 22 if args.fixture in ('motion', 'yaw') else 20
        wait_for(lambda: rospy.get_param('/sens_train_01_source/done', '') == run_id
                 and rospy.get_param('/sens_train_01_recorder/received', 0) == 20
                 and all(len(records[key]) == 20 for key in ('radar', 'infrared', 'training'))
                 and len(records['state']) == expected_states and len(records['clock']) == expected_states,
                 time.monotonic()+35, '20 ROS training samples')
        rows = [json.loads(line) for line in (run/'training-records.jsonl').read_text().splitlines()]
        from ufm_sensors.training_supervision import validate_training_sample
        import yaml
        config = yaml.safe_load(config_file.read_text())
        for row in rows:
            validate_training_sample(row, config)
            if args.fixture == 'multiray':
                labels = row['supervision']
                if (len(row['radar']['points']) != 2 or len(row['lidar']['points']) != 2
                        or len([v for v in labels['target'] if v == 'occupied']) != 2
                        or abs(row['infrared']['image'][6]-.9) > 1e-6
                        or abs(row['infrared']['image'][7]-.9) > 1e-6
                        or labels['observed_mask'][(7*8+5)*8+4]):
                    raise RuntimeError('multiray geometry / occlusion oracle failed')
        from ufm_ros_contract import from_ros_state
        from ufm_ros_contract.perf01a_codec import from_ros_radar, from_ros_infrared
        receipts = dict(state=[from_ros_state(msg) for msg in records['state']],
                        clock=[msg.clock.to_nsec() for msg in records['clock']],
                        radar=[from_ros_radar(msg) for msg in records['radar']],
                        infrared=[from_ros_infrared(msg) for msg in records['infrared']],
                        training=[json.loads(msg.data) for msg in records['training']])
        for kind, values in receipts.items():
            with (run / (kind + '-receipts.jsonl')).open('x', encoding='utf-8') as handle:
                for value in values:
                    handle.write(json.dumps(value, allow_nan=False) + '\n')
        report['audit'] = validate_training_run(rows, receipts, config, run_id)
        source_counts = [rospy.get_param('/sens_train_01_source/' + field, 0)
                         for field in ('published_states', 'published_clocks')]
        if (source_counts != [expected_states, expected_states]
                or rospy.get_param('/sens_train_01_fake_lidar/received_states', 0) != expected_states
                or rospy.get_param('/sens_train_01_fake_lidar/published', 0) != 20):
            raise RuntimeError('source publication / training consumption count mismatch')
        report['source_publication_counts'] = source_counts
        code, _, graph = master.getSystemState('/sens_train_01_runner')
        if code != 1:
            raise RuntimeError('unable to inspect ROS graph')
        publishers, subscriptions, _ = graph
        li_pub = [names for topic, names in publishers if topic == '/uav/training/lidar_supervision']
        li_sub = [names for topic, names in subscriptions if topic == '/uav/training/lidar_supervision']
        report['graph'] = dict(lidar_publishers=li_pub, lidar_subscribers=li_sub,
                               publishers=publishers, subscriptions=subscriptions)
        if (li_pub != [['/sens_train_01_fake_lidar']]
                or not li_sub or set(li_sub[0]) != {'/sens_train_01_recorder', '/sens_train_01_runner'}):
            raise RuntimeError('training supervision graph leaked to online nodes')
        for topic in ('/clock', '/uav/sim/state'):
            if [set(names) for name, names in publishers if name == topic] != [{'/sens_train_01_source'}]:
                raise RuntimeError('training source has conflicting publisher: ' + topic)
        training_nodes = {'/sens_train_01_source', '/sens_train_01_fake_lidar',
                          '/sens_train_01_recorder', '/sens_train_01_runner', '/rosout'}
        if any(set(names) - training_nodes for _, names in publishers + subscriptions):
            raise RuntimeError('training graph contains unexpected online consumers')
        report['received'] = {key:len(value) for key, value in records.items()}
        report['record_count'] = len(rows)
        report['passed'] = True
        result = 0
    except Exception as error:
        report['errors'].append('%s: %s' % (type(error).__name__, error))
    finally:
        for name, process in reversed(processes):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
        for name, process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            report.setdefault('children', []).append(dict(name=name, pid=process.pid, exit=process.returncode))
        for stream in streams:
            stream.close()
        report['port_released'] = False
        for _ in range(20):
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(('127.0.0.1', args.port))
                    report['port_released'] = True
                    break
                except OSError:
                    time.sleep(.1)
        if not report['port_released']:
            result = 1
            report['passed'] = False
            report['errors'].append('ROS master port was not released')
        (run/'validation.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
        print(json.dumps(dict(run=str(run), exit=result, received=report['received'],
                              errors=report['errors'], port_released=report['port_released'])))
    return result


if __name__ == '__main__':
    sys.exit(main())
