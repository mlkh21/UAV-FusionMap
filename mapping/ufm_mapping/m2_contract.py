"""Opt-in synthetic M2 evidence contract; no probability accumulation or ROS imports."""
import math

from .local_map import _validate_quality


DOMAIN = 'm2_explicit_inverse_fixture_v1'
OBSERVATION_FIELDS = frozenset({'header', 'context', 'resolution', 'shape', 'origin',
                                'observed_domain_source', 'voxels'})
FIELDS = frozenset({
    'schema_version', 'fixture_only', 'enabled_by_default', 'map_id', 'frame_id',
    'observed_domain_source', 'calibration_id', 'resolution', 'shape', 'origin', 'cell_index',
    'prior_probability', 'occupied_probability', 'free_probability', 'neutral_probability',
    'minimum_probability', 'maximum_probability', 'free_threshold', 'occupied_threshold',
    'evidence_ttl_ns', 'sample_period_ns', 'identity_history_limit', 'max_active_cells',
})


def _finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def validate_spec(spec):
    if set(spec) != FIELDS or spec['schema_version'] != 'm2_fixture.v1':
        raise ValueError('M2 fixture configuration fields or version differ')
    if spec['fixture_only'] is not True or spec['enabled_by_default'] is not False:
        raise ValueError('M2 fixture must be explicit and disabled by default')
    if spec['frame_id'] != 'odom' or spec['observed_domain_source'] != DOMAIN:
        raise ValueError('M2 fixture requires the declared odom inverse-observation domain')
    for key in ('map_id', 'calibration_id'):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError('M2 fixture requires ' + key)
    for key in ('prior_probability', 'occupied_probability', 'free_probability',
                'neutral_probability', 'minimum_probability', 'maximum_probability',
                'free_threshold', 'occupied_threshold'):
        if not _finite(spec[key]) or not 0 < spec[key] < 1:
            raise ValueError('M2 fixture probability must be finite in (0,1): ' + key)
    if (spec['prior_probability'] != .5 or spec['neutral_probability'] != .5 or
            not spec['free_probability'] < .5 < spec['occupied_probability'] or
            not spec['minimum_probability'] < .5 < spec['maximum_probability'] or
            not spec['free_threshold'] < .5 < spec['occupied_threshold']):
        raise ValueError('M2 fixture prior, evidence direction, bounds or thresholds differ')
    for key in ('evidence_ttl_ns', 'sample_period_ns', 'identity_history_limit', 'max_active_cells'):
        if type(spec[key]) is not int or not 0 < spec[key] < 2**63:
            raise ValueError('M2 fixture requires a positive integer: ' + key)
    for key in ('resolution', 'shape', 'origin', 'cell_index'):
        if len(spec[key]) != 3:
            raise ValueError('M2 fixture geometry requires XYZ')
    if (any(not _finite(value) or value <= 0 for value in spec['resolution']) or
            any(not _finite(value) for value in spec['origin']) or
            any(type(value) is not int or not 0 < value < 2**31 for value in spec['shape']) or
            any(type(value) is not int or not 0 <= value < spec['shape'][axis]
                for axis, value in enumerate(spec['cell_index']))):
        raise ValueError('M2 fixture grid geometry invalid')


def lattice_offset(origin, anchor, resolution):
    if len(origin) != 3 or any(not _finite(value) for value in origin):
        raise ValueError('M2 observation origin must be finite XYZ')
    relative = [(origin[axis] - anchor[axis]) / resolution[axis] for axis in range(3)]
    if any(not math.isfinite(value) for value in relative):
        raise ValueError('M2 origin exceeds finite lattice')
    offset = tuple(round(value) for value in relative)
    if any(abs(value - offset[axis]) > 1e-8 for axis, value in enumerate(relative)):
        raise ValueError('M2 observation origin is not aligned to the configured lattice')
    return offset


