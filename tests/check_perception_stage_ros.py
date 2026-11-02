"""P3 software handoff: output refusal, busy/late ordering, timeout and recovery."""
import json
from pathlib import Path
import sys
import time

import rospy
import rosgraph
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import MapSnapshot, OccupancyObservation, PerfEvent, SensorBundle
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import (from_ros_occupancy, from_ros_snapshot,
                                         to_ros_bundle)
from ufm_ros_contract.query_codec import from_ros_query_result
from online_graph_audit import validate_online_graph
from test_perf01a_contract import valid_bundle


def main():
    run, run_id = Path(sys.argv[1]), sys.argv[2]
    rospy.init_node('p3_stage_checker', disable_signals=True)
    observations, snapshots, events, published, queries, errors = [], [], [], [], [], []
    subscribers = [
        rospy.Subscriber('/uav/perception/occupancy', OccupancyObservation,
                         lambda msg: observations.append(from_ros_occupancy(msg)), queue_size=100),
        rospy.Subscriber('/uav/map/snapshot', MapSnapshot,
                         lambda msg: snapshots.append(from_ros_snapshot(msg)), queue_size=100),
        rospy.Subscriber('/uav/perf/events', PerfEvent,
                         lambda msg: events.append(dict(parent=msg.parent_sample_id, stage=msg.stage,
                             status=msg.status, reason=msg.reason)), queue_size=100),
    ]
    source = rospy.Publisher('/uav/sensors/bundle', SensorBundle, queue_size=10)
    clock = rospy.Publisher('/clock', Clock, queue_size=10)
    graph = None

    def wait(predicate, label, seconds=4.):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.01)
        raise RuntimeError('timeout: ' + label)

    def send(sequence, suffix=''):
        stamp = sequence * 100_000_000
        bundle = valid_bundle(run_id=run_id, radar_timestamp=stamp)
        bundle['header']['sample_id'] += ':' + str(sequence) + suffix
        clock.publish(Clock(clock=rospy.Time(stamp // 1_000_000_000, stamp % 1_000_000_000)))
        source.publish(to_ros_bundle(bundle))
        published.append(bundle)
        return bundle['header']['sample_id']

    def receipt(identity, status):
        expected = 'perception.occupancy:' + identity
        wait(lambda: any(row['header']['sample_id'] == expected for row in observations), identity)
        wait(lambda: any(row['parent'] == identity and row['stage'] == 'map_snapshot_publish'
                         for row in events), 'map event: ' + identity)
        result = next(row for row in observations if row['header']['sample_id'] == expected)
        if result['header']['status'] != status:
            raise AssertionError('occupancy status: ' + str(result['header']))
        return result

    def query(sequence, revision, status, last_stamp):
        request = dict(map_id='perf01a-local', frame_id='odom', run_id=run_id,
                       clock_id='sim:' + run_id, query_timestamp=sequence * 100_000_000,
                       point=[8.25, .25, .25], max_age_ns=50_000_000)
        result = from_ros_query_result(service(MapQueryRequest(**request)).result)
        queries.append(dict(request=request, result=result))
        if (result['revision'], result['status'], result['last_observed_timestamp']) != (
                revision, status, last_stamp):
            raise AssertionError('map evidence changed unexpectedly: ' + str(result))

    try:
        wait(lambda: source.get_num_connections() == 1 and
             all(rospy.get_param('/perf01a_' + role + '/ready', '') == run_id
                 for role in ('perception', 'mapping')), 'business ready')
        rospy.wait_for_service('/uav/map/query', timeout=3.)
        service = rospy.ServiceProxy('/uav/map/query', MapQuery)
        receipt(send(1), 'valid')
        query(1, 1, 'occupied', 100_000_000)
        bad = receipt(send(2, ':bad-output'), 'unavailable')
        if bad['voxels'] or 'backend output' not in bad['header']['reason']:
            raise AssertionError('bad backend output was not refused')
        query(2, 1, 'stale', 100_000_000)
        receipt(send(3), 'valid')
        old_id = send(4, ':slow')
        # The test submits another input while the deliberately slow job is active.
        time.sleep(.05)
        busy = receipt(send(5), 'unavailable')
        if busy['header']['reason'] != 'perception_backend_busy':
            raise AssertionError('capacity overflow not explicit')
        until = time.monotonic() + 1.1
        while time.monotonic() < until:
            time.sleep(.02)
        if any(row['header']['sample_id'] == 'perception.occupancy:' + old_id for row in observations):
            raise AssertionError('superseded old result was published')
        query(5, 2, 'stale', 300_000_000)
        receipt(send(6), 'valid')
        timeout = receipt(send(7, ':slow'), 'unavailable')
        if timeout['header']['reason'] != 'perception_backend_timeout' or timeout['voxels']:
            raise AssertionError('execution deadline not explicit')
        query(7, 3, 'stale', 600_000_000)
        receipt(send(8), 'valid')
        wait(lambda: len(snapshots) == 4, 'four successful map revisions')
        query(8, 4, 'occupied', 800_000_000)
        state = rosgraph.Master(rospy.get_name()).getSystemState()
        graph = validate_online_graph(state[0], state[1], expected_nodes=(
            '/p3_stage_checker', '/perf01a_perception', '/perf01a_mapping'))
        errors.extend(graph['errors'])
        for node, allowed in (('/perf01a_mapping', {'/clock', '/uav/perception/occupancy'}),
                              ('/perf01a_perception', {'/clock', '/uav/sensors/bundle'})):
            actual = {topic for topic, nodes in state[1] if node in nodes}
            if actual - allowed:
                errors.append('cross-layer subscriptions: ' + node)
        if len(observations) != 7 or len(snapshots) != 4:
            errors.append('unexpected output count')
    except (Exception, KeyboardInterrupt) as exc:
        errors.append(type(exc).__name__ + ':' + str(exc))
    finally:
        for subscriber in subscribers:
            subscriber.unregister()
        for name, value in (('receipts.json', dict(published=published, observations=observations,
                snapshots=snapshots, events=events, queries=queries)),
                ('validation.json', dict(passed=not errors, errors=errors, graph=graph,
                    observations=len(observations), snapshots=len(snapshots),
                    python=sys.executable, scope='P3 software CPU fixture only'))):
            with (run / name).open('x') as handle:
                json.dump(value, handle, indent=2)
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
