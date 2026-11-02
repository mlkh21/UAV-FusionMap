"""PERF-01-A ROS薄包装共享工具。"""
import time

from uav_fusionmap_msgs.msg import PerfEvent


def perf_publisher(rospy):
    if not rospy.get_param('/ufm_diagnostics_enabled', True):
        return None
    return rospy.Publisher('/uav/perf/events', PerfEvent, queue_size=500)


class PerfTrace:
    """先保存时间戳，业务发布完成后再发送旁路事件。"""
    def __init__(self, enabled):
        self.enabled = enabled
        self.spans = []

    def mark(self, stage, stamp):
        if self.enabled:
            self.spans.append((stage, stamp, stamp))

    def call(self, stage, function, *args, **kwargs):
        if not self.enabled:
            return function(*args, **kwargs)
        start = time.monotonic_ns()
        result = function(*args, **kwargs)
        self.spans.append((stage, start, time.monotonic_ns()))
        return result

    def flush(self, publisher, run_id, parent, timestamp):
        for stage, start, end in self.spans:
            publish_perf_event(publisher, run_id, parent, 'timing.' + stage,
                               timestamp, end - start, monotonic_ns=end)


def publish_perf_event(publisher, run_id, parent_sample_id, stage, business_timestamp,
                       metric_value_ns=0, status="valid", reason="", monotonic_ns=None):
    if publisher is None:
        return
    event = PerfEvent()
    event.run_id = run_id
    event.parent_sample_id = parent_sample_id
    event.sample_id = "%s:perf:%s:%d" % (parent_sample_id, stage, time.monotonic_ns())
    event.stage = stage
    event.monotonic_ns = time.monotonic_ns() if monotonic_ns is None else monotonic_ns
    event.metric_value_ns = max(0, int(metric_value_ns))
    event.business_timestamp = int(business_timestamp)
    event.clock_id = "sim:" + run_id
    event.status = status
    event.reason = reason
    publisher.publish(event)
