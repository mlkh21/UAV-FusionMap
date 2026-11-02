"""Validate backend output against the submitted observation and configured grid."""
import math
from numbers import Real

from .input_contract import validate_transform
from .placeholder import grid_origin


def _finite(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def validate_geometry(resolution, shape, origin):
    if (len(resolution) != 3 or len(shape) != 3 or len(origin) != 3 or
            any(not _finite(value) or value <= 0 for value in resolution) or
            any(type(value) is not int or not 0 < value < 2**31 for value in shape) or
            any(not _finite(value) for value in origin)):
        raise ValueError('invalid occupancy grid geometry')


def _quality(voxel):
    confidence = voxel.get('confidence')
    if confidence is not None and (not _finite(confidence) or not 0 <= confidence <= 1):
        raise ValueError('invalid confidence')
    uncertainty = voxel['uncertainty']
    status, values = uncertainty['status'], uncertainty['value']
    if status == 'unavailable':
        if values is not None:
            raise ValueError('unavailable uncertainty must be None')
        for key in ('kind', 'unit', 'source'):
            if not isinstance(uncertainty[key], str):
                raise ValueError('uncertainty metadata must be text')
    elif status == 'available':
        if (any(not isinstance(uncertainty[key], str) or not uncertainty[key].strip()
                for key in ('kind', 'unit', 'source')) or
                not isinstance(values, (list, tuple)) or not values or
                any(not _finite(value) for value in values)):
            raise ValueError('invalid available uncertainty')
        if uncertainty['kind'] == 'occupancy_variance' and (len(values) != 1 or values[0] < 0):
            raise ValueError('invalid occupancy_variance')
    else:
        raise ValueError('unknown uncertainty status')


def validate_output(observation, bundle, mode, resolution, shape, origin, rolling_grid=False):
    source, header = bundle['header'], observation['header']
    expected = dict(schema_version='0.1', run_id=source['run_id'], clock_id=source['clock_id'],
                    timestamp=source['timestamp'], sample_id='perception.occupancy:' + source['sample_id'],
                    frame_id='odom', source_type={'disabled': 'derived', 'placeholder': 'fixture',
                                                 'research': 'model'}[mode])
    if any(header[key] != value for key, value in expected.items()):
        raise ValueError('backend output identity, timestamp, frame or source mismatch')
    status, reason = header['status'], header['reason']
    if (status not in ('valid', 'degraded', 'unavailable') or not isinstance(reason, str) or
            (status != 'valid' and not reason.strip())):
        raise ValueError('backend output status or reason invalid')
    if type(header['timestamp']) is not int:
        raise ValueError('backend timestamp must be int64')
    context, original = observation['context'], bundle['context']
    if (context['source_frame_id'] != 'odom' or context['mapping_frame_id'] != 'odom' or
            context['reference_timestamp'] != source['timestamp'] or
            context['clock_id'] != source['clock_id']):
        raise ValueError('backend output context frame or time mismatch')
    for key in ('calibration_id', 'T_mapping_body', 'T_mapping_body_status',
                'T_mapping_source_status', 'state_source', 'pose_uncertainty'):
        if context[key] != original[key]:
            raise ValueError('backend changed observation context: ' + key)
    _quality(dict(uncertainty=context['pose_uncertainty']))
    identity = [float(row == col) for row in range(4) for col in range(4)]
    if list(context['T_mapping_source']) != identity:
        raise ValueError('odom occupancy requires explicit identity source transform')
    if status == 'valid':
        if source['status'] != 'valid' or any(context[key] != 'available' for key in
                ('T_mapping_source_status', 'T_mapping_body_status')):
            raise ValueError('backend marked unavailable input or transforms valid')
        validate_transform(context['T_mapping_body'])
    expected_origin = grid_origin(bundle, resolution, shape, origin,
                                  rolling_grid and status == 'valid')
    validate_geometry(observation['resolution'], observation['shape'], observation['origin'])
    if (tuple(observation['resolution']) != tuple(resolution) or
            tuple(observation['shape']) != tuple(shape) or
            tuple(observation['origin']) != expected_origin):
        raise ValueError('backend output grid differs from configured geometry')
    domain = observation['observed_domain_source']
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError('backend output observed domain is missing')
    voxels = observation['voxels']
    if not isinstance(voxels, list) or (status != 'valid' and voxels):
        raise ValueError('nonvalid backend output must not contain voxel evidence')
    indices = set()
    for voxel in voxels:
        index = voxel['index']
        if (len(index) != 3 or any(type(value) is not int or not 0 <= value < shape[axis]
                                 for axis, value in enumerate(index))):
            raise ValueError('backend voxel index invalid')
        if tuple(index) in indices:
            raise ValueError('backend output contains duplicate voxel indices')
        indices.add(tuple(index))
        probability = voxel['probability']
        if not _finite(probability) or not 0 <= probability <= 1 or type(voxel['observed']) is not bool:
            raise ValueError('backend voxel probability or observed flag invalid')
        _quality(voxel)
