"""M2 synthetic rolling odom window; evidence and log-odds move together."""
import math

from .fixed_probability_map import FixedProbabilityMap
from .m2_contract import lattice_offset, validate_fixture_observation


class RollingProbabilityMap(FixedProbabilityMap):
    def __init__(self, spec, run_id, clock_id):
        super().__init__(spec, run_id, clock_id)
        self.rolling_enabled = True

    def _validate_observation(self, observation):
        validate_fixture_observation(observation, self._spec, rolling=True)

    def _prepare_grid(self, observation):
        if observation['header']['status'] != 'valid':
            return self.origin, (0, 0, 0), dict(self._cells), dict(self._log_odds)
        body = observation['context']['T_mapping_body']
        relative = [(body[4 * axis + 3] - self._anchor_origin[axis] -
                     self.shape[axis] * self.resolution[axis] / 2) / self.resolution[axis]
                    for axis in range(3)]
        if any(not math.isfinite(value) for value in relative):
            raise ValueError('M2 body position exceeds finite map lattice')
        origin = tuple(self._anchor_origin[axis] + math.floor(relative[axis] + .5) *
                       self.resolution[axis] for axis in range(3))
        offset = lattice_offset(observation['origin'], origin, self.resolution)
        if origin == self.origin:
            return origin, offset, dict(self._cells), dict(self._log_odds)
        shift = lattice_offset(self.origin, origin, self.resolution)
        cells, log_odds = {}, {}
        for previous, cell in self._cells.items():
            index = tuple(previous[axis] + shift[axis] for axis in range(3))
            if any(not 0 <= index[axis] < self.shape[axis] for axis in range(3)):
                continue
            cells[index] = dict(cell, index=list(index))
            log_odds[index] = self._log_odds[previous]
        return origin, offset, cells, log_odds
