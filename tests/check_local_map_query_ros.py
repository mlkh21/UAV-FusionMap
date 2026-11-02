"""Independent ROS query client and marked occupancy fixture; no map implementation."""
import argparse
import copy
import json
from pathlib import Path
import sys
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import MapSnapshot, OccupancyObservation, PerfEvent
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import from_ros_snapshot, to_ros_occupancy
from ufm_ros_contract.query_codec import from_ros_query_result

MS = 1_000_000


def validate_mapping_graph(system, clock_owner):
    subscriptions = {topic for topic, nodes in system[1] if '/perf01a_mapping' in nodes}
    if ('/uav/perception/occupancy' not in subscriptions or
            subscriptions - {'/uav/perception/occupancy', '/clock'}):
        raise ValueError('mapping subscription violates boundary: ' + repr(sorted(subscriptions)))
    clock_owners = [nodes for topic, nodes in system[0] if topic == '/clock']
    if clock_owners != [[clock_owner]]:
        raise ValueError('fixture must have exactly one clock publisher')
    return sorted(subscriptions)


def fixture(run_id, sequence, stamp):
    identity = [1.0 if row == col else 0.0 for row in range(4) for col in range(4)]
    unknown = dict(status='unavailable', kind='occupancy_variance', value=None,
                   unit='dimensionless', source='query fixture unknown')
    return dict(header=dict(schema_version='0.1', timestamp=stamp, clock_id='sim:' + run_id,
        run_id=run_id, sample_id='perception.occupancy:query:%s:%d' % (run_id, sequence),
        frame_id='odom', source_type='fixture', status='valid', reason=''),
        resolution=[0.5] * 3, shape=[64, 32, 16], origin=[-16.0, -8.0, -4.0],
        context=dict(reference_timestamp=stamp, clock_id='sim:' + run_id,
            mapping_frame_id='odom', source_frame_id='odom', T_mapping_source=identity,
            T_mapping_body=identity, T_mapping_source_status='available',
            T_mapping_body_status='available', calibration_id='query_fixture_declared_identity',
            state_source='fixture', pose_uncertainty=unknown),
        observed_domain_source='explicit_query_fixture_not_radar_no_return',
        voxels=[dict(index=[48, 16, 8], probability=0.9, observed=True,
                     confidence=None, uncertainty=unknown),
                dict(index=[40, 16, 8], probability=0.1, observed=True,
                     confidence=0.25, uncertainty=dict(status='available',
                     kind='occupancy_variance', value=[0.125], unit='dimensionless',
                     source='query fixture known')),
                dict(index=[44, 16, 8], probability=0.5, observed=True,
                     confidence=None, uncertainty=unknown),
                dict(index=[36, 16, 8], probability=0.5, observed=False,
                     confidence=None, uncertainty=unknown)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('--mode', choices=('enabled', 'disabled', 'unclassified'), default='enabled')
    parser.add_argument('--application-client', action='store_true')
    args = parser.parse_args()
    rospy.init_node('local_map_query_checker', disable_signals=True)
    snapshots, events, queries, checks, errors, clocks = [], [], [], [], [], []
    subscribers = [
        rospy.Subscriber('/uav/map/snapshot', MapSnapshot,
                         lambda msg: snapshots.append(from_ros_snapshot(msg)), queue_size=100),
        rospy.Subscriber('/uav/perf/events', PerfEvent,
                         lambda msg: events.append(msg), queue_size=100),
        rospy.Subscriber('/clock', Clock, lambda msg: clocks.append(msg.clock.to_nsec()), queue_size=100)]
    publisher = rospy.Publisher('/uav/perception/occupancy', OccupancyObservation, queue_size=100)
    clock_publisher = rospy.Publisher('/clock', Clock, queue_size=100)
    published = []
    application_results = []

    def require(condition, name):
        checks.append(dict(name=name, passed=bool(condition)))
        if not condition:
            raise AssertionError(name)

    def wait(condition, label):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.01)
        raise RuntimeError('timeout: ' + label)

    def query(stamp=100 * MS, point=(8.25, .25, .25), **overrides):
        fields = dict(map_id='perf01a-local', frame_id='odom', run_id=args.run_id,
                      clock_id='sim:' + args.run_id, query_timestamp=stamp,
                      point=list(point), max_age_ns=50 * MS)
        fields.update(overrides)
        result = from_ros_query_result(service(MapQueryRequest(**fields)).result)
        queries.append(dict(request=fields, result=result))
        return result

    def publish(value):
        count = len(events)
        publisher.publish(to_ros_occupancy(value))
        published.append(copy.deepcopy(value))
        wait(lambda: len(events) > count, 'map receipt event')
        return events[-1]

    def advance(stamp):
        clock_publisher.publish(Clock(clock=rospy.Time(stamp // 1_000_000_000,
                                                     stamp % 1_000_000_000)))
        wait(lambda: clocks and clocks[-1] == stamp, 'fixture clock receipt')

    try:
        wait(lambda: publisher.get_num_connections() == 1
             and rospy.get_param('/perf01a_mapping/ready', '') == args.run_id, 'mapping readiness')
        require(sys.executable == '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python', 'Conda Python')
        if args.mode == 'disabled':
            try:
                rospy.wait_for_service('/uav/map/query', timeout=0.3)
            except rospy.ROSException:
                require(True, 'query disabled has no service')
            else:
                require(False, 'query disabled has no service')
            publish(fixture(args.run_id, 0, 100 * MS))
            wait(lambda: len(snapshots) == 1, 'disabled snapshot')
            require(snapshots[0]['revision'] == 1, 'disabled query retains snapshot updates')
        else:
            rospy.wait_for_service('/uav/map/query', timeout=5)
            service = rospy.ServiceProxy('/uav/map/query', MapQuery)
            empty = query()
            require(empty['status'] == 'unavailable' and empty['probability'] is None
                    and empty['last_observed_timestamp'] is None, 'empty map unavailable')
            foreign = fixture('foreign-' + args.run_id, 0, 50 * MS)
            event = publish(foreign)
            require(event.status == 'unavailable' and not snapshots
                    and query()['reason'] == 'map_unavailable', 'foreign run cannot seed map')
            advance(100 * MS)
            initial = fixture(args.run_id, 1, 100 * MS)
            publish(initial)
            wait(lambda: len(snapshots) == 1, 'initial snapshot')
            expected_status = 'unknown' if args.mode == 'unclassified' else 'occupied'
            occupied = query()
            require(occupied['status'] == expected_status and occupied['revision'] == 1
                    and occupied['index'] == [48, 16, 8]
                    and abs(occupied['probability'] - .9) < 1e-6, 'occupied geometry and probability')
            require(occupied['confidence'] is None and occupied['uncertainty']['status'] == 'unavailable'
                    and occupied['uncertainty']['source'] == 'query fixture unknown', 'unknown quality retained')
            free = query(point=(4.25, .25, .25))
            require(free['status'] == ('unknown' if args.mode == 'unclassified' else 'free')
                    and abs(free['probability'] - .1) < 1e-6 and free['confidence'] == .25
                    and free['uncertainty']['value'] == [.125], 'explicit free and known quality')
            middle = query(point=(6.25, .25, .25))
            require(middle['status'] == 'unknown' and middle['observed'], 'middle probability unknown')
            missing = query(point=(2.25, .25, .25))
            require(missing['status'] == 'unknown' and not missing['observed']
                    and missing['probability'] is None, 'unobserved voxel is not free')
            require(query(point=(16., .25, .25))['reason'] == 'outside_coverage', 'half-open coverage upper edge')
            outside = query(point=(1e308, .25, .25))
            require(outside['status'] == 'unknown' and outside['reason'] == 'outside_coverage'
                    and outside['index'] is None and outside['probability'] is None,
                    'large finite point outside coverage')
            for fields in (dict(map_id='other'), dict(frame_id='map'),
                           dict(run_id='other'), dict(clock_id='host:other')):
                result = query(**fields)
                require(result['status'] == 'unavailable' and result['probability'] is None,
                        'identity mismatch ' + next(iter(fields)))
            require(query(stamp=99 * MS)['reason'] == 'query_before_latest_map_time', 'reject historical query')
            advance(150 * MS)
            require(query(stamp=150 * MS)['status'] == expected_status, 'age equal to max is fresh')
            advance(151 * MS)
            stale = query(stamp=151 * MS)
            require(stale['status'] == 'stale' and stale['last_observed_timestamp'] == 100 * MS
                    and stale['revision'] == 1, 'no observations ages without revision refresh')
            event = publish(initial)
            require(event.reason == 'observation_not_fused' and query(stamp=151 * MS)['revision'] == 1,
                    'duplicate does not refresh map')
            gap = fixture(args.run_id, 2, 160 * MS)
            gap['header'].update(status='unavailable', reason='fixture_sensor_gap')
            gap['voxels'] = []
            publish(gap)
            require(query(stamp=160 * MS)['status'] == 'stale' and len(snapshots) == 1,
                    'unavailable input keeps history stale')
            for bad in (dict(max_age_ns=-1), dict(stamp=-1), dict(point=(float('nan'), 0, 0)),
                        dict(run_id='')):
                try:
                    query(**bad)
                except rospy.ServiceException as exc:
                    require('invalid_map_query' in str(exc), 'invalid request explicitly rejected')
                else:
                    require(False, 'invalid request explicitly rejected')
            advance(200 * MS)
            recovered = fixture(args.run_id, 3, 200 * MS)
            publish(recovered)
            wait(lambda: len(snapshots) == 2, 'recovered snapshot')
            result = query(stamp=200 * MS)
            require(result['status'] == expected_status and result['revision'] == 2
                    and result['last_observed_timestamp'] == 200 * MS, 'new observation restores freshness')
            with ThreadPoolExecutor(max_workers=4) as pool:
                replies = list(pool.map(lambda _: query(stamp=200 * MS), range(12)))
            require(all(row['revision'] == 2 and row['status'] == expected_status for row in replies),
                    'concurrent service readers agree')
            require(len(snapshots[-1]['cells']) == 3
                    and snapshots[-1]['header']['source_type'] == 'derived'
                    and snapshots[-1]['source_types'] == ['fixture'], 'snapshot observed domain and sources')
            if args.mode == 'unclassified':
                require(result['reason'] == 'classification_thresholds_unconfigured', 'no guessed thresholds')
            if args.application_client:
                root = Path(__file__).resolve().parents[1]
                sys.path.insert(0, str(root / 'application'))
                from ufm_application import MapQueryClient, QueryTransportError
                def transport(fields):
                    try:
                        return from_ros_query_result(service(MapQueryRequest(**fields)).result)
                    except rospy.ServiceException as exc:
                        raise QueryTransportError(str(exc)) from exc
                client = MapQueryClient(transport)
                for expected, changes in (('occupied', {}), ('free', dict(point=[4.25, .25, .25])),
                        ('unknown', dict(point=[2.25, .25, .25])),
                        ('stale', dict(query_timestamp=251 * MS)),
                        ('unavailable', dict(clock_id='foreign'))):
                    fields = dict(map_id='perf01a-local', frame_id='odom', run_id=args.run_id,
                        clock_id='sim:' + args.run_id, query_timestamp=200 * MS,
                        point=[8.25, .25, .25], max_age_ns=50 * MS)
                    fields.update(changes)
                    raw = transport(fields)
                    response = client.query(**fields)
                    application_results.append(dict(request=fields, result=response))
                    require(response == raw and response['status'] == expected,
                            'application preserves public query ' + expected)
                command = [sys.executable, str(root / 'ros_ws/map_query_client.py'),
                    '--run-id', args.run_id, '--clock-id', 'sim:' + args.run_id,
                    '--timestamp-ns', str(200 * MS), '--max-age-ns', str(50 * MS),
                    '--point', '8.25', '.25', '.25']
                for missing in (False, True):
                    reply = subprocess.run(command + (['--service', '/uav/map/query_missing']
                        if missing else []), capture_output=True, text=True, timeout=8.)
                    payload = json.loads(reply.stdout)
                    application_results.append(dict(cli=True, service_missing=missing, result=payload))
                    require(reply.returncode == int(missing) and payload['status'] == (
                        'unavailable' if missing else 'occupied'), 'standalone application CLI ' + str(missing))
                    if missing:
                        require(payload['probability'] is None and not payload['observed'],
                                'missing service is not free')
        import rosgraph
        system = rosgraph.Master(rospy.get_name()).getSystemState()
        with (args.run / 'graph.json').open('x') as handle:
            json.dump(system, handle, indent=2)
        validate_mapping_graph(system, rospy.get_name())
        require(True, 'mapping only consumes occupancy and public clock; unique fixture clock')
    except Exception as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    finally:
        for subscriber in subscribers:
            subscriber.unregister()
        publisher.unregister()
        clock_publisher.unregister()
        rospy.signal_shutdown('query fixture finished')
        with (args.run / 'receipts.json').open('x') as handle:
            json.dump(dict(published=published, snapshots=snapshots, queries=queries, clocks=clocks,
                           application_results=application_results,
                           events=[dict(sample_id=e.sample_id, status=e.status, reason=e.reason) for e in events]),
                      handle, indent=2)
        report = dict(passed=not errors and all(c['passed'] for c in checks), mode=args.mode,
                      python=sys.executable, checks=checks, errors=errors,
                      snapshot_count=len(snapshots), query_count=len(queries), published_count=len(published))
        report['application_result_count'] = len(application_results)
        with (args.run / 'validation.json').open('x') as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
