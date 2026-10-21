#!/usr/bin/env python
"""PERF-01-A placeholder perception ROS节点；不加载研究模型/GPU/LiDAR。"""
import sys
import time

import rospy
from uav_fusionmap_msgs.msg import OccupancyObservation, SensorBundle

from ufm_perception.placeholder import placeholder_infer
from ufm_ros_contract.perf01a_codec import from_ros_bundle, to_ros_occupancy
from ufm_ros_contract.perf01a_ros import PerfTrace, publish_perf_event
from ufm_ros_contract.perf01a_wire import WireAudit


def main():
    if not sys.executable.endswith("/Radar-Diffusion/bin/python"):
        raise RuntimeError("PERF-01-A必须使用Radar-Diffusion Python")
    rospy.init_node("perf01a_placeholder_perception")
    run_id = rospy.get_param("~run_id")
    rolling_grid = rospy.get_param('~rolling_grid', False)
    segmented = rospy.get_param('/perf01a_segmented_timing', False)
    receive_type = SensorBundle
    if rospy.get_param('/perf01a_receive_backend', 'standard') == 'numpy':
        from ufm_ros_contract.perf01a_numpy_receive import numpy_list_receive_type
        receive_type = numpy_list_receive_type(SensorBundle)
    audit = WireAudit.for_node('perception')
    audit.install(receive_type, 'deserialize')
    occupancy_pub = rospy.Publisher("/uav/perception/occupancy", OccupancyObservation, queue_size=100)
    event_pub = rospy.Publisher("/uav/perf/events", __import__("uav_fusionmap_msgs.msg", fromlist=["PerfEvent"]).PerfEvent,
                                queue_size=500)

    def receive(msg):
        started = time.monotonic_ns()
        audit.record('callback:SensorBundle', msg, callback_ns=started)
        trace = PerfTrace(segmented)
        trace.mark('bundle_callback', started)
        bundle = trace.call('bundle_decode', from_ros_bundle, msg)
        sample_id = bundle["header"]["sample_id"]
        try:
            occupancy = trace.call('perception', placeholder_infer, bundle,
                                   rolling_grid=rolling_grid)
            publish_perf_event(event_pub, run_id, sample_id, "occupancy_ready",
                               occupancy["header"]["timestamp"], time.monotonic_ns() - started,
                               status=occupancy['header']['status'], reason=occupancy['header']['reason'])
            encoded = trace.call('occupancy_encode', to_ros_occupancy, occupancy)
            trace.call('occupancy_publish', occupancy_pub.publish, encoded)
        except Exception as exc:
            publish_perf_event(event_pub, run_id, sample_id, "occupancy_ready",
                               bundle["header"]["timestamp"], status="unavailable",
                               reason=type(exc).__name__ + ":" + str(exc))
        trace.flush(event_pub, run_id, sample_id, bundle['header']['timestamp'])

    rospy.Subscriber("/uav/sensors/bundle", receive_type, receive, queue_size=100,
                     buff_size=int(rospy.get_param('/perf01a_image_buff_size', 65536)))
    deadline = time.monotonic() + 15.0
    while not (event_pub.get_num_connections() and occupancy_pub.get_num_connections()):
        if time.monotonic() > deadline or rospy.is_shutdown():
            raise RuntimeError('perception subscribers not ready')
        time.sleep(.02)
    rospy.set_param('~ready', run_id)
    rospy.spin()


if __name__ == "__main__":
    main()
