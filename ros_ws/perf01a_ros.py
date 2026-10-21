"""PERF-01-A ROS薄包装共享工具。"""
import time

from uav_fusionmap_msgs.msg import PerfEvent
from ufm_ros_contract import to_ros_state


def publish_perf_event(publisher, run_id, parent_sample_id, stage, business_timestamp,
                       metric_value_ns=0, status="valid", reason=""):
    event = PerfEvent()
    event.run_id = run_id
    event.parent_sample_id = parent_sample_id
    event.sample_id = "%s:perf:%s:%d" % (parent_sample_id, stage, time.monotonic_ns())
    event.stage = stage
    event.monotonic_ns = time.monotonic_ns()
    event.metric_value_ns = max(0, int(metric_value_ns))
    event.business_timestamp = int(business_timestamp)
    event.clock_id = "sim:" + run_id
    event.status = status
    event.reason = reason
    publisher.publish(event)


def state_message(state):
    return to_ros_state(state)
