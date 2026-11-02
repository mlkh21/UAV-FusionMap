"""Explicit synthetic interval profile only; no accumulator, ROS or research imports."""
import math
import struct

from .m2_contract import validate_spec as validate_arithmetic
from .m2_contract import validate_fixture_observation as validate_arithmetic_observation


PROFILE = dict(kind='occupancy_probability_interval', unit='dimensionless',
    input_source='m3_fixture_bounded_inverse_v1', output_source='m3_fixture_bounded_accumulator_v1',
    unavailable_source='m3_fixture_missing_range_v1', wire_rounding='float32_nearest_even_v1')
QUALITY_FIELDS = frozenset(('status', 'kind', 'value', 'unit', 'source'))


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def wire_probability(value):
    """Resolve the nominal value before constructing input bounds; never adjust bounds."""
    if not _finite(value) or not 0 < value < 1:
        raise ValueError('M3 probability must be finite in (0,1)')
    result = struct.unpack('!f', struct.pack('!f', value))[0]
    if not 0 < result < 1:
        raise ValueError('M3 probability rounds to an excluded float32 endpoint')
    return result


def _bounds(values):
    if (not isinstance(values, (list, tuple)) or len(values) != 2 or
            any(not _finite(value) for value in values) or not 0 < values[0] <= values[1] < 1):
        raise ValueError('M3 interval must contain two finite ordered values in (0,1)')
    return values


def validate_spec(spec):
    fields = {'schema_version', 'fixture_only', 'enabled_by_default', 'arithmetic',
              'interval_profile', 'evidence_intervals'}
    if not isinstance(spec, dict) or set(spec) != fields or spec['schema_version'] != 'm3_fixture.v1':
        raise ValueError('M3 fixture configuration fields or schema differ')
    if spec['fixture_only'] is not True or spec['enabled_by_default'] is not False:
        raise ValueError('M3 fixture must be explicit and disabled by default')
    if not isinstance(spec['arithmetic'], dict):
        raise ValueError('M3 arithmetic configuration must be explicit')
    validate_arithmetic(spec['arithmetic'])
    if spec['arithmetic']['map_id'] != 'm3-fixture' or spec['interval_profile'] != PROFILE:
        raise ValueError('M3 fixture map identity or interval profile differs')
    intervals = spec['evidence_intervals']
    if not isinstance(intervals, dict) or set(intervals) != {'occupied', 'free'}:
        raise ValueError('M3 evidence intervals must be explicit occupied/free ranges')
    for kind in ('occupied', 'free'):
        lower, upper = _bounds(intervals[kind])
        configured = spec['arithmetic'][kind + '_probability']
        nominal = wire_probability(configured)
        if configured != nominal:
            raise ValueError('M3 configured evidence mean must already be float32')
        if not lower <= nominal <= upper:
            raise ValueError('M3 evidence interval excludes its wire probability')
    for key in ('minimum_probability', 'maximum_probability'):
        wire_probability(spec['arithmetic'][key])


def validate_interval_quality(probability, quality, spec, *, output=False, wire=False):
    """Internal containment is exact; wire output uses the monotone float32 rounding image.

    For a closed interval [l,u], a received float32 q can be its rounded nominal
    exactly when round32(l) <= q <= round32(u), including nearest-even ties.
    This avoids a symmetric epsilon at binade boundaries and never rewrites data.
    """
    if wire and not output:
        raise ValueError('M3 input containment cannot use an output rounding allowance')
    if not isinstance(quality, dict) or set(quality) != QUALITY_FIELDS:
        raise ValueError('M3 quality must contain only declared uncertainty fields')
    if any(not isinstance(quality[key], str) for key in ('kind', 'unit', 'source')):
        raise ValueError('M3 uncertainty metadata must be text')
    if quality['status'] == 'unavailable':
        if quality['value'] is not None:
            raise ValueError('M3 unavailable interval must have value None')
        return
    profile = spec['interval_profile']
    source = profile['output_source' if output else 'input_source']
    if (quality['status'] != 'available' or quality['kind'] != profile['kind'] or
            quality['unit'] != profile['unit'] or quality['source'] != source):
        raise ValueError('M3 interval status, kind, unit or source differs from profile')
    lower, upper = _bounds(quality['value'])
    if not _finite(probability) or not 0 < probability < 1:
        raise ValueError('M3 available interval requires finite probability in (0,1)')
    if output:
        arithmetic = spec['arithmetic']
        if not arithmetic['minimum_probability'] <= lower <= upper <= arithmetic['maximum_probability']:
            raise ValueError('M3 output interval exceeds configured clip range')
    if wire:
        if probability != wire_probability(probability):
            raise ValueError('M3 wire output mean must already be float32')
        contains = wire_probability(lower) <= probability <= wire_probability(upper)
    else:
        contains = lower <= probability <= upper
    if not contains:
        raise ValueError('M3 interval excludes its nominal probability')
    if not output and probability == spec['arithmetic']['neutral_probability'] and lower != upper:
        raise ValueError('M3 neutral evidence supports only a point interval')


def validate_fixture_observation(observation, spec, rolling=False):
    validate_spec(spec)
    validate_arithmetic_observation(observation, spec['arithmetic'], rolling=rolling)
    pose = observation['context']['pose_uncertainty']
    if not isinstance(pose, dict) or pose.get('status') != 'unavailable':
        raise ValueError('M3 fixture does not propagate available pose uncertainty')
    validate_interval_quality(None, pose, spec)
    for voxel in observation['voxels']:
        if set(voxel) != {'index', 'probability', 'observed', 'confidence', 'uncertainty'}:
            raise ValueError('M3 voxel must contain only public occupancy fields')
        if voxel['probability'] != wire_probability(voxel['probability']):
            raise ValueError('M3 input mean must be resolved to float32 before constructing its interval')
        validate_interval_quality(voxel['probability'], voxel['uncertainty'], spec)
