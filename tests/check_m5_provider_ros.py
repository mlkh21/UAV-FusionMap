"""Independent actual terrain service/clock probes plus unchanged occupancy service."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_terrain_msgs.msg import TerrainStatus
from uav_fusionmap_terrain_msgs.srv import TerrainQuery
from uav_fusionmap_msgs.msg import MapSnapshot, OccupancyObservation, PerfEvent
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import to_ros_occupancy, from_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result
from ufm_terrain_contract.codec import from_ros, from_ros_response, to_ros
from check_local_map_query_ros import fixture

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('run_id')
    args = parser.parse_args()
    rospy.init_node('m5_terrain_checker', disable_signals=True)
    states, snapshots, checks, queries, graphs = [], [], [], [], []
    errors, callbacks = [], []
    def receive_status(msg):
        try: states.append(from_ros('TerrainStatus', msg))
        except Exception as exc: callbacks.append(str(exc))
    subscribers = [rospy.Subscriber('/uav/terrain/v1/status', TerrainStatus, receive_status, queue_size=20),
        rospy.Subscriber('/uav/map/snapshot', MapSnapshot, lambda m: snapshots.append(from_ros_snapshot(m)), queue_size=2),
        rospy.Subscriber('/uav/perf/events', PerfEvent, lambda m: None, queue_size=10)]
    occupancy = rospy.Publisher('/uav/perception/occupancy', OccupancyObservation, queue_size=2)
    clock_pub = rospy.Publisher('/clock', Clock, queue_size=1)
    clock_state = dict(stamp=99, pause=True)
    stop = threading.Event()
    def clock_loop():
        while not stop.is_set():
            if not clock_state['pause']:
                clock_pub.publish(Clock(clock=rospy.Time(0, clock_state['stamp'])))
            stop.wait(.04)
    worker = threading.Thread(target=clock_loop)
    worker.start()

    def require(condition, name):
        checks.append(dict(name=name, passed=bool(condition)))
        if not condition: raise AssertionError(name)

    def wait(predicate, name):
        deadline = time.monotonic() + 7.
        while time.monotonic() < deadline:
            if callbacks: raise AssertionError('codec callback: ' + repr(callbacks))
            if predicate(): return
            time.sleep(.02)
        raise RuntimeError('timeout: ' + name)

    def advance(stamp, state):
        clock_state.update(stamp=stamp, pause=False)
        wait(lambda: states and states[-1]['evaluation_timestamp'] == stamp and states[-1]['state'] == state, 'clock/state ' + state)

    def query(stamp=100, **changes):
        req = dict(terrain_id='m5-terrain-fixture', run_id=args.run_id, clock_id='sim:' + args.run_id,
            frame_id='map', query_timestamp=stamp, point_xy=[111., 179.], pin_version=False,
            expected_provider_instance_id='', expected_terrain_revision=0)
        req.update(changes)
        response = rospy.ServiceProxy('/uav/terrain/v1/query', TerrainQuery)(to_ros('TerrainQueryRequest', req))
        row = from_ros_response(response, request=req)
        queries.append(dict(request=req, result=row))
        return row

    def old_query():
        response = rospy.ServiceProxy('/uav/map/query', MapQuery)(MapQueryRequest(map_id='perf01a-local',
            frame_id='odom', run_id=args.run_id, clock_id='sim:' + args.run_id,
            query_timestamp=100, point=[8.25, .25, .25], max_age_ns=100))
        return from_ros_query_result(response.result)

    def graph(label):
        system = rospy.get_master().getSystemState()[2]
        subscriptions = {t for t, nodes in system[1] if '/terrain_provider' in nodes}
        require(subscriptions == {'/clock'}, 'terrain clock-only subscriptions ' + label)
        require(not any('lidar' in t.lower() or 'training' in t.lower() or t in ('/tf', '/tf_static')
                        for t, nodes in system[0] + system[1]), 'no supervision or TF side channel ' + label)
        require({t for t, nodes in system[2] if t.startswith('/uav/terrain/')} == {'/uav/terrain/v1/query'}, 'no install endpoint ' + label)
        graphs.append(dict(label=label, system=system))

    rogue = None
    try:
        rospy.wait_for_service('/uav/terrain/v1/query', timeout=8.)
        rospy.wait_for_service('/uav/map/query', timeout=8.)
        wait(lambda: states and occupancy.get_num_connections(), 'initial connection')
        require(query()['reason'] == 'clock_unavailable', 'waiting for actual clock')
        advance(99, 'empty')
        require(query(99)['reason'] == 'terrain_unavailable', 'authorization not started')
        occupancy.publish(to_ros_occupancy(fixture(args.run_id, 0, 100)))
        wait(lambda: snapshots, 'old occupancy snapshot')
        old = old_query()
        require(old['status'] == 'occupied' and old['revision'] == 1, 'old occupancy query before terrain install')
        advance(100, 'current')
        first = query()
        instance = first['provider_instance_id']
        require(first['height'] == 13 and first['context']['installed_timestamp'] == 100, 'installed fixed height')
        for point, expected_height, expected_status in (([111.,179.],13.,'valid'), ([113.,179.],14.,'valid'),
                ([111.,177.],None,'unknown'), ([113.,177.],1.,'valid'), ([115.,179.],None,'unknown')):
            row = query(point_xy=point)
            require((row['status'], row['height']) == (expected_status, expected_height), 'sample/no-data/coverage ' + str(point))
        for changes, code in ((dict(frame_id='odom'), 'request_domain_mismatch'), (dict(run_id='other'), 'request_domain_mismatch'),
            (dict(clock_id='sim:other'), 'request_domain_mismatch'), (dict(terrain_id='other'), 'request_domain_mismatch'),
            (dict(query_timestamp=101), 'query_ahead_of_clock'),
            (dict(pin_version=True, expected_provider_instance_id='old', expected_terrain_revision=1), 'provider_instance_mismatch'),
            (dict(pin_version=True, expected_provider_instance_id=instance, expected_terrain_revision=2), 'revision_mismatch')):
            stamp = changes.pop('query_timestamp', 100)
            row = query(stamp, **changes)
            require(row['reason'] == code and row['height'] is None and row['context'] is None, code)
        for point in ([111.1, 179.], [float('nan'), 179.]):
            req = to_ros('TerrainQueryRequest', dict(terrain_id='m5-terrain-fixture', run_id=args.run_id,
                clock_id='sim:' + args.run_id, frame_id='map', query_timestamp=100, point_xy=[111.,179.],
                pin_version=False, expected_provider_instance_id='', expected_terrain_revision=0))
            req.point_xy = point
            try: rospy.ServiceProxy('/uav/terrain/v1/query', TerrainQuery)(req)
            except rospy.ServiceException as exc: require('invalid_request' in str(exc), 'stable invalid request')
            else: raise AssertionError('invalid request accepted')
        graph('current')
        sequence = states[-1]['status_sequence']
        clock_state['pause'] = True
        wait(lambda: states[-1]['reason'] == 'clock_transport_unavailable', 'clock transport timeout')
        require(query()['reason'] == 'clock_transport_unavailable', 'service timeout gate')
        require(states[-1]['status_sequence'] > sequence, 'wall heartbeat advances during pause')
        require(old_query() == old, 'terrain timeout preserves old occupancy result')
        advance(100, 'current')
        require(query()['context'] == first['context'], 'clock pause/resume does not refresh evidence')
        peer_log = (args.run / 'clock-peer.log').open('x')
        rogue = subprocess.Popen([sys.executable, '-B', str(ROOT / 'tests/m5_clock_peer.py')],
                                  stdout=peer_log, stderr=subprocess.STDOUT)
        wait(lambda: len(dict(rospy.get_master().getSystemState()[2][0]).get('/clock', [])) == 2, 'second clock publisher')
        require(query()['reason'] == 'clock_source_mismatch', 'multiple/unexpected clock rejected')
        rogue.send_signal(signal.SIGINT)
        rogue.wait(timeout=4.)
        peer_log.close()
        wait(lambda: states[-1]['state'] == 'current', 'source recovery with fresh expected clock')
        require(query()['status'] == 'valid', 'foreign reset value never adopted')
        advance(200, 'expired')
        require(query()['status'] == 'stale' and query()['height'] == 13., 'evaluation expires historical query')
        require(query(point_xy=[111.,177.])['height'] is None, 'expired no-data remains missing')
        advance(300, 'unavailable')
        require(query()['reason'] == 'registration_unavailable' and query()['height'] is None, 'current registration gates history')
        advance(99, 'locked')
        advance(120, 'locked')
        require(query()['reason'] == 'clock_reset_new_run_required', 'reset stays locked after clock increases')
        (args.run / 'restart-request.json').write_text(json.dumps(dict(old_instance=instance)))
        new_run = args.run_id + '-recovery'
        wait(lambda: states[-1]['provider_instance_id'] != instance and states[-1]['state'] == 'current', 'new run recovery')
        fresh = query(120, run_id=new_run, clock_id='sim:' + new_run)
        require(fresh['terrain_revision'] == 1 and fresh['provider_instance_id'] != instance and fresh['height'] == 13., 'new instance revision one')
        require(query(120, run_id=new_run, clock_id='sim:' + new_run, pin_version=True,
                      expected_provider_instance_id=instance, expected_terrain_revision=1)['reason'] == 'provider_instance_mismatch', 'old pin rejected after restart')
        require(query(120)['reason'] == 'request_domain_mismatch', 'new run never rebinds old request')
        graph('recovered')
        (args.run / 'stop-request.json').write_text('{}')
        wait(lambda: '/uav/terrain/v1/query' not in dict(rospy.get_master().getSystemState()[2][2]), 'terrain service removed')
        require(old_query() == old and len(snapshots) == 1, 'terrain shutdown preserves old occupancy')
    except Exception as exc:
        errors.append(type(exc).__name__ + ':' + str(exc))
    finally:
        if rogue is not None and rogue.poll() is None:
            rogue.send_signal(signal.SIGINT)
            try: rogue.wait(timeout=3.)
            except subprocess.TimeoutExpired:
                rogue.kill()
                rogue.wait(timeout=2.)
        stop.set()
        worker.join(2.)
        for sub in subscribers: sub.unregister()
        occupancy.unregister()
        clock_pub.unregister()
    (args.run / 'receipts.json').write_text(json.dumps(dict(statuses=states, queries=queries, snapshots=snapshots, graphs=graphs), indent=2))
    (args.run / 'validation.json').write_text(json.dumps(dict(passed=not errors, errors=errors, checks=checks,
        query_count=len(queries), status_count=len(states), old_snapshot_count=len(snapshots)), indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
