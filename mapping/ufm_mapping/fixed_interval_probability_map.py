"""Explicit fixed M3 fixture candidate; intervals bound the declared M2 arithmetic."""
import copy

from .fixed_probability_map import FixedProbabilityMap, _logit, _probability
from .m3_contract import validate_fixture_observation, validate_interval_quality, validate_spec


class FixedIntervalProbabilityMap(FixedProbabilityMap):
    def __init__(self, spec, run_id, clock_id):
        validate_spec(spec)
        super().__init__(spec['arithmetic'], run_id, clock_id)
        self._interval_spec = copy.deepcopy(spec)

    def _validate_observation(self, observation):
        validate_fixture_observation(observation, self._interval_spec)

    def _updated_cell(self, voxel, previous, previous_state, stamp, expired):
        new_cycle = previous is None or expired
        previous_nominal = None if new_cycle else previous_state[0]
        cell, nominal = super()._updated_cell(voxel, previous, previous_nominal, stamp, expired)
        profile = self._interval_spec['interval_profile']
        quality = dict(status='unavailable', kind=profile['kind'], value=None, unit=profile['unit'],
                       source=profile['unavailable_source'])
        lower, upper = None, None
        if (voxel['uncertainty']['status'] == 'available' and
                (new_cycle or previous_state[1] is not None)):
            bounds = (self._prior, self._prior) if new_cycle else previous_state[1:]
            lower, upper = [max(self._lower, min(self._upper,
                bounds[axis] + _logit(evidence) - self._prior))
                for axis, evidence in enumerate(voxel['uncertainty']['value'])]
            quality.update(status='available', value=[_probability(lower), _probability(upper)],
                           source=profile['output_source'])
        validate_interval_quality(cell['probability'], quality, self._interval_spec, output=True)
        cell['uncertainty'] = quality
        # One bounded, immutable state item per cell: nominal and optional endpoint log-odds.
        # The parent stages/commits/evicts these items together with public cells.
        return cell, (nominal, lower, upper)
