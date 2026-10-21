"""Independent ROS rolling fixture: bundle -> placeholder -> map -> snapshot/query."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import MapSnapshot, OccupancyObservation, PerfEvent, SensorBundle
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, from_ros_snapshot, to_ros_bundle
from ufm_ros_contract.query_codec import from_ros_query_result

from check_local_map_query_ros import validate_mapping_graph
from test_perf01a_contract import valid_bundle


def wait(predicate, label):
    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise RuntimeError('timeout: ' + label)


def motion_bundle(run_id, stamp, body, point=None, yaw=0.0):
    cosine, sine = math.cos(yaw), math.sin(yaw)
    if point is None:
        relative = (0., 0., 0.)
    else:
        dx, dy = point[0] - body[0], point[1] - body[1]
        relative = (cosine * dx + sine * dy, -sine * dx + cosine * dy, point[2] - body[2])
    bundle = valid_bundle(run_id=run_id, radar_timestamp=stamp, point=relative)
    bundle['radar']['header']['sample_id'] += ':' + str(stamp)
    bundle['infrared']['header']['sample_id'] += ':' + str(stamp)
    bundle['header']['sample_id'] = 'sensors.bundle:' + bundle['radar']['header']['sample_id']
    transform = [cosine, -sine, 0., body[0], sine, cosine, 0., body[1],
                 0., 0., 1., body[2], 0., 0., 0., 1.]
    bundle['context']['T_mapping_source'] = transform
    bundle['context']['T_mapping_body'] = list(transform)
    if point is None:
        bundle['radar']['points'] = []
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('--mode', choices=('rolling',), required=True)
    args = parser.parse_args()
    rospy.init_node('local_map_rolling_checker', disable_signals=True)
    snapshots, occupancies, events, queries, checks, errors = [], [], [], [], [], []
    subscribers = [
        rospy.Subscriber('/uav/map/snapshot', MapSnapshot,
                         lambda msg: snapshots.append(from_ros_snapshot(msg)), queue_size=100),
        rospy.Subscriber('/uav/perception/occupancy', OccupancyObservation,
                         lambda msg: occupancies.append(from_ros_occupancy(msg)), queue_size=100),
        rospy.Subscriber('/uav/perf/events', PerfEvent, lambda msg: events.append(msg), queue_size=100),
    ]
    source = rospy.Publisher('/uav/sensors/bundle', SensorBundle, queue_size=100)
    clock = rospy.Publisher('/clock', Clock, queue_size=100)

    def check(condition, label):
        checks.append(dict(name=label, passed=bool(condition)))
        if not condition:
            raise AssertionError(label)

    def query(stamp, point=(2.25, .25, .25), **kwargs):
        fields = dict(map_id='perf01a-local', frame_id='odom', run_id=args.run_id,
                      clock_id='sim:' + args.run_id, query_timestamp=stamp,
                      point=list(point), max_age_ns=50_000_000)
        fields.update(kwargs)
        value = from_ros_query_result(service(MapQueryRequest(**fields)).result)
        queries.append(dict(request=fields, result=value))
        return value

    def publish(stamp, body, point=None, yaw=0., valid=True, expect_snapshot=True):
        bundle = motion_bundle(args.run_id, stamp, body, point, yaw)
        if not valid:
            bundle['header'].update(status='unavailable', reason='fixture_gap')
        before_occupancy, before_snapshots = len(occupancies), len(snapshots)
        before_events = len(events)
        clock.publish(Clock(clock=rospy.Time(stamp // 1_000_000_000,
                                            stamp % 1_000_000_000)))
        source.publish(to_ros_bundle(bundle))
        wait(lambda: len(occupancies) > before_occupancy, 'occupancy receipt')
        wait(lambda: any(row.stage == 'map_snapshot_publish' for row in events[before_events:]),
             'mapping receipt')
        if expect_snapshot:
            wait(lambda: len(snapshots) > before_snapshots, 'snapshot receipt')
        else:
            check(len(snapshots) == before_snapshots, 'invalid or duplicate does not publish')
        return bundle

    try:
        wait(lambda: source.get_num_connections() == 1
             and rospy.get_param('/perf01a_mapping/ready', '') == args.run_id
             and rospy.get_param('/perf01a_perception/ready', '') == args.run_id,
             'perception and mapping ready')
        rospy.wait_for_service('/uav/map/query', timeout=5)
        service = rospy.ServiceProxy('/uav/map/query', MapQuery)
        check(sys.executable == '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python',
              'Conda interpreter')
        check(query(100_000_000)['status'] == 'unavailable', 'empty map unavailable')
        first = publish(100_000_000, (0., 0., 0.), (2.25, .25, .25))
        check(snapshots[-1]['origin'] == [-16., -8., -4.] and
              query(100_000_000)['status'] == 'occupied', 'initial cell known')
        publish(110_000_000, (.5, 0., 0.))
        moved = snapshots[-1]
        retained = query(110_000_000)
        check(moved['origin'] == [-15.5, -8., -4.] and moved['revision'] == 2 and
              retained['index'] == [35, 16, 8] and
              retained['last_observed_timestamp'] == 100_000_000,
              'rolling origin and overlap keep physical cell')
        check(query(110_000_000, point=(16.25, .25, .25))['reason'] == 'no_observation',
              'entered area is unknown')
        publish(120_000_000, (.5, 0., 0.), (2.25, .25, .25), yaw=math.pi / 2)
        check(occupancies[-1]['voxels'][0]['index'] == [35, 16, 8] and
              query(120_000_000)['last_observed_timestamp'] == 120_000_000,
              'turn keeps odom geometry')
        publish(130_000_000, (1., 0., 0.), valid=False, expect_snapshot=False)
        check(snapshots[-1]['revision'] == 3 and query(171_000_000)['status'] == 'stale',
              'gap neither rolls nor refreshes historical cell')
        before = len(snapshots)
        source.publish(to_ros_bundle(first))
        wait(lambda: any(row.stage == 'map_snapshot_publish' and row.reason.startswith('ValueError:')
                         for row in events), 'old arrival rejected')
        check(len(snapshots) == before, 'old timestamp does not republish')
        publish(180_000_000, (40., 0., 0.))
        check(snapshots[-1]['origin'][0] == 24. and snapshots[-1]['cells'] == [] and
              query(180_000_000, (40.25, .25, .25))['status'] == 'unknown',
              'large move evicts all history and leaves unknown')
        publish(190_000_000, (40., 0., 0.), (41.25, .25, .25))
        check(query(190_000_000, (41.25, .25, .25))['status'] == 'occupied',
              'recover only explicitly observed area')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: query(190_000_000, (41.25, .25, .25)), range(12)))
        check(all(row['revision'] == 5 and row['status'] == 'occupied' for row in results),
              'concurrent reads agree on one revision')
        import rosgraph
        graph = rosgraph.Master(rospy.get_name()).getSystemState()
        validate_mapping_graph(graph, rospy.get_name())
        subscribers_perception = {topic for topic, nodes in graph[1]
                                  if '/perf01a_perception' in nodes}
        check(subscribers_perception <= {'/uav/sensors/bundle', '/clock'} and
              '/uav/sensors/bundle' in subscribers_perception,
              'perception and mapping do not subscribe across layers')
        with (args.run / 'graph.json').open('x') as handle:
            json.dump(graph, handle, indent=2)
    except Exception as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    finally:
        for subscriber in subscribers:
            subscriber.unregister()
        source.unregister()
        clock.unregister()
        rospy.signal_shutdown('rolling fixture finished')
        with (args.run / 'receipts.json').open('x') as handle:
            json.dump(dict(snapshots=snapshots, occupancies=occupancies, queries=queries,
                           events=[dict(stage=row.stage, status=row.status, reason=row.reason)
                                   for row in events]), handle, indent=2)
        report = dict(passed=not errors and all(row['passed'] for row in checks),
                      checks=checks, errors=errors, python=sys.executable,
                      snapshot_count=len(snapshots), occupancy_count=len(occupancies),
                      query_count=len(queries))
        with (args.run / 'validation.json').open('x') as handle:
            json.dump(report, handle, indent=2)
    if errors:
        raise RuntimeError('; '.join(errors))


if __name__ == '__main__':
    main()
