"""Explicit M4 synthetic registration/input contract; no Scene Map or ROS execution."""
from fractions import Fraction
import math

from .m3_contract import validate_spec as validate_local_spec
from .m3_contract import validate_fixture_observation as validate_local_observation


def _fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError('M4 ' + label + ' fields differ')


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('M4 requires explicit ' + label)


def _xyz(value, label, *, positive=False, integer=False):
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(
            not _finite(v) or positive and v <= 0 or
            integer and (type(v) is not int or v >= 2**31) for v in value):
        raise ValueError('M4 invalid XYZ ' + label)


def _fraction(value):
    return Fraction(str(value))


def _integral_offset(first, second, resolution):
    values = [(_fraction(a) - _fraction(b)) / _fraction(r)
              for a, b, r in zip(first, second, resolution)]
    if any(value.denominator != 1 for value in values):
        raise ValueError('M4 requires exact whole-cell lattice alignment')
    return tuple(int(value) for value in values)


def validate_spec(spec):
    _fields(spec, 'schema_version fixture_only enabled_by_default local_map scene registration '
                  'max_sealed_submaps', 'configuration')
    if (spec['schema_version'] != 'm4_fixture.v1' or spec['fixture_only'] is not True or
            spec['enabled_by_default'] is not False):
        raise ValueError('M4 fixture must be explicit and disabled by default')
    validate_local_spec(spec['local_map'])
    scene, registration = spec['scene'], spec['registration']
    _fields(scene, 'map_id frame_id resolution shape origin', 'scene')
    if scene['map_id'] != 'm4-scene-fixture' or scene['frame_id'] != 'map':
        raise ValueError('M4 scene identity differs from profile')
    _xyz(scene['resolution'], 'resolution', positive=True)
    _xyz(scene['shape'], 'shape', positive=True, integer=True)
    _xyz(scene['origin'], 'origin')
    local = spec['local_map']['arithmetic']
    if list(scene['resolution']) != list(local['resolution']):
        raise ValueError('M4 does not resample local resolution')
    if type(spec['max_sealed_submaps']) is not int or not 0 < spec['max_sealed_submaps'] < 2**31:
        raise ValueError('M4 max_sealed_submaps must be a positive int32')
    _fields(registration, 'registration_id source_frame target_frame source status run_id clock_id '
                         'valid_from_ns valid_until_ns T_map_odom', 'registration')
    for key in ('registration_id', 'run_id', 'clock_id'):
        _text(registration[key], key)
    if (registration['source_frame'] != 'odom' or registration['target_frame'] != 'map' or
            registration['source'] != 'fixture' or registration['status'] != 'available'):
        raise ValueError('M4 requires declared available fixture map-from-odom registration')
    start, end = registration['valid_from_ns'], registration['valid_until_ns']
    if (type(start) is not int or type(end) is not int or not 0 <= start < end < 2**63):
        raise ValueError('M4 registration requires explicit half-open int64 time interval')
    matrix = registration['T_map_odom']
    if not isinstance(matrix, (list, tuple)) or len(matrix) != 16 or any(not _finite(v) for v in matrix):
        raise ValueError('M4 registration must be finite 4x4')
    if any(matrix[i] != float(i // 4 == i % 4) for i in range(16) if i not in (3, 7, 11)):
        raise ValueError('M4 registration supports only fixed translation, no rotation')
    translation = [matrix[i] for i in (3, 7, 11)]
    if not any(translation):
        raise ValueError('M4 fixture requires explicit nonzero translation')
    _integral_offset(translation, [0, 0, 0], scene['resolution'])
    translated = [float(_fraction(a) + _fraction(b)) for a, b in zip(local['origin'], translation)]
    _integral_offset(translated, scene['origin'], scene['resolution'])
    _validate_window(local['origin'], spec)


def validate_registration_time(spec, timestamp, run_id, clock_id):
    """Caller validates the full immutable spec once; each input/query binds its domain."""
    registration = spec['registration']
    if (run_id, clock_id) != (registration['run_id'], registration['clock_id']):
        raise ValueError('M4 registration run or clock mismatch')
    if (type(timestamp) is not int or not registration['valid_from_ns'] <= timestamp <
            registration['valid_until_ns']):
        raise ValueError('M4 timestamp outside registration validity')


def _validate_window(origin, spec):
    local, scene = spec['local_map']['arithmetic'], spec['scene']
    translation = [spec['registration']['T_map_odom'][i] for i in (3, 7, 11)]
    for axis in range(3):
        start = _fraction(origin[axis]) + _fraction(translation[axis])
        end = start + _fraction(local['resolution'][axis]) * local['shape'][axis]
        lower = _fraction(scene['origin'][axis])
        upper = lower + _fraction(scene['resolution'][axis]) * scene['shape'][axis]
        if not lower <= start < end <= upper:
            raise ValueError('M4 complete active window outside Scene envelope')


def validate_fixture_observation(observation, spec):
    """Stateless preflight only: ordering/dedup and directory transactions need the future candidate."""
    validate_spec(spec)
    validate_local_observation(observation, spec['local_map'], rolling=True)
    header, context = observation['header'], observation['context']
    # Keep training/undeclared side channels out even when a generic codec would omit them.
    _fields(header, 'schema_version run_id clock_id sample_id timestamp frame_id source_type status reason',
            'occupancy header')
    _fields(context, 'reference_timestamp clock_id source_frame_id mapping_frame_id T_mapping_source '
                    'T_mapping_source_status T_mapping_body T_mapping_body_status calibration_id '
                    'state_source pose_uncertainty', 'spatial context')
    _fields(context['pose_uncertainty'], 'status kind value unit source', 'pose uncertainty')
    validate_registration_time(spec, header['timestamp'], header['run_id'], header['clock_id'])
    local = spec['local_map']['arithmetic']
    _xyz(observation['origin'], 'observation origin')
    _xyz(observation['shape'], 'observation shape', positive=True, integer=True)
    _xyz(observation['resolution'], 'observation resolution', positive=True)
    _integral_offset(observation['origin'], local['origin'], local['resolution'])
    if header['status'] != 'valid':
        return  # Nonvalid placeholder transforms are not dereferenced and cannot move the window.
    body = context['T_mapping_body']
    origin = []
    for axis in range(3):
        anchor, resolution = local['origin'][axis], local['resolution'][axis]
        # Match the existing M3 rolling window's intermediate float arithmetic.
        # Rational geometry remains useful for exact lattice/envelope checks,
        # but must not predict a different active window near a float64 tie.
        relative = (body[4 * axis + 3] - anchor - local['shape'][axis] * resolution / 2) / resolution
        if not math.isfinite(relative):
            raise ValueError('M4 body position exceeds finite active lattice')
        shift = math.floor(relative + .5)
        origin.append(anchor + shift * resolution)
    _validate_window(origin, spec)
