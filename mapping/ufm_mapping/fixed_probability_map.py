"""Opt-in fixed-grid M2 arithmetic candidate for explicitly synthetic inverse evidence."""
from collections import OrderedDict
import copy
import math

from .local_map import SparseLocalMap
from .m2_contract import validate_fixture_observation, validate_spec


def _logit(probability):
    return math.log(probability) - math.log1p(-probability)


def _probability(log_odds):
    if log_odds >= 0:
        return 1. / (1. + math.exp(-log_odds))
    value = math.exp(log_odds)
    return value / (1. + value)


class FixedProbabilityMap(SparseLocalMap):
    """Public snapshots/queries reuse M1; updates never call M1's overwrite path."""
    def __init__(self, spec, run_id, clock_id):
        validate_spec(spec)
        if any(not isinstance(value, str) or not value.strip() for value in (run_id, clock_id)):
            raise ValueError('M2 candidate requires explicit run and clock identity')
        super().__init__(map_id=spec['map_id'], resolution=spec['resolution'],
            shape=spec['shape'], origin=spec['origin'], staleness_limit_ns=spec['evidence_ttl_ns'],
            max_active_cells=spec['max_active_cells'], free_threshold=spec['free_threshold'],
            occupied_threshold=spec['occupied_threshold'])
        self._spec = copy.deepcopy(spec)
        self._run_id, self._clock_id = run_id, clock_id
        self._input_timestamp = -1
        self._geometry_timestamp = -1
        self._seen = OrderedDict()
        self._log_odds = {}
        self._prior = _logit(spec['prior_probability'])
        self._lower = _logit(spec['minimum_probability'])
        self._upper = _logit(spec['maximum_probability'])

    @property
    def retained_identity_count(self):
        return len(self._seen)

    def _validate_observation(self, observation):
        validate_fixture_observation(observation, self._spec)

    def _prepare_grid(self, observation):
        return self.origin, (0, 0, 0), dict(self._cells), dict(self._log_odds)

    def _updated_cell(self, voxel, previous, previous_log_odds, stamp, expired):
        """Construct staged cell/state; subclasses must not commit to the live map here."""
        value = self._prior if previous is None or expired else previous_log_odds
        value = max(self._lower, min(self._upper,
                    value + _logit(voxel['probability']) - self._prior))
        cell = dict(index=list(voxel['index']), probability=_probability(value), observed=True,
            last_observed_timestamp=stamp, confidence=None,
            uncertainty=dict(status='unavailable', kind='', value=None, unit='',
                             source='uncalibrated M2 synthetic inverse evidence'))
        return cell, value

    def update(self, observation):
        self._validate_observation(observation)
        header = observation['header']
        if (header['run_id'], header['clock_id']) != (self._run_id, self._clock_id):
            raise ValueError('M2 candidate run or clock domain changed')
        identity, stamp = header['sample_id'], header['timestamp']
        if identity in self._seen:
            if self._seen[identity] != observation:
                raise ValueError('M2 observation sample identity conflict')
            return False
        if stamp <= self._input_timestamp:
            raise ValueError('M2 observation timestamp must increase')

        new_origin, offset, cells, log_odds = self._prepare_grid(observation)
        moved = new_origin != self.origin
        contributed = False
        if header['status'] == 'valid':
            for voxel in observation['voxels']:
                probability = voxel['probability']
                if not voxel['observed'] or probability == self._spec['neutral_probability']:
                    continue
                index = tuple(voxel['index'][axis] + offset[axis] for axis in range(3))
                if any(not 0 <= index[axis] < self.shape[axis] for axis in range(3)):
                    continue
                previous = cells.get(index)
                expired = (previous is not None and stamp - previous['last_observed_timestamp'] >
                           self.staleness_limit_ns)
                cell, value = self._updated_cell(voxel, previous, log_odds.get(index), stamp, expired)
                log_odds[index] = value
                cells[index] = dict(cell, index=list(index))
                contributed = True
        if len(cells) > self.max_active_cells:
            keep = sorted(cells, key=lambda index: (-cells[index]['last_observed_timestamp'], index))[
                :self.max_active_cells]
            cells = {index: cells[index] for index in keep}
            log_odds = {index: log_odds[index] for index in keep}

        # Validate and stage all state before committing even the input watermark.
        retained = copy.deepcopy(observation)
        self._seen[identity] = retained
        if len(self._seen) > self._spec['identity_history_limit']:
            self._seen.popitem(last=False)
        self._input_timestamp = stamp
        self.origin = new_origin
        self._cells, self._log_odds = cells, log_odds
        if moved:
            self._geometry_timestamp = stamp
        if not contributed and not moved:
            return False
        if contributed:
            self._latest_timestamp = stamp
            self._source_types.add('fixture')
        self._revision += 1
        return True

    def query(self, map_id, frame_id, run_id, clock_id, query_timestamp, point, max_age_ns):
        if type(query_timestamp) is not int or not 0 <= query_timestamp < 2**63:
            raise ValueError('query timestamp must be nonnegative int64 nanoseconds')
        if type(max_age_ns) is not int or not 0 <= max_age_ns < 2**63:
            raise ValueError('max age must be nonnegative int64 nanoseconds')
        result = super().query(map_id, frame_id, run_id, clock_id, query_timestamp, point,
                               min(max_age_ns, self.staleness_limit_ns))
        if query_timestamp < self._geometry_timestamp and result['status'] != 'unavailable':
            result.update(status='unavailable', reason='query_before_latest_map_time', index=None,
                          probability=None, confidence=None, uncertainty=None, observed=False,
                          last_observed_timestamp=None)
        return result
