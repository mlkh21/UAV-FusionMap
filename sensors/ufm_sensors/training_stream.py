"""Bounded training-fixture state history; never used by the online matcher."""
import copy

from .training_supervision import build_training_sample


class TrainingScanBuffer:
    def __init__(self, run_id, config, reference_timestamps,
                 max_history_states=64, max_pending_states=2):
        references = list(reference_timestamps)
        duration = config['lidar']['scan_duration_ns']
        if (not run_id or not references
                or any(type(stamp) is not int or stamp < duration // 2 for stamp in references)
                or any(a >= b for a, b in zip(references, references[1:]))
                or type(duration) is not int or duration < 0 or duration % 2
                or config.get('mode') != 'training_data_generation'
                or config.get('schema_version') not in ('0.1', '0.2')
                or (duration and config['schema_version'] != '0.2')
                or max_history_states < 1 or max_pending_states < 1):
            raise ValueError('invalid bounded training scan configuration')
        self.run_id = run_id
        self.config = copy.deepcopy(config)
        self.references = references
        self.max_history_states = max_history_states
        self.max_pending_states = max_pending_states
        self.states = []
        self._sample_ids = set()
        self._clock_ns = None
        self.published = 0

    def push_state(self, state):
        header = state['header']
        stamp, sample_id = header['timestamp'], header['sample_id']
        if (header['run_id'] != self.run_id or header['clock_id'] != 'sim:' + self.run_id
                or header['frame_id'] != 'odom' or header['source_type'] != 'derived'
                or header['status'] != 'valid' or state['body_frame_id'] != 'base_link'
                or state['state_source'] != 'estimated'
                or type(stamp) is not int or stamp < 0
                or not isinstance(sample_id, str) or not sample_id
                or sample_id in self._sample_ids
                or (self.states and stamp <= self.states[-1]['header']['timestamp'])):
            raise ValueError('invalid, duplicate or unordered training state')
        if len(self.states) >= self.max_history_states:
            raise ValueError('training history exceeded bounded fixture capacity')
        pending = sum(self._clock_ns is None or item['header']['timestamp'] > self._clock_ns
                      for item in self.states)
        if ((self._clock_ns is None or stamp > self._clock_ns)
                and pending >= self.max_pending_states):
            raise ValueError('training clock lag beyond bounded queue')
        self.states.append(copy.deepcopy(state))
        self._sample_ids.add(sample_id)
        return self._drain()

    def advance_clock(self, stamp):
        if (type(stamp) is not int or stamp < 0
                or (self._clock_ns is not None and stamp < self._clock_ns)):
            raise ValueError('training clock regression or invalid timestamp')
        self._clock_ns = stamp
        return self._drain()

    def _drain(self):
        samples = []
        half = self.config['lidar']['scan_duration_ns'] // 2
        while self.published < len(self.references):
            reference = self.references[self.published]
            end = reference + half
            if (self._clock_ns is None or self._clock_ns < end
                    or not self.states or self.states[-1]['header']['timestamp'] < end):
                break
            matching = [item for item in self.states if item['header']['timestamp'] == reference]
            if not matching:
                raise ValueError('training reference state missing')
            # Future pose data is consumed only after /clock covers the scan end.
            history = [item for item in self.states if item['header']['timestamp'] <= self._clock_ns]
            samples.append(build_training_sample(matching[0], self.config, state_history=history))
            self.published += 1
        return samples

    def finish(self):
        if self.published != len(self.references):
            raise ValueError('training stream ended with incomplete scan history or clock coverage')
