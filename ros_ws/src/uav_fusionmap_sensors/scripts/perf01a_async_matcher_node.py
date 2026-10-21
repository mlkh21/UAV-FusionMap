#!/usr/bin/env python
"""ROS transport and audit wrapper around the sensors bounded matcher."""
from contextlib import contextmanager
from pathlib import Path
import sys
import time

import rospy
from rosgraph_msgs.msg import Clock
from uav_fusionmap_msgs.msg import AircraftState, InfraredFrame, PerfEvent, RadarFrame, SensorBundle

from ufm_ros_contract import from_ros_state, to_ros_state
from ufm_ros_contract.perf01a_codec import from_ros_infrared, from_ros_radar, to_ros_bundle
from ufm_ros_contract.perf01a_ros import PerfTrace, publish_perf_event
from ufm_ros_contract.perf01a_wire import WireAudit
from ufm_sensors.clock_gate import StateClockGate
from ufm_sensors.state_adapter import adapt_state

# Resolve the real helper alongside this script, including under catkin relays.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from perf01a_async_common import AuditNode, run_node, wait_ready, write_audit


class Matcher(AuditNode):
    def __init__(self):
        super().__init__()
        from ufm_sensors.perf01a_async import BoundedMatcher
        self.matcher = BoundedMatcher(self.run_id, self.profile)
        self.gate = StateClockGate(self.run_id)
        self.clock_ns = None
        self.segmented = rospy.get_param('/perf01a_segmented_timing', False)
        self.match_trace = bool(rospy.get_param('/perf01a_match_trace', False))
        self.ir_borrow_image = bool(rospy.get_param('/perf01a_ir_borrow_image', False))
        self.lock_records = []
        self.state_inputs = []
        self.sensor_inputs = []
        self.stage_records = []
        self.worker_polls = []
        self._active_lock = None
        self._trigger = None
        self.wire_audit = WireAudit.for_node('sensor')
        self.wire_audit.install(InfraredFrame, 'deserialize')
        self.wire_audit.install(SensorBundle, 'serialize')
        self.receipts = dict(radar=[], infrared=[])
        self.received_by_id = dict(radar={}, infrared={})
        self.decisions = []
        self.finished = False
        self.gate_high_water = 0
        self.event_pub = rospy.Publisher('/uav/perf/events', PerfEvent, queue_size=500)
        self.bundle_pub = rospy.Publisher('/uav/sensors/bundle', SensorBundle, queue_size=100)
        self.state_pub = rospy.Publisher('/uav/sensors/state', AircraftState, queue_size=100)
        self.subscribers = [
            rospy.Subscriber('/clock', Clock, self.receive_clock, queue_size=1000),
            rospy.Subscriber('/uav/sim/state', AircraftState, self.receive_state, queue_size=100),
            rospy.Subscriber('/uav/sensors/radar', RadarFrame, self.receive_radar, queue_size=100),
            rospy.Subscriber('/uav/sensors/infrared', InfraredFrame, self.receive_infrared,
                queue_size=100, buff_size=int(rospy.get_param('/perf01a_image_buff_size', 65536)),
                tcp_nodelay=bool(rospy.get_param('/perf01a_ir_tcp_nodelay', False))),
        ]
        rospy.on_shutdown(self.shutdown)

    def start(self):
        wait_ready(lambda: self.bundle_pub.get_num_connections() >= 1 and
                   self.event_pub.get_num_connections() >= 1 and
                   all(sub.get_num_connections() >= 1 for sub in self.subscribers), self.stop)
        self.publish_counts()
        rospy.set_param('~ready', self.run_id)
        self.start_worker(self.poll)

    @contextmanager
    def traced_lock(self, role, timestamp=None, sample_id=None):
        entered = time.monotonic_ns() if self.match_trace else None
        with self.lock:
            if not self.match_trace:
                yield
                return
            row = dict(lock_id=len(self.lock_records), role=role, timestamp=timestamp,
                       sample_id=sample_id, entered_ns=entered,
                       acquired_ns=time.monotonic_ns(), cpu_acquired_ns=time.thread_time_ns())
            self.lock_records.append(row)
            previous = self._active_lock
            self._active_lock = row
            try:
                yield
            finally:
                row['cpu_released_ns'] = time.thread_time_ns()
                row['lock_thread_cpu_ns'] = row['cpu_released_ns'] - row['cpu_acquired_ns']
                row['released_ns'] = time.monotonic_ns()
                self._active_lock = previous

    def call_matcher(self, method, *args):
        trace = PerfTrace(self.segmented)
        started = time.monotonic_ns() if self.match_trace else None
        source = method.__name__
        if self.match_trace and source == 'add_state':
            header = args[0]['header']
            self.state_inputs.append(dict(sample_id=header['sample_id'],
                                          timestamp=header['timestamp'], begin_ns=started,
                                          lock_id=self._active_lock['lock_id']))
        if self.match_trace and source in ('add_radar', 'add_infrared'):
            header = args[0]['header']
            self.sensor_inputs.append(dict(kind=source[4:], sample_id=header['sample_id'],
                                           timestamp=header['timestamp'], begin_ns=started,
                                           lock_id=self._active_lock['lock_id']))
        state_input = self.state_inputs[-1] if self.match_trace and source == 'add_state' else None
        sensor_input = self.sensor_inputs[-1] if self.match_trace and source in ('add_radar', 'add_infrared') else None
        previous = self._trigger
        if self.match_trace:
            self._trigger = dict(source=source, begin_ns=started,
                                 lock_id=self._active_lock['lock_id'])
        try:
            decisions = self.stage_call('matcher.' + source, trace.call, 'pairing', method, *args)
            if state_input is not None:
                state_input['matcher_end_ns'] = time.monotonic_ns()
            if sensor_input is not None:
                sensor_input['matcher_end_ns'] = time.monotonic_ns()
            for decision in decisions or []:
                self.stage_call('decision.emit', self.emit, decision, trace,
                                sample_id=decision['radar']['header']['sample_id'])
        finally:
            if state_input is not None:
                state_input['end_ns'] = time.monotonic_ns()
            if sensor_input is not None:
                sensor_input['end_ns'] = time.monotonic_ns()
            self._trigger = previous

    def stage_call(self, name, method, *args, sample_id=None):
        if not self.match_trace:
            return method(*args)
        started = time.monotonic_ns()
        cpu_started = time.thread_time_ns()
        try:
            return method(*args)
        finally:
            cpu_end = time.thread_time_ns()
            end = time.monotonic_ns()
            self.stage_records.append(dict(name=name, sample_id=sample_id,
                lock_id=self._active_lock['lock_id'], start_ns=started, end_ns=end,
                thread_cpu_start_ns=cpu_started, thread_cpu_end_ns=cpu_end,
                thread_cpu_ns=cpu_end - cpu_started))

    def accept_states(self, states):
        for state in states:
            sample_id = state['header']['sample_id']
            message = self.stage_call('state.encode', to_ros_state, state, sample_id=sample_id)
            self.stage_call('state.publish', self.state_pub.publish, message, sample_id=sample_id)
            self.call_matcher(self.matcher.add_state, state, time.monotonic_ns())

    def receive_state(self, msg):
        try:
            with self.traced_lock('state', msg.header.timestamp, msg.header.sample_id):
                if self.finished or self.stop.is_set():
                    return
                state = self.stage_call('state.adapt', lambda: adapt_state(from_ros_state(msg), {
                    'odom_origin_policy': 'px4_estimator_local_origin',
                    'body_origin_policy': 'source_body_virtual_flu'}), sample_id=msg.header.sample_id)
                states = self.stage_call('gate.consume_state', self.gate.consume_state,
                                         state, time.monotonic(), sample_id=msg.header.sample_id)
                self.accept_states(states)
                self.gate_high_water = max(self.gate_high_water, self.gate.pending_count)
        except Exception as exc:
            self.fail(exc)

    def receive_clock(self, msg):
        try:
            with self.traced_lock('clock', msg.clock.to_nsec()):
                if self.finished or self.stop.is_set():
                    return
                clock_ns = msg.clock.to_nsec()
                states = self.stage_call('gate.consume_clock', self.gate.consume_clock,
                                         clock_ns, time.monotonic())
                self.clock_ns = clock_ns
                self.call_matcher(self.matcher.observe_clock, clock_ns, time.monotonic_ns())
                self.accept_states(states)
        except Exception as exc:
            self.fail(exc)

    def receive_radar(self, msg):
        started = time.monotonic_ns()
        self.receive('radar', msg, started)

    def receive_infrared(self, msg):
        started = time.monotonic_ns()
        self.wire_audit.record('callback:InfraredFrame', msg, callback_ns=started)
        self.receive('infrared', msg, started)

    def receive(self, kind, msg, started):
        try:
            with self.traced_lock(kind, msg.header.timestamp, msg.header.sample_id):
                acquired = time.monotonic_ns()
                row = dict(sample_id=msg.header.sample_id, timestamp=msg.header.timestamp,
                           receive_monotonic_ns=started, receipt_clock_ns=self.clock_ns,
                           lock_wait_ns=acquired - started)
                if self.finished:
                    raise RuntimeError('input received after matcher finish: ' + row['sample_id'])
                self.receipts[kind].append(row)
                self.received_by_id[kind].setdefault(row['sample_id'], row)
                if self.stop.is_set():
                    return
                if msg.header.run_id != self.run_id or msg.header.clock_id != 'sim:' + self.run_id:
                    raise ValueError('input run/clock mismatch')
                decode_start = time.monotonic_ns()
                frame = (from_ros_radar(msg) if kind == 'radar' else
                         from_ros_infrared(msg, borrow_image=self.ir_borrow_image))
                row['decode_ns'] = time.monotonic_ns() - decode_start
                matching_start = time.monotonic_ns()
                if kind == 'radar':
                    publish_perf_event(self.event_pub, self.run_id,
                        'sensors.bundle:' + row['sample_id'], 'radar_receive',
                        row['timestamp'], monotonic_ns=started)
                    self.call_matcher(self.matcher.add_radar, frame, time.monotonic_ns())
                else:
                    self.call_matcher(self.matcher.add_infrared, frame, time.monotonic_ns())
                row['cache_and_emit_ns'] = time.monotonic_ns() - matching_start
        except Exception as exc:
            self.fail(exc)

    def emit(self, decision, pairing_trace, publish=True):
        radar = decision['radar']
        bundle = decision['bundle']
        radar_id = radar['header']['sample_id']
        stamp = radar['header']['timestamp']
        root = 'sensors.bundle:' + radar_id
        decided = time.monotonic_ns()
        infrared_id = bundle['infrared']['header']['sample_id'] if bundle else None
        row = dict(radar_id=radar_id, infrared_id=infrared_id,
            timestamp=stamp, reason=decision['reason'], wait_ns=decision['wait_ns'],
            data_age_ns=decision['data_age_ns'], decision_monotonic_ns=decided,
            decision_clock_ns=self.clock_ns)
        if self.match_trace:
            row['trigger'] = (dict(self._trigger) if self._trigger is not None else
                              dict(source='shutdown', begin_ns=decided, lock_id=None))
        self.decisions.append(row)
        if not publish:
            return
        trace = PerfTrace(self.segmented)
        trace.spans.extend(pairing_trace.spans)
        if bundle is not None:
            ir_receipt = self.received_by_id['infrared'][infrared_id]
            publish_perf_event(self.event_pub, self.run_id, root, 'infrared_receive',
                ir_receipt['timestamp'], monotonic_ns=ir_receipt['receive_monotonic_ns'])
        received = self.received_by_id['radar'][radar_id]['receive_monotonic_ns']
        self.stage_call('decision.ready_event', lambda: publish_perf_event(
            self.event_pub, self.run_id, root, 'sensor_bundle_ready', stamp,
            decided - received, status='valid' if bundle is not None else 'unavailable',
            reason=decision['reason'], monotonic_ns=decided), sample_id=radar_id)
        if bundle is not None:
            message = self.stage_call('bundle.encode', trace.call, 'bundle_encode',
                                      to_ros_bundle, bundle, sample_id=radar_id)
            self.stage_call('bundle.publish', trace.call, 'bundle_publish',
                            self.bundle_pub.publish, message, sample_id=radar_id)
        self.stage_call('decision.flush_events', trace.flush, self.event_pub,
                        self.run_id, root, stamp, sample_id=radar_id)

    def publish_counts(self):
        counts = {kind: len(rows) for kind, rows in self.receipts.items()}
        rospy.set_param('~received', dict(run_id=self.run_id, **counts))
        for kind, count in counts.items():
            rospy.set_param('~received_' + kind, count)
        rospy.set_param('~state_drain', dict(run_id=self.run_id,
            received=self.gate.counters['accepted_states'],
            published=self.gate.counters['published_states'],
            pending=self.gate.pending_count,
            clock_ns=str(self.gate.last_clock_ns if self.gate.last_clock_ns is not None else -1)))

    def poll(self):
        next_status = 0.0
        while True:
            sleep_start = time.monotonic_ns() if self.match_trace else None
            sleep_cpu = time.thread_time_ns() if self.match_trace else None
            stopped = self.stop.wait(.002)
            wake = time.monotonic_ns() if self.match_trace else None
            wake_cpu = time.thread_time_ns() if self.match_trace else None
            if stopped or rospy.is_shutdown():
                break
            now = time.monotonic()
            finish = False
            status_due = now >= next_status
            if status_due:
                finish = rospy.get_param('/perf01a_async_finish', '') == self.run_id
                next_status = now + .02
            with self.traced_lock('worker', self.clock_ns):
                if self.match_trace:
                    self.worker_polls.append(dict(lock_id=self._active_lock['lock_id'],
                        sleep_start_ns=sleep_start, wake_ns=wake,
                        sleep_thread_cpu_ns=wake_cpu - sleep_cpu))
                self.stage_call('gate.poll_timeout', self.gate.poll_timeout, time.monotonic())
                if self.clock_ns is not None:
                    self.call_matcher(self.matcher.advance, self.clock_ns, time.monotonic_ns())
                else:
                    self.call_matcher(self.matcher.poll, time.monotonic_ns())
                if finish:
                    if not all(rospy.get_param('/perf01a_' + kind + '/done', '') == self.run_id
                               for kind in ('radar', 'infrared')):
                        raise RuntimeError('finish requested before producers done')
                    self.call_matcher(self.matcher.finish, time.monotonic_ns())
                    self.finished = True
                elif status_due:
                    self.stage_call('worker.publish_counts', self.publish_counts)
            if finish:
                self.save()
                self.publish_counts()
                rospy.set_param('~done', self.run_id)
                return

    def save(self):
        if not self.saved:
            stats = self.matcher.audit()
            stats['state_gate'] = dict(self.gate.counters)
            stats['state_gate_high_water'] = self.gate_high_water
            payload = dict(run_id=self.run_id, receipts=self.receipts,
                           decisions=self.decisions, stats=stats, errors=self.errors)
            if self.match_trace:
                payload['match_trace'] = dict(
                    locks=[row for row in self.lock_records if 'released_ns' in row],
                    state_inputs=self.state_inputs, sensor_inputs=self.sensor_inputs,
                    stages=self.stage_records, worker_polls=self.worker_polls)
            write_audit(self.directory, 'matcher-audit.json', payload)
            self.saved = True

    def shutdown(self):
        self.stop_worker()
        try:
            with self.lock:
                if not self.finished:
                    self.errors.append('shutdown_before_matcher_finish')
                    for decision in self.matcher.finish(time.monotonic_ns()):
                        self.emit(decision, PerfTrace(False), publish=False)
                    self.finished = True
                self.save()
        except Exception as exc:
            self.fail(exc)


if __name__ == '__main__':
    run_node('perf01a_sensor', Matcher)