def _validate_body_transform(matrix):
    if len(matrix) != 16 or any(not _finite(value) for value in matrix):
        raise ValueError('M2 body transform must be finite 4x4')
    if any(abs(a - b) > 1e-9 for a, b in zip(matrix[12:], (0., 0., 0., 1.))):
        raise ValueError('M2 body transform must be homogeneous')
    for row in range(3):
        for col in range(3):
            dot = sum(matrix[4 * row + index] * matrix[4 * col + index] for index in range(3))
            if abs(dot - float(row == col)) > 1e-6:
                raise ValueError('M2 body rotation must be orthonormal')
    determinant = (matrix[0] * (matrix[5] * matrix[10] - matrix[6] * matrix[9]) -
                   matrix[1] * (matrix[4] * matrix[10] - matrix[6] * matrix[8]) +
                   matrix[2] * (matrix[4] * matrix[9] - matrix[5] * matrix[8]))
    if abs(determinant - 1.) > 1e-6:
        raise ValueError('M2 body transform must be a proper rotation')


def validate_fixture_observation(observation, spec, rolling=False):
    """Synthetic odom occupancy; body motion is accepted only by the rolling candidate."""
    if set(observation) != OBSERVATION_FIELDS:
        raise ValueError('M2 fixture must contain only public occupancy fields')
    header, context = observation['header'], observation['context']
    if (header['schema_version'] != '0.1' or header['source_type'] != 'fixture' or
            observation['observed_domain_source'] != DOMAIN or header['frame_id'] != spec['frame_id']):
        raise ValueError('not an explicit M2 inverse-observation fixture')
    for key in ('run_id', 'clock_id', 'sample_id'):
        if not isinstance(header[key], str) or not header[key].strip():
            raise ValueError('invalid M2 fixture identity')
    if (type(header['timestamp']) is not int or not 0 <= header['timestamp'] < 2**63 or
            header['status'] not in ('valid', 'degraded', 'unavailable') or
            not isinstance(header['reason'], str) or
            (header['status'] != 'valid' and not header['reason'].strip())):
        raise ValueError('invalid M2 fixture timestamp, status or reason')
    identity = [float(row == col) for row in range(4) for col in range(4)]
    if (context['clock_id'] != header['clock_id'] or
            context['reference_timestamp'] != header['timestamp'] or
            context['mapping_frame_id'] != 'odom' or context['source_frame_id'] != 'odom' or
            context['calibration_id'] != spec['calibration_id'] or context['state_source'] != 'fixture'):
        raise ValueError('M2 fixture context is not the declared observation-time identity')
    for key in ('T_mapping_source', 'T_mapping_body'):
        status = context[key + '_status']
        if rolling and status == 'unavailable' and header['status'] != 'valid':
            continue
        if status != 'available':
            raise ValueError('M2 valid fixture requires available transforms')
        if rolling and key == 'T_mapping_body':
            _validate_body_transform(context[key])
        elif list(context[key]) != identity or any(not _finite(value) for value in context[key]):
            raise ValueError('M2 fixture requires declared identity source/fixed transforms')
    _validate_quality(dict(uncertainty=context['pose_uncertainty']))
    for key in ('resolution', 'shape'):
        if list(observation[key]) != list(spec[key]):
            raise ValueError('M2 fixture geometry differs from configuration')
    if rolling:
        lattice_offset(observation['origin'], spec['origin'], spec['resolution'])
    elif list(observation['origin']) != list(spec['origin']):
        raise ValueError('M2 fixed fixture origin differs from configuration')
    voxels = observation['voxels']
    if not isinstance(voxels, list) or (header['status'] != 'valid' and voxels):
        raise ValueError('nonvalid M2 fixture cannot carry evidence')
    indices = set()
    for voxel in voxels:
        index, probability = voxel['index'], voxel['probability']
        if (len(index) != 3 or any(type(value) is not int or not 0 <= value < spec['shape'][axis]
                                 for axis, value in enumerate(index)) or tuple(index) in indices):
            raise ValueError('M2 fixture index invalid or duplicated')
        indices.add(tuple(index))
        if not _finite(probability) or not 0 < probability < 1 or type(voxel['observed']) is not bool:
            raise ValueError('M2 evidence probability or observed flag invalid')
        if not voxel['observed'] and probability != spec['neutral_probability']:
            raise ValueError('unobserved fixture must retain the neutral probability slot')
        _validate_quality(voxel)
