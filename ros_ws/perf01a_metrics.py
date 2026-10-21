"""PERF-01-A事件聚合、身份闭合与百分位统计；不依赖ROS。"""
import math
import os
import resource
import time
from collections import Counter, defaultdict


STAGES = ("radar_receive", "infrared_receive", "sensor_bundle_ready",
          "occupancy_ready", "map_snapshot_publish")


def percentile(values, ratio):
    values = sorted(float(value) for value in values)
    if not values:
        return None
    if ratio <= 0 or ratio > 1:
        raise ValueError("ratio must be in (0, 1]")
    # 冻结为nearest-rank，避免引入numpy及平台差异。
    rank = max(1, int(math.ceil(ratio * len(values))))
    return values[rank - 1]


def percentile_set(values):
    return {"p50": percentile(values, .50), "p95": percentile(values, .95),
            "p99": percentile(values, .99), "count": len(values)}


def resource_snapshot():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return dict(pid=os.getpid(), python=os.sys.executable, monotonic_ns=time.monotonic_ns(),
                user_seconds=usage.ru_utime, system_seconds=usage.ru_stime,
                maxrss_kb=usage.ru_maxrss)


class PerfAggregator:
    """收集PerfEvent字典并在关闭时输出可复核的fixture报告。"""
    def __init__(self, run_id):
        self.run_id = run_id
        self.started_ns = time.monotonic_ns()
        self.events = []
        self.status_counts = Counter()
        self.stage_counts = Counter()
        self._sample_parent = {}
        self._first = defaultdict(dict)
        self._values = defaultdict(list)
        self.errors = []
        self._event_ids = {}

    def record(self, event):
        if event.get("run_id") != self.run_id:
            self.errors.append("event_run_mismatch")
            return
        monotonic_ns = event.get("monotonic_ns")
        if type(monotonic_ns) is not int or monotonic_ns < 0:
            self.errors.append("event_monotonic_invalid")
            return
        # ROS回调跨节点到达顺序不作为业务时序；各事件自身的monotonic_ns在报告中排序。
        sample_id = event.get("sample_id", "")
        parent = event.get("parent_sample_id", "")
        if not sample_id:
            self.errors.append("event_sample_id_missing")
            return
        if event.get('clock_id') != 'sim:' + self.run_id:
            self.errors.append('event_clock_mismatch')
            return
        if sample_id in self._event_ids:
            self.errors.append('duplicate_event' if self._event_ids[sample_id] == event
                               else 'event_identity_conflict')
            return
        self._event_ids[sample_id] = dict(event)
        self._sample_parent[sample_id] = parent
        status = event.get("status", "")
        stage = event.get("stage", "")
        self.status_counts[status] += 1
        self.stage_counts[stage] += 1
        self.events.append(dict(event))
        if status == "valid":
            self._first[(sample_id, stage)].setdefault("event", event)
        metric = event.get("metric_value_ns", -1)
        if type(metric) is int and metric >= 0 and status == "valid":
            self._values[stage].append(metric)

    def _root(self, sample_id):
        seen = set()
        current = sample_id
        while self._sample_parent.get(current):
            if current in seen:
                return current
            seen.add(current)
            current = self._sample_parent[current]
        return current

    def _sample_stages(self):
        rows = defaultdict(dict)
        for (sample_id, stage), value in self._first.items():
            rows[self._root(sample_id)][stage] = value["event"]
        return rows

    def report(self, finished_ns=None):
        finished_ns = finished_ns or time.monotonic_ns()
        rows = self._sample_stages()
        latency = {"sync_wait_ns": [], "sensor_to_occupancy_ns": [],
                   "occupancy_to_map_ns": [], "sensor_to_map_ns": []}
        complete = 0
        missing = Counter()
        radar_roots = set()
        for root, stages in rows.items():
            if "radar_receive" in stages:
                radar_roots.add(root)
            required = ("radar_receive", "sensor_bundle_ready", "occupancy_ready",
                        "map_snapshot_publish")
            for stage in required:
                if stage not in stages:
                    missing[stage] += 1
            if all(stage in stages for stage in required):
                radar = stages["radar_receive"]["monotonic_ns"]
                bundle = stages["sensor_bundle_ready"]["monotonic_ns"]
                occupancy = stages["occupancy_ready"]["monotonic_ns"]
                mapped = stages["map_snapshot_publish"]["monotonic_ns"]
                if not radar <= bundle <= occupancy <= mapped:
                    self.errors.append('stage_time_regression')
                    continue
                complete += 1
                latency["sync_wait_ns"].append(bundle - radar)
                latency["sensor_to_occupancy_ns"].append(occupancy - radar)
                latency["occupancy_to_map_ns"].append(mapped - occupancy)
                latency["sensor_to_map_ns"].append(mapped - radar)
        unique = len(radar_roots)
        closed = complete
        rejected_roots = {self._root(e['sample_id']) for e in self.events
                          if e['status'] in ('timeout', 'duplicate', 'out_of_order', 'unavailable')}
        explicit_rejections = len(rejected_roots & radar_roots)
        report = dict(run_id=self.run_id, scope="PERF-01-A fixture placeholder only",
                      event_count=len(self.events), stage_counts=dict(self.stage_counts),
                      status_counts=dict(self.status_counts), unique_radar_samples=unique,
                      closed_samples=closed, missing_stages=dict(missing),
                      identity_closure_rate=(float(closed) / unique if unique else None),
                      drop_rate=(float(max(0, unique - closed)) / unique
                                 if unique else None),
                      drop_rate_semantics='observed radar roots without a complete valid map event chain',
                      explicit_rejections=explicit_rejections,
                      timeout_count=self.status_counts["timeout"],
                      duplicate_count=self.status_counts["duplicate"],
                      out_of_order_count=self.status_counts["out_of_order"],
                      unavailable_count=self.status_counts["unavailable"],
                      latency_percentiles={key: percentile_set(value)
                                           for key, value in latency.items()},
                      metric_percentiles={key: percentile_set(value)
                                          for key, value in self._values.items()},
                      wall_duration_ns=max(0, finished_ns - self.started_ns),
                      resources=resource_snapshot(), errors=list(dict.fromkeys(self.errors)))
        return report
