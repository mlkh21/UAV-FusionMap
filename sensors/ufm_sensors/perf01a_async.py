"""Independent PERF-01-A sampling and bounded matching, without ROS dependencies.

All times are integer ns. Frames retain their original simulation timestamp;
now_ns is a monotonic wall clock. observe_clock()/advance() record the source clock.
Callers serialize calls (e.g. a ROS node lock). At coincident schedule events,
deliver state, infrared, radar in that order, then advance the clock. A wall
timer must call poll(now) even before the first clock, or finish(now) at EOF.
ROS wrappers call observe_clock on each clock callback before frame receipts;
advance on a worker makes decisions without changing the recorded receipt clock.

The fixture pose policy is causal historical selection, with an inclusive age
bound, as in build_sensor_bundle; it is not a motion interpolation algorithm.
EOF permits matching before the business deadline, but never invents clock
coverage. Returned decisions belong to the caller and are not retained here.
Late-radar rejections report the old timestamp immediately; normal decisions
and overflow/wall-timeout decisions are emitted in radar timestamp order.
"""
import copy
import math
from pathlib import Path
import random

import yaml

from .perf01a_fixture import (build_sensor_bundle, normalize_fake_infrared_options,
                              normalize_fake_radar_options)


CONFIG_PATH = Path(__file__).resolve().parents[2] / 'configs' / 'perf01a_async.yaml'
STREAMS = ('radar', 'infrared', 'state')


