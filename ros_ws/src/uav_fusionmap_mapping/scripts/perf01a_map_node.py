#!/usr/bin/env python
"""PERF-01-A稀疏Local Map ROS节点；仅消费OccupancyObservation。"""
import sys
import time
import json
from pathlib import Path
import threading

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import MapSnapshot, OccupancyObservation
from uav_fusionmap_msgs.srv import MapQuery, MapQueryResponse

from ufm_mapping.local_map import SparseLocalMap
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, to_ros_snapshot
from ufm_ros_contract.perf01a_ros import PerfTrace, publish_perf_event
from ufm_ros_contract.query_codec import from_ros_query_request, to_ros_query_result


def main():
    if not sys.executable.endswith("/Radar-Diffusion/bin/python"):
        raise RuntimeError("PERF-01-A必须使用Radar-Diffusion Python")
    rospy.init_node("perf01a_mapping")
    run_id = rospy.get_param("~run_id")
    segmented = rospy.get_param('/perf01a_segmented_timing', False)
    map_id = rospy.get_param("~map_id", "perf01a-local")
    local_map = SparseLocalMap(map_id=map_id,
                               staleness_limit_ns=int(rospy.get_param("~staleness_limit_ns", 100_000_000)),
                               max_active_cells=int(rospy.get_param("~max_active_cells", 10000)),
                               free_threshold=rospy.get_param('~free_threshold', None),
                               occupied_threshold=rospy.get_param('~occupied_threshold', None),
                               rolling_enabled=rospy.get_param('~rolling_enabled', False))
    snapshot_pub = rospy.Publisher("/uav/map/snapshot", MapSnapshot, queue_size=100)
    event_pub = rospy.Publisher("/uav/perf/events", __import__("uav_fusionmap_msgs.msg", fromlist=["PerfEvent"]).PerfEvent,
                                queue_size=500)
    lock = threading.RLock()

    def query(request):
        with lock:
            try:
                result = local_map.query(**from_ros_query_request(request))
            except ValueError as exc:
                raise rospy.ServiceException('invalid_map_query: ' + str(exc))
            return MapQueryResponse(result=to_ros_query_result(result))

    if rospy.get_param('~enable_query', False):
        rospy.Service('/uav/map/query', MapQuery, query)
    aging_directory = rospy.get_param('/perf01a_map_audit_directory', '')
    aging_rows = []
    clock_ns = [None]

    def record_age():
        if not aging_directory or clock_ns[0] is None:
            return
        snapshot = local_map.snapshot()
        aging_rows.append(dict(query_timestamp=clock_ns[0], revision=snapshot['revision'],
            cells=[dict(index=c['index'], timestamp=c['last_observed_timestamp'],
                        probability=c['probability'], observed=c['observed']) for c in snapshot['cells']],
            stale=[list(index) for index in local_map.stale_cells(clock_ns[0])]))

    def receive_clock(msg):
        with lock:
            clock_ns[0] = msg.clock.to_nsec()
            if clock_ns[0] % 20_000_000 == 0:
                record_age()

    def save_aging():
        with lock:
            with (Path(aging_directory) / 'map-aging.json').open('x') as handle:
                json.dump(dict(run_id=run_id, staleness_limit_ns=local_map.staleness_limit_ns,
                               rows=aging_rows), handle, indent=2)

    if aging_directory:
        rospy.Subscriber('/clock', Clock, receive_clock, queue_size=1000)
        rospy.on_shutdown(save_aging)

    def receive(msg):
        started = time.monotonic_ns()
        trace = PerfTrace(segmented)
        trace.mark('occupancy_callback', started)
        observation = trace.call('occupancy_decode', from_ros_occupancy, msg)
        sample_id = observation["header"]["sample_id"]
        prefix = "perception.occupancy:"
        parent = sample_id[len(prefix):] if sample_id.startswith(prefix) else sample_id
        try:
            if observation['header']['run_id'] != run_id:
                raise ValueError('occupancy run differs from configured node run')
            if not trace.call('map_update', local_map.update, observation):
                publish_perf_event(event_pub, run_id, parent, 'map_snapshot_publish',
                    observation['header']['timestamp'], status='unavailable',
                    reason='observation_not_fused')
                trace.flush(event_pub, run_id, parent, observation['header']['timestamp'])
                return
            snapshot = trace.call('map_snapshot', local_map.snapshot)
            record_age()
            encoded = trace.call('map_encode', to_ros_snapshot, snapshot)
            trace.call('map_publish', snapshot_pub.publish, encoded)
            publish_perf_event(event_pub, run_id, parent, "map_snapshot_publish",
                               snapshot["header"]["timestamp"], time.monotonic_ns() - started)
        except Exception as exc:
            publish_perf_event(event_pub, run_id, parent, "map_snapshot_publish",
                               observation["header"]["timestamp"], status="unavailable",
                               reason=type(exc).__name__ + ":" + str(exc))
        trace.flush(event_pub, run_id, parent, observation['header']['timestamp'])

    def receive_locked(msg):
        with lock:
            receive(msg)

    rospy.Subscriber("/uav/perception/occupancy", OccupancyObservation, receive_locked, queue_size=100)
    deadline = time.monotonic() + 15.0
    while not (event_pub.get_num_connections() and snapshot_pub.get_num_connections()):
        if time.monotonic() > deadline or rospy.is_shutdown():
            raise RuntimeError('mapping subscribers not ready')
        time.sleep(.02)
    rospy.set_param('~ready', run_id)
    rospy.spin()


if __name__ == "__main__":
    main()
