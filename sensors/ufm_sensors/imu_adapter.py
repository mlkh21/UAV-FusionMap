"""功能级PX4/JSBSim IMU源到pilot点虚拟FLU轴；不声明实际安装外参。"""
import copy
from collections import Counter
from .identity_history import IdentityHistory


def adapt_imu(sample, run_id, calibration_id):
    if calibration_id != 'sim_pilot_virtual_flu_v1':
        raise ValueError('imu_virtual_calibration_required')
    h = sample['header']
    if (h['run_id'] != run_id or h['clock_id'] != 'sim:' + run_id or
            h['source_type'] != 'simulation' or h['frame_id'] != 'body_frd' or
            h['schema_version'] != '0.1' or h['status'] not in ('valid', 'unavailable') or
            sample['acceleration_type'] != 'specific_force'):
        raise ValueError('invalid_imu_source_contract')
    if sample['acceleration_covariance'] is not None or sample['angular_velocity_covariance'] is not None:
        raise ValueError('imu_covariance_not_verified')
    if h['status'] == 'unavailable' and not h['reason'].startswith('terminal:'):
        raise ValueError('invalid_imu_terminal')
    result = copy.deepcopy(sample)
    result['header'].update(source_type='derived', frame_id='imu',
                            sample_id='sensors.imu:' + h['sample_id'])
    result['calibration_id'] = calibration_id
    if h['status'] == 'valid':
        result['linear_acceleration'] = [v * axis for v, axis in
                                         zip(sample['linear_acceleration'], (1, -1, -1))]
        result['angular_velocity'] = [v * axis for v, axis in
                                      zip(sample['angular_velocity'], (1, -1, -1))]
    return result


class ImuClockGate:
    """对独立IMU流按源/clock覆盖放行；无时钟不补发或填造有效样本。"""
    def __init__(self, run_id, pending_limit=100, timeout_wall_s=.5,
                 identity_history_limit=1000):
        if (not isinstance(run_id, str) or not run_id.strip() or type(pending_limit) is not int
                or pending_limit < 1 or not isinstance(timeout_wall_s, (int, float))
                or not 0 < timeout_wall_s < float('inf')):
            raise ValueError('invalid_imu_gate_config')
        self.run_id = run_id
        self.pending_limit = pending_limit
        self.timeout_wall_s = timeout_wall_s
        self.last_clock_ns = None
        self.last_published_ns = None
        self.locked = False
        self.pending = []
        self._history = IdentityHistory(identity_history_limit)
        self.counters = Counter()

    @property
    def identity_count(self):
        return len(self._history.records)

    def poll_timeout(self, now):
        kept = []
        for received, sample in self.pending:
            if now - received >= self.timeout_wall_s:
                self.counters['imu_pending_timeout'] += 1
            else:
                kept.append((received, sample))
        self.pending = kept
        return []

    def consume_imu(self, sample, now):
        h = sample['header']
        if (h['run_id'] != self.run_id or h['clock_id'] != 'sim:' + self.run_id or
                type(h['timestamp']) is not int or not 0 <= h['timestamp'] < 2**63 or
                not isinstance(h['sample_id'], str) or not h['sample_id']):
            raise ValueError('imu_identity_or_clock_mismatch')
        if h['status'] == 'unavailable' and h['reason'].startswith('terminal:'):
            if self.locked:
                return []
            self.locked = True
            self.pending.clear()
            return [copy.deepcopy(sample)]
        if self.locked:
            return []
        if h['status'] != 'valid':
            raise ValueError('invalid_imu_status')
        try:
            outcome = self._history.remember(sample)
        except ValueError as exc:
            raise ValueError('imu_sample_identity_conflict') from exc
        if outcome == 'duplicate':
            self.counters['duplicate_imu'] += 1
            return []
        if outcome == 'retired':
            self.counters['old_imu'] += 1
            return []
        self.poll_timeout(now)
        if self.last_published_ns is not None and h['timestamp'] <= self.last_published_ns:
            self.counters['old_imu'] += 1
            return []
        if len(self.pending) >= self.pending_limit:
            self.counters['imu_pending_overflow'] += 1
            return []
        self.pending.append((now, copy.deepcopy(sample)))
        return self._release()

    def consume_clock(self, ns, now):
        if type(ns) is not int or not 0 <= ns < 2**63:
            raise ValueError('invalid_imu_clock')
        self.poll_timeout(now)
        if self.locked:
            return []
        if self.last_clock_ns is not None and ns < self.last_clock_ns:
            self.locked = True
            self.pending.clear()
            raise ValueError('imu_clock_regression')
        self.last_clock_ns = ns
        return self._release()

    def _release(self):
        if self.last_clock_ns is None:
            return []
        ready = sorted((s for _, s in self.pending if s['header']['timestamp'] <= self.last_clock_ns),
                       key=lambda s: s['header']['timestamp'])
        self.pending = [(t, s) for t, s in self.pending if s['header']['timestamp'] > self.last_clock_ns]
        output = []
        for sample in ready:
            ns = sample['header']['timestamp']
            if self.last_published_ns is not None and ns <= self.last_published_ns:
                self.counters['old_imu'] += 1
                continue
            self.last_published_ns = ns
            output.append(sample)
        return output
