#!/usr/bin/env python
"""PERF-01-A短fixture观察器：旁路订阅PerfEvent，不参与业务闭环。"""
import json
import sys
import time
from pathlib import Path

import rospy
from uav_fusionmap_msgs.msg import PerfEvent

from perf01a_metrics import PerfAggregator, resource_snapshot


def main():
    if not sys.executable.endswith("/Radar-Diffusion/bin/python"):
        raise RuntimeError("PERF-01-A必须使用Radar-Diffusion Python")
    rospy.init_node("perf01a_observer")
    run_id = rospy.get_param("~run_id")
    output = Path(rospy.get_param("~output"))
    if output.exists():
        raise FileExistsError(str(output))
    duration_s = float(rospy.get_param("~duration_s", 10.0))
    aggregator = PerfAggregator(run_id)
    rospy.Subscriber("/uav/perf/events", PerfEvent,
                     lambda msg: aggregator.record(dict(run_id=msg.run_id,
                         sample_id=msg.sample_id, parent_sample_id=msg.parent_sample_id,
                         stage=msg.stage, monotonic_ns=msg.monotonic_ns,
                         metric_value_ns=msg.metric_value_ns,
                         business_timestamp=msg.business_timestamp,
                         clock_id=msg.clock_id, status=msg.status, reason=msg.reason)),
                     queue_size=1000)
    resource_start = resource_snapshot()
    time.sleep(duration_s)
    report = aggregator.report()
    report["observer_resource_start"] = resource_start
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    rospy.signal_shutdown("perf01a observer complete")


if __name__ == "__main__":
    main()
