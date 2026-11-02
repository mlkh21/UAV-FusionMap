"""Independent online observer for fail-closed perception modes."""
import json
import os
from pathlib import Path
import sys
import time
import xmlrpc.client

import rospy
from uav_fusionmap_msgs.msg import (InfraredFrame, MapSnapshot, OccupancyObservation,
                                    PerfEvent, SensorBundle)
from uav_fusionmap_msgs.srv import MapQuery, MapQueryRequest
from ufm_ros_contract.perf01a_codec import from_ros_bundle, from_ros_occupancy, from_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros_ws'))
from online_graph_audit import validate_online_graph
from perception_mode_validation import validate_unavailable_mode


def main():
    run, run_id, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    rospy.init_node('perception_mode_checker', disable_signals=True)
    bundles, observations, snapshots, events = [], [], [], []
    subscribers = [
        rospy.Subscriber('/uav/sensors/infrared', InfraredFrame,
                         lambda msg: None, queue_size=100),
        rospy.Subscriber('/uav/sensors/bundle', SensorBundle,
                         lambda msg: bundles.append(from_ros_bundle(msg)), queue_size=100),
        rospy.Subscriber('/uav/perception/occupancy', OccupancyObservation,
                         lambda msg: observations.append(from_ros_occupancy(msg)), queue_size=100),
        rospy.Subscriber('/uav/map/snapshot', MapSnapshot,
                         lambda msg: snapshots.append(from_ros_snapshot(msg)), queue_size=100),
        rospy.Subscriber('/uav/perf/events', PerfEvent,
                         lambda msg: events.append({key: getattr(msg, key) for key in msg.__slots__})
                         if msg.stage == 'map_snapshot_publish' else None, queue_size=100),
    ]
    errors, graph, query, expected = [], None, {}, None
    try:
        deadline = time.monotonic() + 24
        while time.monotonic() < deadline:
            if rospy.get_param('/perf01a_source/done', '') == run_id:
                expected = rospy.get_param('/perf01a_source/expected_samples')
                break
            time.sleep(.02)
        else:
            raise RuntimeError('source completion timeout')
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if len(bundles) >= expected and len(observations) >= expected and len(events) >= expected:
                break
            time.sleep(.02)
        else:
            errors.append('downstream receipts incomplete after drain')
        state = xmlrpc.client.ServerProxy(os.environ['ROS_MASTER_URI']).getSystemState(
            '/perception_mode_checker')
        if state[0] != 1:
            raise RuntimeError('ROS graph unavailable: ' + str(state[1]))
        graph = validate_online_graph(state[2][0], state[2][1], expected_nodes=(
            '/perception_mode_checker', '/perf01a_source', '/perf01a_sensor',
            '/perf01a_perception', '/perf01a_mapping'))
        rospy.wait_for_service('/uav/map/query', timeout=3)
        service = rospy.ServiceProxy('/uav/map/query', MapQuery)
        query = from_ros_query_result(service(MapQueryRequest(
            map_id='perf01a-local', frame_id='odom', run_id=run_id, clock_id='sim:' + run_id,
            query_timestamp=expected * 50_000_000, point=[8.25, 0.25, 0.25],
            max_age_ns=50_000_000)).result)
        errors.extend(validate_unavailable_mode(run_id, mode, expected, bundles,
                                                 observations, events, snapshots, query, graph))
    except (Exception, KeyboardInterrupt) as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    finally:
        for subscriber in subscribers:
            subscriber.unregister()
        report = dict(run_id=run_id, mode=mode, python=sys.executable, expected=expected,
                      bundle_count=len(bundles), occupancy_count=len(observations),
                      map_event_count=len(events), snapshot_count=len(snapshots),
                      graph=graph, query=query, errors=errors, passed=not errors)
        for name, value in (('receipts.json', dict(bundles=bundles, observations=observations,
                                                 events=events, snapshots=snapshots)),
                            ('validation.json', report)):
            with (run / name).open('x') as handle:
                json.dump(value, handle, indent=2)
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