def _merge(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _ns(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + ' must be a nonnegative integer')
    return value


def _validate(profile):
    if profile.get('pairing_policy', 'deadline') not in ('deadline', 'exact'):
        raise ValueError('unknown pairing_policy')
    speed = profile.get('speed_mps', 0)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed) or speed < 0:
        raise ValueError('speed_mps must be finite and nonnegative')
    if speed:
        obstacles = profile.get('obstacles_odom', [])
        if not obstacles or any(len(p) != 3 or any(not math.isfinite(v) for v in p) for p in obstacles):
            raise ValueError('finite obstacles_odom required')
    for name in ('max_delta_ns', 'max_pose_age_ns', 'max_wait_ns', 'max_wall_wait_ns'):
        _ns(profile[name], name)
    for name in ('radar_capacity', 'infrared_capacity', 'state_capacity', 'producer_capacity', 'audit_capacity'):
        if type(profile[name]) is not int or profile[name] <= 0:
            raise ValueError(name + ' must be a positive integer')
    if profile['max_wait_ns'] < profile['max_delta_ns']:
        raise ValueError('max_wait_ns must cover the nearest-match horizon')
    if profile['max_wall_wait_ns'] == 0:
        raise ValueError('max_wall_wait_ns must be positive')
    for name in ('clock_period_ns', 'source_drain_ns', 'overflow_interval_ns'):
        if _ns(profile[name], name) == 0:
            raise ValueError(name + ' must be positive')
    _ns(profile['overflow_extra_radar_count'], 'overflow_extra_radar_count')
    state_rate = profile['state_frequency_hz']
    if type(state_rate) is not int or state_rate <= 0 or 1_000_000_000 % state_rate:
        raise ValueError('state_frequency_hz requires an integer nanosecond period')
    if (1_000_000_000 // state_rate) % profile['clock_period_ns']:
        raise ValueError('state sampling must align to source clock ticks')
    for stream in ('radar', 'infrared'):
        rate = profile[stream + '_frequency_hz']
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 < rate <= 1e9:
            raise ValueError('frequency must be positive and finite')
        if 1_000_000_000 / rate != int(1_000_000_000 / rate):
            raise ValueError('fixture frequency must have an integer nanosecond period')
        for suffix in ('_phase_ns', '_delay_ns'):
            _ns(profile[stream + suffix], stream + suffix)
    for name in ('fault_start_ns', 'fault_stop_ns', 'recovery_start_ns', 'jitter_ns',
                 'reorder_radar_delay_ns', 'reorder_infrared_delay_ns'):
        _ns(profile[name], name)
    if not profile['fault_start_ns'] <= profile['fault_stop_ns'] <= profile['recovery_start_ns']:
        raise ValueError('fault window must precede recovery')
    if profile['fault'] not in ('none', 'jitter', 'out_of_order', 'missing', 'overflow'):
        raise ValueError('unknown async fault')
    if profile['fault'] == 'overflow':
        burst_span = profile['overflow_extra_radar_count'] * profile['overflow_interval_ns']
        if burst_span >= min(profile['max_wait_ns'], profile['fault_stop_ns'] - profile['fault_start_ns']):
            raise ValueError('overflow burst must finish inside the fault window before deadline')
    if len(profile['ir_resolution']) != 2 or any(type(v) is not int or v <= 0
                                                for v in profile['ir_resolution']):
        raise ValueError('ir_resolution must be positive [width, height]')
    normalize_fake_radar_options(profile.get('fake_radar', {}))
    normalize_fake_infrared_options(profile.get('fake_infrared', {}))
    sensor_seed = profile.get('sensor_noise_seed', profile.get('seed', 0))
    if type(sensor_seed) is not int:
        raise ValueError('sensor_noise_seed must be an integer')
    return profile


def load_profile(name='normal', path=None):
    """Return a detached, validated defaults + scenarios[name] deep merge."""
    with Path(path or CONFIG_PATH).open() as handle:
        config = yaml.safe_load(handle)
    if config['schema_version'] != 'perf01a.async.v1':
        raise ValueError('unsupported async schema_version')
    return _validate(_merge(config['defaults'], config['scenarios'][name]))


def make_schedule(profile, duration_ns):
    """Plan independent streams; arrival_ns is simulation-relative, not wall time.

    Dropped samples remain in the generated plan but must not be delivered.
    Jitter perturbs acquisition time inside the fault window, then adds a
    nonnegative delivery delay. The perturbed timestamp is the original sample
    timestamp, never a matcher correction. No image payloads are allocated here.
    """
    _validate(profile)
    _ns(duration_ns, 'duration_ns')
    result = {}
    for stream in ('radar', 'infrared'):
        randomizer = random.Random(profile['seed'] + (0 if stream == 'radar' else 1))
        period = int(1_000_000_000 / profile[stream + '_frequency_hz'])
        samples = []
        nominal_times = list(range(profile[stream + '_phase_ns'], duration_ns, period))
        injected = set()
        if stream == 'radar' and profile['fault'] == 'overflow':
            injected = {profile['fault_start_ns'] + i * profile['overflow_interval_ns']
                        for i in range(1, profile['overflow_extra_radar_count'] + 1)
                        if profile['fault_start_ns'] + i * profile['overflow_interval_ns'] < duration_ns}
            if injected.intersection(nominal_times):
                raise ValueError('injected Radar timestamps must not duplicate the baseline')
            nominal_times = sorted(nominal_times + list(injected))
        for index, nominal in enumerate(nominal_times):
            active = profile['fault_start_ns'] <= nominal < profile['fault_stop_ns']
            fault = profile['fault'] if active else 'none'
            timestamp = nominal
            delay = profile[stream + '_delay_ns']
            if fault == 'jitter':
                timestamp = max(0, min(duration_ns - 1,
                    nominal + randomizer.randint(-profile['jitter_ns'], profile['jitter_ns'])))
                delay += randomizer.randint(0, profile['jitter_ns'])
            if fault == 'out_of_order' and index % (2 if stream == 'radar' else 3) == 0:
                delay += profile['reorder_' + stream + '_delay_ns']
            arrival = timestamp + delay
            samples.append(dict(sequence=index, timestamp_ns=timestamp, arrival_ns=arrival,
                                drop=(fault == 'missing' and stream == 'infrared')))
            if nominal in injected:
                samples[-1].update(arrival_ns=timestamp, injected_burst=True)
        result[stream] = samples
    return result


class BoundedMatcher:
    """Bounded payload ownership and metadata-only receipt/terminal accounting.

    add_* return zero or more radar decisions, including capacity and wall-time
    failures. advance makes deadline decisions from the current cache. Infrared
    and state evictions are visible in audit(), not fake radar decisions.
    Duplicate identities are counted and ignored; a changed timestamp is also
    counted as an identity conflict. No payload hashes are computed.
    """

    def __init__(self, run_id, config):
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError('run_id required')
        self.run_id = run_id
        self.config = _validate(copy.deepcopy(config))
        self.clock_ns = None
        self._first_clock_ns = None
        self.now_ns = None
        self.closed = False
        self._processed = -1
        self._buffers = {kind: [] for kind in STREAMS}
        self._ledger = {kind: {} for kind in STREAMS}
        self._duplicates = {kind: 0 for kind in STREAMS}
        self._conflicts = {kind: 0 for kind in STREAMS}
        self._high_water = {kind: 0 for kind in STREAMS}

    @property
    def cache_sizes(self):
        return {kind: len(buffer) for kind, buffer in self._buffers.items()}

    def _time(self, now_ns):
        _ns(now_ns, 'now_ns')
        if self.now_ns is not None and now_ns < self.now_ns:
            raise ValueError('monotonic wall clock regressed')
        self.now_ns = now_ns

    @staticmethod
    def _key(entry):
        header = entry['frame']['header']
        return header['timestamp'], header['sample_id']

    def _metadata(self, kind, frame, now_ns):
        header = frame['header']
        timestamp = _ns(header['timestamp'], 'header.timestamp')
        for name in ('sample_id', 'run_id', 'clock_id'):
            if not isinstance(header[name], str) or not header[name].strip():
                raise ValueError('header.' + name + ' required')
        sample_id = header['sample_id']
        prior = self._ledger[kind].get(sample_id)
        if prior is not None:
            self._duplicates[kind] += 1
            if (timestamp, header['run_id'], header['clock_id']) != (
                    prior['timestamp_ns'], prior['run_id'], prior['clock_id']):
                self._conflicts[kind] += 1
            return None
        if sum(len(rows) for rows in self._ledger.values()) >= self.config['audit_capacity']:
            raise RuntimeError('audit_capacity exceeded; finish this short run')
        try:
            index = int(sample_id.rsplit(':', 1)[1])
        except (ValueError, IndexError):
            index = None
        row = dict(sample_id=sample_id, run_id=header['run_id'], clock_id=header['clock_id'],
                   sequence=index, timestamp_ns=timestamp, received_ns=now_ns,
                   received_clock_ns=self.clock_ns,
                   uses=0, disposition='pending', reason='', terminal_ns=None)
        self._ledger[kind][sample_id] = row
        return row

    def _retire(self, entry, reason):
        row = entry['metadata']
        row.update(disposition='adopted' if row['uses'] else 'not_adopted',
                   reason=reason, terminal_ns=self.now_ns)

    def _received_by(self, entry, deadline):
        received_clock = entry['metadata']['received_clock_ns']
        # A pre-clock receipt is bounded only by the first real source clock.
        bound = self._first_clock_ns if received_clock is None else received_clock
        return bound is not None and bound <= deadline

    def _decision(self, entry, reason=None, ordered=True):
        radar = entry['frame']
        stamp = radar['header']['timestamp']
        bundle = None
        selected_ir = selected_state = None
        if reason is None:
            if self.clock_ns is None or stamp > self.clock_ns:
                reason = 'clock_unavailable'
            elif not self._received_by(entry, stamp + self.config['max_wait_ns']):
                reason = 'arrival_deadline_exceeded'
            else:
                candidates = [e for e in self._buffers['infrared']
                              if e['frame']['header']['timestamp'] <= self.clock_ns and
                              self._received_by(e, stamp + self.config['max_wait_ns'])]
                if candidates:
                    selected_ir = min(candidates, key=lambda e: (
                        abs(e['frame']['header']['timestamp'] - stamp), *self._key(e)))
                historical = [e for e in self._buffers['state']
                              if e['frame']['header']['timestamp'] <= stamp and
                              self._received_by(e, stamp + self.config['max_wait_ns'])]
                if historical:
                    selected_state = max(historical, key=self._key)
                bundle, reason = build_sensor_bundle(
                    radar, selected_ir['frame'] if selected_ir else None,
                    [selected_state['frame']] if selected_state else [],
                    max_delta_ns=self.config['max_delta_ns'],
                    max_pose_age_ns=self.config['max_pose_age_ns'])
        if bundle is not None:
            for used in (entry, selected_ir, selected_state):
                used['metadata']['uses'] += 1
        self._retire(entry, reason)
        if ordered:
            self._processed = max(self._processed, stamp)
        return dict(radar=radar, bundle=bundle, reason=reason,
                    wait_ns=self.now_ns - entry['metadata']['received_ns'],
                    data_age_ns=max(0, (self.clock_ns if self.clock_ns is not None else stamp) - stamp))

    def _expire_wall(self):
        output = []
        pending = self._buffers['radar']
        expired = [i for i, entry in enumerate(pending)
                   if self.now_ns - entry['metadata']['received_ns'] >= self.config['max_wall_wait_ns']]
        # An older radar received later cannot hold an already expired radar.
        if expired:
            for _ in range(max(expired) + 1):
                entry = pending.pop(0)
                timed_out = self.now_ns - entry['metadata']['received_ns'] >= self.config['max_wall_wait_ns']
                output.append(self._decision(entry, 'wall_timeout' if timed_out
                                             else 'wall_timeout_order_barrier'))
        for kind in ('infrared', 'state'):
            kept = []
            for entry in self._buffers[kind]:
                if self.now_ns - entry['metadata']['received_ns'] >= self.config['max_wall_wait_ns']:
                    self._retire(entry, 'wall_timeout')
                else:
                    kept.append(entry)
            self._buffers[kind] = kept
        return output

    def _add(self, kind, frame, now_ns):
        self._time(now_ns)
        if self.closed:
            raise RuntimeError('matcher finished; start a new run')
        metadata = self._metadata(kind, frame, now_ns)
        output = self._expire_wall()
        if kind == 'radar':
            output.extend(self._drain_due())
        if metadata is None:
            return output
        header = frame['header']
        reason = ('run_mismatch' if header['run_id'] != self.run_id else
                  'clock_mismatch' if header['clock_id'] != 'sim:' + self.run_id else '')
        entry = dict(frame=frame, metadata=metadata)
        if reason:
            if kind == 'radar':
                output.append(self._decision(entry, reason, ordered=False))
            else:
                self._retire(entry, reason)
            return output
        if kind == 'state' and header.get('reason', '').startswith('terminal:'):
            self._retire(entry, 'upstream_terminal')
            output.extend(self._close('upstream_terminal'))
            return output
        if kind != 'radar' and header['status'] != 'valid':
            self._retire(entry, kind + '_unavailable')
            return output
        if kind == 'radar' and header['timestamp'] <= self._processed:
            output.append(self._decision(entry, 'late_radar', ordered=False))
            return output
        if (kind == 'radar' and self.clock_ns is not None and
                self.clock_ns > header['timestamp'] + self.config['max_wait_ns']):
            output.append(self._decision(entry, 'arrival_deadline_exceeded', ordered=False))
            return output
        buffer = self._buffers[kind]
        # Decide eviction before allocating an owned copy of the incoming payload.
        if len(buffer) == self.config[kind + '_capacity']:
            oldest = min(buffer + [entry], key=self._key)
            if oldest is not entry:
                buffer.remove(oldest)
            if kind == 'radar':
                output.append(self._decision(oldest, 'radar_overflow'))
            else:
                self._retire(oldest, kind + '_overflow')
            if oldest is entry:
                return output
            del oldest
        if kind == 'infrared':
            owned = copy.deepcopy({key: value for key, value in frame.items() if key != 'image'})
            owned['image'] = list(frame['image'])
        else:
            owned = copy.deepcopy(frame)
        entry['frame'] = owned
        buffer.append(entry)
        buffer.sort(key=self._key)
        self._high_water[kind] = max(self._high_water[kind], len(buffer))
        return output

    def add_state(self, state, now_ns):
        return self._add('state', state, now_ns)

    def add_radar(self, frame, now_ns):
        return self._add('radar', frame, now_ns)

    def add_infrared(self, frame, now_ns):
        return self._add('infrared', frame, now_ns)

    def observe_clock(self, clock_ns, now_ns):
        """Record source clock without matching; a regression terminates this run."""
        _ns(clock_ns, 'clock_ns')
        self._time(now_ns)
        if self.closed:
            return []
        if self.clock_ns is not None and clock_ns < self.clock_ns:
            return self._close('clock_regression')
        if self._first_clock_ns is None:
            self._first_clock_ns = clock_ns
        self.clock_ns = clock_ns
        return []

    def poll(self, now_ns):
        """Expire wall waits, including startup before any source clock exists."""
        self._time(now_ns)
        return [] if self.closed else self._expire_wall()

    def advance(self, clock_ns, now_ns):
        output = self.observe_clock(clock_ns, now_ns)
        if self.closed:
            return output
        output.extend(self._expire_wall())
        output.extend(self._drain_due())
        return output

    def _drain_due(self):
        """Release due Radar before capacity checks, even if the worker is late."""
        output = []
        if self.clock_ns is None:
            return output
        pending = self._buffers['radar']
        while pending:
            stamp = pending[0]['frame']['header']['timestamp']
            if stamp + self.config['max_wait_ns'] > self.clock_ns and not self._exact_ready(pending[0]):
                break
            output.append(self._decision(pending.pop(0)))
        return output

    def _exact_ready(self, entry):
        """Zero temporal distance is optimal for the unique-timestamp fixture streams."""
        if self.config.get('pairing_policy', 'deadline') != 'exact':
            return False
        stamp = entry['frame']['header']['timestamp']
        if stamp > self.clock_ns:
            return False
        exact = {}
        for kind in ('infrared', 'state'):
            candidates = [e for e in self._buffers[kind] if self._key(e)[0] == stamp]
            if len(candidates) != 1:
                return False
            exact[kind] = candidates[0]['frame']
        small_ir = dict(exact['infrared'], image=[])
        bundle, _ = build_sensor_bundle(entry['frame'], small_ir, [exact['state']],
            max_delta_ns=self.config['max_delta_ns'], max_pose_age_ns=self.config['max_pose_age_ns'])
        return bundle is not None

    def _close(self, reason=None):
        output = [self._decision(entry, reason) for entry in self._buffers['radar']]
        self._buffers['radar'].clear()
        for kind in ('infrared', 'state'):
            for entry in self._buffers[kind]:
                self._retire(entry, reason or 'eof')
            self._buffers[kind].clear()
        self.closed = True
        return output

    def finish(self, now_ns):
        """Drain all received samples, release payloads; repeated EOF is harmless."""
        self._time(now_ns)
        if self.closed:
            return []
        return self._expire_wall() + self._close()

    def audit(self, schedule=None):
        """Detached metadata only; schedule reconciliation uses identity AND time.

        adopted counts distinct samples used >=1 times; uses counts associations.
        Until eviction/EOF a reusable IR/state row may be pending with uses>0.
        generated = declared_dropped + expected receipts; compare received with
        unexpected_missing/unexpected_received rather than assuming transport.
        """
        counts = {}
        for kind, ledger in self._ledger.items():
            rows = list(ledger.values())
            counts[kind] = dict(received=len(rows),
                adopted=sum(r['disposition'] == 'adopted' for r in rows),
                not_adopted=sum(r['disposition'] == 'not_adopted' for r in rows),
                pending=sum(r['disposition'] == 'pending' for r in rows),
                uses=sum(r['uses'] for r in rows),
                timeouts=sum(r['reason'] in ('wall_timeout', 'wall_timeout_order_barrier',
                    'radar_ir_timeout', 'pose_age_exceeded', 'infrared_unavailable',
                    'arrival_deadline_exceeded') for r in rows),
                duplicate_receipts=self._duplicates[kind], identity_conflicts=self._conflicts[kind])
            if schedule is not None and kind in schedule:
                expected = {('fixture.%s:%s:%d' % (kind, self.run_id, s['sequence']), s['timestamp_ns'])
                            for s in schedule[kind] if not s['drop']}
                received = {(r['sample_id'], r['timestamp_ns']) for r in rows
                            if r['run_id'] == self.run_id and r['clock_id'] == 'sim:' + self.run_id}
                counts[kind].update(generated=len(schedule[kind]),
                    declared_dropped=sum(s['drop'] for s in schedule[kind]),
                    unexpected_missing=len(expected - received),
                    unexpected_received=len(received - expected) + len(rows) - len(received))
        return dict(run_id=self.run_id, closed=self.closed, clock_ns=self.clock_ns,
                    cache_sizes=self.cache_sizes, high_water=dict(self._high_water),
                    counts=counts, records=copy.deepcopy(self._ledger))


def expected_matches(profile, duration_ns):
    """Independent metadata event oracle; never instantiates/calls the matcher.

    Assumptions: 1x wall/sim progression, 1ms source clock and independent valid
    adapted 100Hz states (profile fields mirror the current ROS source), with
    200ms drain. Arrival and decision clocks round up to source ticks; sampling
    timestamps remain unchanged. No undeclared transport loss or callback delay.
    At equal time: observe clock, expire waits, state -> IR -> radar, then make
    decisions. The dense overflow completes before any burst deadline and does
    not require atomic delivery. State-cache boundary cases may still depend on
    callback order; actual transport/clock deviations must be reported separately.

    This algorithm uses plain lists of (timestamp, sequence, arrival) metadata
    and explicit time scans. It does not call build_sensor_bundle or reuse
    production cache, matching, eviction, or decision helpers.
    """
    schedule = make_schedule(profile, duration_ns)
    tick = profile['clock_period_ns']
    stop = (duration_ns + profile['source_drain_ns']) // tick * tick
    events = {instant: [] for instant in range(0, stop + 1, tick)}
    for kind, samples in schedule.items():
        for item in samples:
            if not item['drop']:
                arrival = (item['arrival_ns'] + tick - 1) // tick * tick
                if arrival > stop:
                    raise ValueError('source drain does not cover planned arrivals')
                events[arrival].append((kind, item))
    for item in schedule['radar']:
        if item['timestamp_ns'] + profile['max_wait_ns'] > stop:
            raise ValueError('source drain does not cover Radar deadlines')
    state_period = 1_000_000_000 // profile['state_frequency_hz']
    for sequence, instant in enumerate(range(0, stop + 1, state_period)):
        events[instant].append(('state', dict(sequence=sequence, timestamp_ns=instant)))
    waiting, infrared, states = [], [], []
    output = {}
    watermark = -1
    current_clock = None

    def reject(row, reason):
        output[row[1]] = dict(infrared_sequence=None, reason=reason, timestamp_ns=row[0])

    def evaluate(row):
        if current_clock is None or row[0] > current_clock:
            reject(row, 'clock_unavailable')
            return
        visible = [candidate for candidate in infrared if candidate[0] <= current_clock
                   and candidate[2] <= row[0] + profile['max_wait_ns']]
        if not visible:
            reject(row, 'infrared_unavailable')
            return
        best = sorted(visible, key=lambda candidate: (
            abs(candidate[0] - row[0]), candidate[0], 'fixture.infrared:r:%d' % candidate[1]))[0]
        if abs(best[0] - row[0]) > profile['max_delta_ns']:
            reject(row, 'radar_ir_timeout')
            return
        historical = [candidate for candidate in states if candidate[0] <= row[0]
                      and candidate[2] <= row[0] + profile['max_wait_ns']]
        if not historical:
            reject(row, 'pose_unavailable')
            return
        latest = max(historical)
        if row[0] - latest[0] > profile['max_pose_age_ns']:
            reject(row, 'pose_age_exceeded')
            return
        output[row[1]] = dict(infrared_sequence=best[1], reason='', timestamp_ns=row[0])

    for instant, arrivals in sorted(events.items()):
        waiting.sort()
        expired = [i for i, row in enumerate(waiting) if instant - row[2] >= profile['max_wall_wait_ns']]
        if expired:
            prefix = waiting[:max(expired) + 1]
            waiting = waiting[max(expired) + 1:]
            for row in prefix:
                reject(row, 'wall_timeout' if instant - row[2] >= profile['max_wall_wait_ns']
                       else 'wall_timeout_order_barrier')
                watermark = max(watermark, row[0])
        infrared = [row for row in infrared if instant - row[2] < profile['max_wall_wait_ns']]
        states = [row for row in states if instant - row[2] < profile['max_wall_wait_ns']]
        arrivals.sort(key=lambda event: ({'state': 0, 'infrared': 1, 'radar': 2}[event[0]],
                                         event[1]['sequence']))
        for kind, item in arrivals:
            row = (item['timestamp_ns'], item['sequence'], instant)
            if kind == 'state':
                states = sorted(states + [row])[-profile['state_capacity']:]
            elif kind == 'infrared':
                infrared = sorted(infrared + [row])[-profile['infrared_capacity']:]
            elif row[0] <= watermark:
                reject(row, 'late_radar')
            elif instant > row[0] + profile['max_wait_ns']:
                reject(row, 'arrival_deadline_exceeded')
            else:
                waiting.append(row)
                waiting.sort()
                if len(waiting) > profile['radar_capacity']:
                    evicted = waiting.pop(0)
                    reject(evicted, 'radar_overflow')
                    watermark = max(watermark, evicted[0])
        current_clock = instant
        while waiting:
            stamp = waiting[0][0]
            exact = (profile.get('pairing_policy', 'deadline') == 'exact' and stamp <= instant
                     and sum(r[0] == stamp for r in infrared) == 1
                     and sum(r[0] == stamp for r in states) == 1)
            if stamp + profile['max_wait_ns'] > instant and not exact:
                break
            row = waiting.pop(0)
            evaluate(row)
            watermark = max(watermark, row[0])
    for row in waiting:
        evaluate(row)
    return dict(sorted(output.items()))
