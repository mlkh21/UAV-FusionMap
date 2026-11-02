"""Explicit synthetic M3 rolling map; nominal/range state moves in one cell ledger."""
from .fixed_interval_probability_map import FixedIntervalProbabilityMap
from .m3_contract import validate_fixture_observation
from .rolling_probability_map import RollingProbabilityMap


class RollingIntervalProbabilityMap(FixedIntervalProbabilityMap):
    def __init__(self, spec, run_id, clock_id):
        super().__init__(spec, run_id, clock_id)
        self.rolling_enabled = True

    def _validate_observation(self, observation):
        validate_fixture_observation(observation, self._interval_spec, rolling=True)

    def _prepare_grid(self, observation):
        # Same-module geometry only: staged cells and their opaque state items
        # migrate/evict together; interval construction stays in the M3 parent.
        return RollingProbabilityMap._prepare_grid(self, observation)
