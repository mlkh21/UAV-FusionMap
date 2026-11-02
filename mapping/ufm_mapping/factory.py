"""Explicit map selection shared by ROS assembly and public occupancy replay."""
from .local_map import SparseLocalMap


def create_map(backend='latest', settings=None, *, run_id=None, clock_id=None, fixture_spec=None):
    settings = dict(settings or {})
    if backend == 'latest':
        if fixture_spec is not None:
            raise ValueError('M2 fixture configuration requires explicit m2_fixture backend')
        return SparseLocalMap(**settings)
    if backend not in ('m2_fixture', 'm3_fixture', 'm4_fixture'):
        raise ValueError('unknown map backend: ' + str(backend))
    if fixture_spec is None:
        raise ValueError(backend + ' requires explicit fixture configuration')
    if set(settings) - {'rolling_enabled'} or type(settings.get('rolling_enabled', False)) is not bool:
        raise ValueError('fixture parameters must come from configuration; rolling_enabled is boolean')
    # Keep the default map path independent of the synthetic candidate modules.
    if backend == 'm4_fixture':
        if settings.get('rolling_enabled') is not True:
            raise ValueError('m4_fixture requires explicit rolling_enabled=True')
        from .scene_map import SceneMap
        return SceneMap(fixture_spec, run_id, clock_id)
    if backend == 'm3_fixture':
        if settings.get('rolling_enabled', False):
            from .rolling_interval_probability_map import RollingIntervalProbabilityMap
            candidate = RollingIntervalProbabilityMap
        else:
            from .fixed_interval_probability_map import FixedIntervalProbabilityMap
            candidate = FixedIntervalProbabilityMap
    elif settings.get('rolling_enabled', False):
        from .rolling_probability_map import RollingProbabilityMap
        candidate = RollingProbabilityMap
    else:
        from .fixed_probability_map import FixedProbabilityMap
        candidate = FixedProbabilityMap
    return candidate(fixture_spec, run_id, clock_id)
