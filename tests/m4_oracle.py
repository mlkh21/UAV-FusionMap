"""Test-only rational Scene expectations from explicit ownership tables, no map imports.

This module does not decide ownership, rolling or eviction. Each step supplies the
active and FIFO-sealed version lists independently of the future implementation.
"""
import copy
from fractions import Fraction as F


def _f(value):
    return F(str(value))


def scene_index(point, scene):
    return [int((_f(p) - _f(o)) // _f(r)) for p, o, r in
            zip(point, scene['origin'], scene['resolution'])]


def cell_value(version, spec):
    profile, scene = spec['local_map']['interval_profile'], spec['scene']
    translation = [spec['registration']['T_map_odom'][i] for i in (3, 7, 11)]
    point = [_f(p) + _f(t) for p, t in zip(version['point'], translation)]
    bounds = version['interval']
    return dict(index=scene_index(point, scene), probability=float(F(version['probability'])),
        observed=True, last_observed_timestamp=version['timestamp'], confidence=None,
        uncertainty=dict(status='unavailable' if bounds is None else 'available',
            kind=profile['kind'], value=None if bounds is None else [float(F(v)) for v in bounds],
            unit=profile['unit'], source=profile['unavailable_source'] if bounds is None else
            profile['output_source']))


def expected_step(spec, versions, declaration):
    """Materialize a declared state and public queries; never consume observations."""
    active, sealed = declaration['active'], declaration['sealed']
    local, scene = spec['local_map']['arithmetic'], spec['scene']
    if len(sealed) > spec['max_sealed_submaps'] or any(not group for group in sealed):
        raise ValueError('oracle table has excessive or empty sealed groups')
    if any(len(group) > local['max_active_cells'] for group in [active] + sealed):
        raise ValueError('oracle table exceeds per-submap capacity')
    names = active + [name for group in sealed for name in group]
    cells = [cell_value(versions[name], spec) for name in names]
    if len({tuple(c['index']) for c in cells}) != len(cells):
        raise ValueError('oracle table has duplicate Scene ownership')
    if any(not all(0 <= value < scene['shape'][i] for i, value in enumerate(c['index'])) for c in cells):
        raise ValueError('oracle table cell outside Scene')
    evidence = declaration['evidence_timestamp']
    domain = spec['registration']
    revision = declaration['revision']
    coverage = [float(_f(scene['origin'][i]) + side * scene['shape'][i] * _f(scene['resolution'][i]))
                for i in range(3) for side in (0, 1)]
    snapshot = dict(header=dict(schema_version='0.1', timestamp=0 if evidence is None else evidence,
        clock_id=domain['clock_id'], run_id=domain['run_id'],
        sample_id='mapping.snapshot:%s:%d' % (scene['map_id'], revision), frame_id='map',
        source_type='derived', status='unavailable' if evidence is None else 'valid',
        reason='no_observation' if evidence is None else ''),
        map_id=scene['map_id'], revision=revision, cells=sorted(cells, key=lambda c:c['index']),
        resolution=copy.deepcopy(scene['resolution']), shape=copy.deepcopy(scene['shape']),
        origin=copy.deepcopy(scene['origin']), coverage=coverage,
        source_types=[] if evidence is None else ['fixture'])
    queries = []
    for query in declaration['queries']:
        request = dict(map_id=scene['map_id'], frame_id='map', run_id=domain['run_id'],
            clock_id=domain['clock_id'], query_timestamp=query['timestamp'],
            point=list(query['point']), max_age_ns=query.get('max_age_ns', local['evidence_ttl_ns']))
        request.update(query.get('identity_changes', {}))
        result = dict(map_id=scene['map_id'], revision=revision, run_id=request['run_id'],
            clock_id=request['clock_id'], frame_id=request['frame_id'],
            query_timestamp=request['query_timestamp'], point=list(request['point']),
            index=None, status='unavailable', reason='map_unavailable', probability=None,
            confidence=None, uncertainty=None, observed=False, last_observed_timestamp=None)
        time = request['query_timestamp']
        if request['map_id'] != scene['map_id']:
            result['reason'] = 'map_id_mismatch'
        elif request['frame_id'] != 'map':
            result['reason'] = 'frame_mismatch'
        elif (request['run_id'], request['clock_id']) != (domain['run_id'], domain['clock_id']):
            result['reason'] = 'run_or_clock_mismatch'
        elif not domain['valid_from_ns'] <= time < domain['valid_until_ns']:
            result['reason'] = 'registration_unavailable'
        elif evidence is None:
            pass
        elif time < max(evidence, declaration['structure_timestamp']):
            result['reason'] = 'query_before_latest_map_time'
        else:
            index = scene_index(request['point'], scene)
            if not all(0 <= v < scene['shape'][i] for i,v in enumerate(index)):
                result.update(status='unknown', reason='outside_coverage')
            else:
                result.update(index=index, status='unknown', reason='no_observation')
                matches = [c for c in cells if c['index'] == index]
                if matches:
                    cell = matches[0]
                    result.update(copy.deepcopy(cell))
                    probability = cell['probability']
                    if time - cell['last_observed_timestamp'] > min(request['max_age_ns'], local['evidence_ttl_ns']):
                        result.update(status='stale', reason='max_age_exceeded')
                    elif probability >= local['occupied_threshold']:
                        result.update(status='occupied', reason='')
                    elif probability <= local['free_threshold']:
                        result.update(status='free', reason='')
                    else:
                        result.update(status='unknown', reason='between_thresholds')
        if query.get('status') is not None and query['status'] != result['status']:
            raise ValueError('oracle query status disagrees with explicit table: ' + str(query))
        queries.append(dict(request=request, result=result))
    return dict(snapshot=snapshot, queries=queries,
        ownership=dict(active=list(active), sealed=copy.deepcopy(sealed)),
        structure_timestamp=declaration['structure_timestamp'])
