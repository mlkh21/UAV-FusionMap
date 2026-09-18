"""源时间状态机；所有墙上时刻由调用方显式传入单调秒。"""
import copy
import math
from collections import Counter, OrderedDict

from .mavlink_source import timestamp_ns, unavailable_quality


class SourceTimeline:
    def __init__(self, run_id, warmup_stable_sim_ns=10_000_000_000,
                 startup_timeout_wall_s=60., pending_limit=100,
                 pending_timeout_wall_s=.5, source_timeout_wall_s=2.):
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError('run_id_required')
        if type(pending_limit) is not int or pending_limit < 1:
            raise ValueError('invalid_pending_limit')
        if type(warmup_stable_sim_ns) is not int or warmup_stable_sim_ns <= 0:
            raise ValueError('invalid_warmup')
        for value in (startup_timeout_wall_s, pending_timeout_wall_s, source_timeout_wall_s):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('invalid_timeout')
        self.run_id = run_id
        self.phase = 'PREPARING'
        self.last_clock_ns = None
        self.counters = Counter()
        self.warmup_stable_sim_ns = warmup_stable_sim_ns
        self.startup_timeout_wall_s = startup_timeout_wall_s
        self.pending_limit = pending_limit
        self.pending_timeout_wall_s = pending_timeout_wall_s
        self.source_timeout_wall_s = source_timeout_wall_s
        self._start = self._wall = None
        self._last_receive = {'imu': None, 'odometry': None}
        self._latest_state_ns = self._published_ns = None
        self._reset = self._warmup_ns = None
        self._pending = []
        self._seen = OrderedDict()
        self._last_state = None

    def _touch(self, now):
        if not math.isfinite(now) or (self._wall is not None and now < self._wall):
            raise ValueError('invalid_receive_monotonic')
        if self._start is None:
            self._start = now
        self._wall = now

    def _diagnostic(self, reason):
        self.counters[reason] += 1
        return {'type': 'diagnostic', 'reason': reason}

    def _fault(self, code):
        self.phase = 'FAULT'
        self._pending.clear()
        ns = self.last_clock_ns if self.last_clock_ns is not None else 0
        # 终止事件具有独立身份；数组仅为槽位，不可当作观测。
        terminal = {'header': {
            'schema_version': '0.1', 'timestamp': ns, 'clock_id': 'sim:' + self.run_id,
            'run_id': self.run_id, 'sample_id': 'sim.terminal:%s:%d' % (code, ns//1000),
            'frame_id': 'world_ned', 'source_type': 'simulation',
            'status': 'unavailable', 'reason': 'terminal:' + code},
            'position': [0., 0., 0.], 'orientation_xyzw': [0., 0., 0., 0.],
            'linear_velocity': [0., 0., 0.], 'body_frame_id': 'body_frd',
            'velocity_frame_id': 'body_frd', 'state_source': 'estimated',
            'quality': unavailable_quality()}
        return [self._diagnostic(code), {'type': 'state', 'state': terminal}]

    def poll_timeout(self, now):
        self._touch(now)
        if self.phase == 'FAULT':
            return []
        if self.phase == 'PREPARING' and now-self._start >= self.startup_timeout_wall_s:
            return self._fault('startup_timeout')
        for source, last in self._last_receive.items():
            if last is not None and now-last >= self.source_timeout_wall_s:
                return self._fault(source + '_timeout')
        events, keep = [], []
        for entry in self._pending:
            if now-entry[1] >= self.pending_timeout_wall_s:
                events.append(self._diagnostic('pending_timeout'))
            else:
                keep.append(entry)
        self._pending = keep
        return events

    def _bind(self, state):
        result = copy.deepcopy(state)
        result['header']['run_id'] = self.run_id
        result['header']['clock_id'] = 'sim:' + self.run_id
        return result

    def _release(self):
        if self.last_clock_ns is None:
            return []
        ready = sorted((e for e in self._pending if e[0] <= self.last_clock_ns), key=lambda e:e[0])
        self._pending = [e for e in self._pending if e[0] > self.last_clock_ns]
        if not ready:
            return []
        if self.phase == 'PREPARING':
            if self._warmup_ns is None:
                self._warmup_ns = ready[0][0]
            latest = ready[-1]
            if latest[0]-self._warmup_ns < self.warmup_stable_sim_ns:
                return []
            self.phase = 'ACTIVE'
            self.counters['activated'] += 1
            ready = [latest]  # 丢弃预热缓存，只从当前覆盖状态开始。
        events = []
        for ns, _, state in ready:
            if self._published_ns is not None and ns <= self._published_ns:
                events.append(self._diagnostic('old_state'))
                continue
            self._published_ns = ns
            self.counters['published_states'] += 1
            events.append({'type': 'state', 'state': self._bind(state)})
        return events

    def consume(self, sample, receive_monotonic):
        events = self.poll_timeout(receive_monotonic)
        if self.phase == 'FAULT':
            return events
        kind = sample.get('type')
        if kind == 'imu':
            ns = timestamp_ns(sample['time_usec'])
            if self.last_clock_ns is not None:
                if ns < self.last_clock_ns:
                    return events + self._fault('imu_regression_or_reordering')
                if ns == self.last_clock_ns:
                    self.counters['duplicate_imu'] += 1
                    return events
            self.last_clock_ns = ns
            self._last_receive['imu'] = receive_monotonic
            self.counters['accepted_imu'] += 1
            return events + [{'type': 'clock', 'timestamp': ns}] + self._release()
        if kind != 'odometry':
            raise ValueError('unsupported_sample_type')
        state = sample['state']
        ns = state['header']['timestamp']
        if type(ns) is not int or not 0 <= ns <= 2**63-1:
            raise ValueError('invalid_state_timestamp')
        reset = sample['reset_counter']
        if type(reset) is not int or not 0 <= reset <= 255:
            raise ValueError('invalid_reset_counter')
        # 必须先检查reset，即使该样本稍后因重复或过旧被丢弃。
        if self._reset is not None and reset != self._reset:
            if self.phase == 'ACTIVE':
                return events + self._fault('estimator_reset')
            self._pending.clear()
            self._warmup_ns = None
            events.append(self._diagnostic('preparing_estimator_reset'))
        self._reset = reset
        key = state['header']['sample_id']
        identity_value = (state, reset)
        if key in self._seen:
            if self._seen[key] != identity_value:
                return events + [self._diagnostic('sample_identity_conflict')]
            self.counters['duplicate_state'] += 1
            return events
        self._seen[key] = copy.deepcopy(identity_value)
        if len(self._seen) > max(1000, self.pending_limit*2):
            self._seen.popitem(last=False)
        if self._published_ns is not None and ns <= self._published_ns:
            return events + [self._diagnostic('old_state')]
        if self._latest_state_ns is None or ns > self._latest_state_ns:
            self._last_receive['odometry'] = receive_monotonic
            self._latest_state_ns = ns
        self._last_state = copy.deepcopy(state)
        self.counters['accepted_odometry'] += 1
        if len(self._pending) >= self.pending_limit:
            return events + [self._diagnostic('pending_overflow')]
        self._pending.append((ns, receive_monotonic, copy.deepcopy(state)))
        return events + self._release()
