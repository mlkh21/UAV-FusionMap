#!/usr/bin/env python
"""Independent Radar or IR producer driven by the shared simulation clock."""
import heapq
from pathlib import Path
import sys
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import InfraredFrame, RadarFrame

from ufm_ros_contract.perf01a_codec import to_ros_infrared, to_ros_radar
from ufm_ros_contract.perf01a_wire import WireAudit
from ufm_sensors.perf01a_fixture import make_fake_infrared, make_fake_radar, make_motion_radar

# Catkin devel relays set __file__ to the source but do not export helper names.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from perf01a_async_common import AuditNode, report_error, run_node, wait_ready, write_audit


class Producer(AuditNode):
    def __init__(self):
        super().__init__()
        from ufm_sensors.perf01a_async import make_schedule
        self.kind = rospy.get_param('~kind')
        if self.kind not in ('radar', 'infrared'):
            raise ValueError('kind must be radar or infrared')
        self.endpoint_probe = bool(rospy.get_param('/perf01a_endpoint_probe', False))
        self.wire_audit = WireAudit.for_node(self.kind) if self.kind == 'infrared' else None
        if self.wire_audit is not None:
            self.wire_audit.install(InfraredFrame, 'serialize')
        self.schedule = sorted(make_schedule(self.profile, self.duration_ns)[self.kind],
                               key=lambda row: (row['timestamp_ns'], row['sequence']))
        self.rows = []
        self.pending = []
        self.capacity = self.profile.get('producer_capacity', 16)
        if type(self.capacity) is not int or self.capacity < 1:
            raise ValueError('producer_capacity must be a positive integer')
        self.pending_high_water = 0
        self.overflow_count = 0
        self.clock_ns = None
        self.last_clock_wall = time.monotonic()
        self.complete = False
        self.publisher = rospy.Publisher('/uav/sensors/' + self.kind,
            RadarFrame if self.kind == 'radar' else InfraredFrame, queue_size=self.capacity)
        self.clock_sub = rospy.Subscriber('/clock', Clock, self.receive_clock, queue_size=1000)
        rospy.on_shutdown(self.shutdown)

    def start(self):
        wait_ready(lambda: self.publisher.get_num_connections() >= 1 and
                   self.clock_sub.get_num_connections() >= 1, self.stop)
        rospy.set_param('~ready', self.run_id)
        self.start_worker(self.produce)

    def receive_clock(self, msg):
        try:
            with self.lock:
                stamp = msg.clock.to_nsec()
                if self.clock_ns is not None and stamp < self.clock_ns:
                    raise ValueError('clock_regression')
                self.clock_ns = stamp
                self.last_clock_wall = time.monotonic()
        except Exception as exc:
            self.fail(exc)

    def produce(self):
        index = 0
        while not self.stop.is_set() and not rospy.is_shutdown():
            with self.lock:
                clock_ns = self.clock_ns
                last_clock_wall = self.last_clock_wall
            if time.monotonic() - last_clock_wall > 15.0:
                raise RuntimeError('producer clock stalled')
            if clock_ns is None:
                self.stop.wait(.001)
                continue
            # Interleave historical generation and delivery when the worker falls behind.
            while not self.stop.is_set():
                next_sample = (self.schedule[index]['timestamp_ns']
                               if index < len(self.schedule) else None)
                if (self.pending and self.pending[0][0] <= clock_ns and
                        (next_sample is None or self.pending[0][0] <= next_sample)):
                    self.publish_next()
                elif next_sample is not None and next_sample <= clock_ns:
                    self.generate(self.schedule[index])
                    index += 1
                else:
                    break
            if index == len(self.schedule) and not self.pending:
                self.complete = True
                self.save()
                rospy.set_param('~done', self.run_id)
                return
            self.stop.wait(.001)

    def generate(self, plan):
        if not plan['drop'] and len(self.pending) >= self.capacity:
            self.discard_overflow()
        generated = time.monotonic_ns()
        sensor_seed = self.profile.get('sensor_noise_seed', self.profile.get('seed', 0))
        radar_options = self.profile.get('fake_radar', {})
        infrared_options = self.profile.get('fake_infrared', {})
        if self.kind == 'radar':
            if self.profile.get('speed_mps', 0):
                frame = make_motion_radar(self.run_id, plan['sequence'], plan['timestamp_ns'],
                                         self.profile['speed_mps'], self.profile['obstacles_odom'],
                                         seed=sensor_seed, **radar_options)
            else:
                frame = make_fake_radar(self.run_id, plan['sequence'], plan['timestamp_ns'],
                                       point=(4.0, 0.0, 0.0), seed=sensor_seed,
                                       **radar_options)
        else:
            width, height = self.profile.get('ir_resolution', [2, 2])
            frame = make_fake_infrared(self.run_id, plan['sequence'],
                                      plan['timestamp_ns'], width, height,
                                      seed=sensor_seed, **infrared_options)
        row = dict(sample_id=frame['header']['sample_id'], sequence=plan['sequence'],
            timestamp_ns=plan['timestamp_ns'], arrival_ns=plan['arrival_ns'],
            drop=bool(plan['drop']), generated_monotonic_ns=generated,
            publish_monotonic_ns=None, published=False,
            reason='planned_drop' if plan['drop'] else '')
        if self.endpoint_probe:
            row.update(capture_monotonic_ns=None, capture_clock_status='unavailable',
                       capture_timestamp_ns=None)
        self.rows.append(row)
        if not row['drop']:
            heapq.heappush(self.pending, (row['arrival_ns'], row['sequence'], frame, row))
            self.pending_high_water = max(self.pending_high_water, len(self.pending))

    def discard_overflow(self):
        _, _, frame, row = heapq.heappop(self.pending)
        row['reason'] = 'producer_overflow'
        row['discard_monotonic_ns'] = time.monotonic_ns()
        del frame
        self.overflow_count += 1
        message = 'producer_overflow: ' + row['sample_id']
        self.errors.append(message)
        report_error(self.run_id, RuntimeError(message))

    def publish_next(self):
        _, _, frame, row = heapq.heappop(self.pending)
        encode = to_ros_radar if self.kind == 'radar' else to_ros_infrared
        message = encode(frame)
        row['publish_monotonic_ns'] = time.monotonic_ns()
        self.publisher.publish(message)
        row['published'] = True

    def save(self):
        if not self.saved:
            write_audit(self.directory, self.kind + '-audit.json',
                        dict(run_id=self.run_id, kind=self.kind, rows=self.rows, errors=self.errors,
                             stats=dict(producer_capacity=self.capacity,
                                        pending_high_water=self.pending_high_water,
                                        producer_overflow=self.overflow_count)))
            self.saved = True

    def shutdown(self):
        self.stop_worker()
        try:
            if not self.complete:
                self.errors.append('shutdown_before_producer_done')
            self.save()
        except Exception as exc:
            self.fail(exc)


if __name__ == '__main__':
    run_node('perf01a_radar', Producer)
