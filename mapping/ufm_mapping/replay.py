"""Deterministic occupancy replay through public Local Map methods; no sensor access."""
import copy
import math

from .factory import create_map


def equivalent(actual, expected):
    """The wire's float32 quantities allow 1e-6 absolute error; identities stay exact."""
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            equivalent(actual[key], expected[key]) for key in actual)
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(equivalent(a, b) for a, b in zip(actual, expected))
    if isinstance(actual, float) or isinstance(expected, float):
        return (isinstance(actual, float) and isinstance(expected, float) and
                math.isclose(actual, expected, rel_tol=0., abs_tol=1e-6))
    return type(actual) is type(expected) and actual == expected


def _wire_quality(result):
    result = copy.deepcopy(result)
    if result['uncertainty'] is None:
        result['uncertainty'] = dict(status='unavailable', kind='', value=None, unit='', source='')
    return result


def replay_observations(observations, run_id, map_settings=None, query_records=(), *,
                        backend='latest', clock_id=None, fixture_spec=None):
    """One fresh map per call. Recorded query revisions select which state to query.

    Queries reproduce the recorded map version, not the original wall-clock
    interleaving. Callers compare all resulting fields against the receipt.
    Cross-run observations are refused; a new run requires a separate call.
    """
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError('configured run_id is required')
    local_map = create_map(backend, map_settings, run_id=run_id, clock_id=clock_id,
                           fixture_spec=fixture_spec)
    snapshots, steps, queries = [], [], {}
    pending = {}
    for index, record in enumerate(query_records):
        revision = record['result']['revision']
        if type(revision) is not int or revision < 0:
            raise ValueError('query receipt revision must be nonnegative')
        pending.setdefault(revision, []).append((index, record['request']))

    def query_revision(revision):
        for index, request in pending.pop(revision, []):
            queries[index] = dict(request=copy.deepcopy(request),
                                 result=_wire_quality(local_map.query(**request)))

    query_revision(0)
    for index, observation in enumerate(observations):
        before = local_map.snapshot()
        try:
            if observation['header']['run_id'] != run_id:
                raise ValueError('occupancy run differs from configured replay run')
            changed = local_map.update(observation)
            outcome, reason = ('fused', '') if changed else ('not_fused', 'observation_not_fused')
        except (ValueError, KeyError, TypeError) as exc:
            outcome, reason = 'rejected', type(exc).__name__ + ':' + str(exc)
            changed = False
        after = local_map.snapshot()
        if not changed and before != after:
            raise RuntimeError('refused observation changed map snapshot')
        steps.append(dict(index=index, outcome=outcome, reason=reason,
                          revision=after['revision'], timestamp=after['header']['timestamp']))
        if changed:
            snapshots.append(after)
            query_revision(after['revision'])
    if pending:
        raise ValueError('query references an unreached map revision: ' + str(sorted(pending)))
    return dict(steps=steps, snapshots=snapshots,
                queries=[queries[index] for index in range(len(query_records))],
                final_snapshot=local_map.snapshot())
