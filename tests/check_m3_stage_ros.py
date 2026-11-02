"""Synthetic M3 ROS acceptance: receipts and independent queries, not model inference."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import MapSnapshot, OccupancyObservation, PerfEvent
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, from_ros_snapshot, to_ros_occupancy
from ufm_ros_contract.query_codec import from_ros_query_result
from m3_fixture import load_spec, interval_quality
from m3_motion_fixture import motion_observation
from check_local_map_query_ros import validate_mapping_graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'application'))
from ufm_application import MapQueryClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('run_id')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('m3_stage_checker', disable_signals=True)
    profile_spec = load_spec(args.run / 'm3-config.yaml')
    spec = profile_spec['arithmetic']
    snapshots, events, observations, queries, outcomes, checks = [], [], [], [], [], []
    errors = []
    subscribers = [
        rospy.Subscriber('/uav/map/snapshot', MapSnapshot,
                         lambda msg: snapshots.append(from_ros_snapshot(msg)), queue_size=100),
        rospy.Subscriber('/uav/perf/events', PerfEvent, lambda msg: events.append(msg), queue_size=100)]
    publisher = rospy.Publisher('/uav/perception/occupancy', OccupancyObservation, queue_size=100)
    clock = rospy.Publisher('/clock', Clock, queue_size=100)
    clock_times = []

    def advance(stamp):
        # The fixture clock is independent of rejected/late observation timestamps.
        if not clock_times or stamp > clock_times[-1]:
            clock_times.append(stamp)
            clock.publish(Clock(clock=rospy.Time(stamp // 1_000_000_000, stamp % 1_000_000_000)))

    def require(condition, name):
        checks.append(dict(name=name, passed=bool(condition)))
        if not condition:
            raise AssertionError(name)

    def wait(condition, label):
        deadline = time.monotonic() + 6.
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(.01)
        raise RuntimeError('timeout: ' + label)

    def query(stamp, status, probability=None, point=(8.25, .25, .25), bounds=None, **changes):
        advance(stamp)
        request = dict(map_id=spec['map_id'], frame_id='odom', run_id=args.run_id,
            clock_id='sim:' + args.run_id, query_timestamp=stamp, max_age_ns=999_000_000,
            point=list(point))
        request.update(changes)
        result = client.query(**request)
        queries.append(dict(request=request, result=result))
        require(result['status'] == status, 'query status ' + status)
        require((result['probability'] is None if probability is None else
                 result['probability'] is not None and abs(result['probability'] - probability) < 1e-6),
                'query probability ' + str(probability))
        quality = result['uncertainty']
        require(result['confidence'] is None, 'confidence is not synthesized')
        if bounds is None:
            require(quality['status'] == 'unavailable' and quality['value'] is None,
                    'missing quality remains unavailable')
            if result['observed']:
                require(quality['source'] == profile_spec['interval_profile']['unavailable_source'],
                        'missing interval provenance retained')
        else:
            require(quality['status'] == 'available' and quality['kind'] ==
                    'occupancy_probability_interval' and quality['unit'] == 'dimensionless' and
                    quality['source'] == profile_spec['interval_profile']['output_source'],
                    'conditional interval metadata retained')
            require(len(quality['value']) == 2 and all(abs(a - b) < 1e-12 for a, b in
                    zip(quality['value'], bounds)), 'independent expected interval endpoints')
        return result

    def send(row, outcome, revision, evidence_time):
        count, snapshot_count = len(events), len(snapshots)
        wire = to_ros_occupancy(row)
        observations.append(from_ros_occupancy(wire))
        if outcome != 'rejected':
            advance(row['header']['timestamp'])
        publisher.publish(wire)
        wait(lambda: len(events) > count, 'map receipt')
        event = events[-1]
        actual = ('fused' if event.status == 'valid' else
                  'not_fused' if event.reason == 'observation_not_fused' else 'rejected')
        outcomes.append(actual)
        require(actual == outcome, 'observation outcome ' + outcome)
        if outcome == 'fused':
            wait(lambda: len(snapshots) == snapshot_count + 1, 'map snapshot')
        require(len(snapshots) == revision, 'snapshot count and revision')
        if snapshots:
            require(snapshots[-1]['revision'] == revision and
                    snapshots[-1]['header']['timestamp'] == evidence_time, 'evidence time retained')

    def row(index, kind='occupied', stamp=None, **kwargs):
        return motion_observation(profile_spec, args.run_id, index, kind=kind, stamp=stamp, **kwargs)

    try:
        wait(lambda: publisher.get_num_connections() == 1 and
             rospy.get_param('/perf01a_mapping/ready', '') == args.run_id, 'mapping ready')
        rospy.wait_for_service('/uav/map/query', timeout=5.)
        service = rospy.ServiceProxy('/uav/map/query', MapQuery)
        client = MapQueryClient(lambda request: from_ros_query_result(
            service(MapQueryRequest(**request)).result))
        require(rospy.get_param('/perf01a_mapping/resolved_map_backend') == 'm3_fixture',
                'explicit backend selected')
        query(0, 'unavailable')
        first = row(0)
        first['voxels'].append(dict(copy.deepcopy(first['voxels'][0]), index=[40, 16, 8], probability=.25))
        first['voxels'][-1]['uncertainty'] = interval_quality(profile_spec, ['1/5', '3/10'])
        send(first, 'fused', 1, 10_000_000)
        query(10_000_000, 'occupied', .75, bounds=(.7, .8))
        query(10_000_000, 'free', .25, point=(4.25, .25, .25), bounds=(.2, .3))
        query(10_000_000, 'unknown', point=(2.25, .25, .25))
        second = row(1)
        send(second, 'fused', 2, 20_000_000)
        query(20_000_000, 'occupied', .9, bounds=(49/58, .9))
        send(second, 'not_fused', 2, 20_000_000)
        conflict = copy.deepcopy(second)
        conflict['voxels'][0]['probability'] = .25
        send(conflict, 'rejected', 2, 20_000_000)
        gap = row(2, 'unavailable', body=(40., 0., 0.), origin=(24., -8., -4.))
        gap['context']['T_mapping_body_status'] = 'unavailable'
        gap['context']['T_mapping_body'] = [0.] * 16
        send(gap, 'not_fused', 2, 20_000_000)
        send(row(3, stamp=25_000_000), 'rejected', 2, 20_000_000)
        bad = row(4, stamp=200_000_000, body=(.5, 0., 0.))
        bad['voxels'].append(dict(copy.deepcopy(bad['voxels'][0]), index=[40, 16, 8]))
        bad['voxels'][-1]['uncertainty']['unit'] = 'm2'
        send(bad, 'rejected', 2, 20_000_000)
        query(20_000_000, 'occupied', .9, bounds=(49/58, .9))
        send(row(5, stamp=40_000_000, body=(.5, 0., 0.), yaw=1.5707963267948966,
                 origin=(-15., -8., -4.)), 'fused', 3, 40_000_000)
        boundary = query(140_000_000, 'occupied', .9, bounds=(.9, .9))
        require(boundary['index'] == [47, 16, 8], 'same world cell after shift and yaw')
        send(row(6, 'empty', stamp=150_000_000, body=(1., 0., 0.)), 'fused', 4, 40_000_000)
        query(140_000_000, 'unavailable')
        stale = query(150_000_000, 'stale', .9, bounds=(.9, .9))
        require(stale['last_observed_timestamp'] == 40_000_000, 'empty move cannot refresh TTL')
        send(row(7, stamp=160_000_000, body=(1., 0., 0.)), 'fused', 5, 160_000_000)
        query(160_000_000, 'occupied', .75, bounds=(.7, .8))
        wrong_domain = row(8, stamp=170_000_000, body=(1., 0., 0.))
        wrong_domain['observed_domain_source'] = 'old_placeholder_fixture'
        send(wrong_domain, 'rejected', 5, 160_000_000)
        query(170_000_000, 'occupied', .75, bounds=(.7, .8))
        send(row(9, 'free', stamp=180_000_000, body=(1., 0., 0.)), 'fused', 6, 180_000_000)
        require(query(180_000_000, 'unknown', .5, bounds=(7/19, 12/19))['observed'],
                'conflict unknown remains observed')
        send(row(10, 'free', stamp=190_000_000, body=(1., 0., 0.)), 'fused', 7, 190_000_000)
        query(190_000_000, 'free', .25, bounds=(7/55, 36/85))
        send(row(11, 'empty', stamp=200_000_000, body=(40., 0., 0.),
                 origin=(24., -8., -4.)), 'fused', 8, 190_000_000)
        require(not query(200_000_000, 'unknown', point=(40.25, .25, .25))['observed'], 'new region unknown')
        send(row(12, stamp=210_000_000), 'fused', 9, 210_000_000)
        query(210_000_000, 'occupied', .75, bounds=(.7, .8))
        send(row(13, stamp=220_000_000, bounds=None), 'fused', 10, 220_000_000)
        query(220_000_000, 'occupied', .9)
        send(row(14, 'free', stamp=230_000_000), 'fused', 11, 230_000_000)
        query(330_000_000, 'occupied', .75)
        send(row(15, 'empty', stamp=340_000_000, body=(.5, 0., 0.)),
             'fused', 12, 230_000_000)
        query(340_000_000, 'stale', .75)
        send(row(16, stamp=350_000_000, body=(.5, 0., 0.)), 'fused', 13, 350_000_000)
        query(350_000_000, 'occupied', .75, bounds=(.7, .8))
        cli = subprocess.run([sys.executable, '-B', str(ROOT / 'ros_ws/map_query_client.py'),
            '--map-id', spec['map_id'], '--run-id', args.run_id, '--clock-id', 'sim:' + args.run_id,
            '--timestamp-ns', '350000000', '--max-age-ns', '100000000', '--point', '8.25', '.25', '.25'],
            text=True, capture_output=True, timeout=10)
        cli_result = json.loads(cli.stdout)
        require(cli.returncode == 0 and cli_result['status'] == 'occupied' and
                abs(cli_result['probability'] - .75) < 1e-6 and
                cli_result['uncertainty']['source'] == profile_spec['interval_profile']['output_source'],
                'independent application CLI preserves interval source')
        master = rospy.get_master()
        graph = master.getSystemState()[2]
        subscriptions = validate_mapping_graph(graph, '/m3_stage_checker')
        require(not any('lidar' in topic.lower() or 'training' in topic.lower()
                        for topic, nodes in graph[0] + graph[1]), 'graph excludes training and LiDAR')
        with (args.run / 'graph.json').open('x') as handle:
            json.dump(dict(system=graph, mapping_subscriptions=subscriptions), handle, indent=2)
        with (args.run / 'application-cli.json').open('x') as handle:
            json.dump(dict(result=cli_result, stderr=cli.stderr, exit=cli.returncode), handle, indent=2)
    except Exception as exc:
        errors.append(type(exc).__name__ + ':' + str(exc))
    with (args.run / 'receipts.json').open('x') as handle:
        json.dump(dict(observations=observations, snapshots=snapshots, queries=queries,
                       outcomes=outcomes, clock_times=clock_times,
                       events=[dict(status=item.status, reason=item.reason, stage=item.stage,
                                    parent_sample_id=item.parent_sample_id,
                                    business_timestamp=item.business_timestamp) for item in events]),
                  handle, indent=2)
    with (args.run / 'validation.json').open('x') as handle:
        json.dump(dict(passed=not errors, errors=errors, checks=checks,
            observation_count=len(observations), snapshot_count=len(snapshots), query_count=len(queries),
            application_statuses=sorted({item['result']['status'] for item in queries})), handle, indent=2)
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
