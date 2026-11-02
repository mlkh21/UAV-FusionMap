"""Private, stateless M5 fixture input checks; no terrain/map backend or GIS imports."""
from fractions import Fraction
import json
import math


LIMITS = dict(max_tiles=1, max_axis_samples=4, max_samples_per_tile=16,
              max_total_samples=16, max_input_bytes=16384, max_receipt_events=64)


def _fields(value, names, name):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError('M5 ' + name + ' fields differ from the private contract')


def _text(value, name):
    if isinstance(value, str) and len(value) > LIMITS['max_input_bytes']:
        raise ValueError('M5 ' + name + ' exceeds input byte limit before text encoding')
    if not isinstance(value, str) or not value.strip():
        raise ValueError('M5 ' + name + ' requires nonempty text')


def _number(value, name):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError('M5 ' + name + ' requires finite numbers, not booleans')


def _time(value, name):
    if type(value) is not int or not 0 <= value < 2**63:
        raise ValueError('M5 ' + name + ' requires nonnegative int64 nanoseconds')


def _interval(value, name):
    _array(value, 2, name)
    for item in value:
        _time(item, name)
    if value[0] >= value[1]:
        raise ValueError('M5 ' + name + ' requires an ordered half-open interval')


def _array(value, length, name):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError('M5 ' + name + ' has wrong array length/type')


def _numbers(value, length, name):
    _array(value, length, name)
    for item in value:
        _number(item, name)


def _quality(value, nominal, kind):
    _fields(value, 'status kind value unit source', 'height quality')
    _text(value['source'], 'height quality source')
    if value['status'] == 'unavailable':
        if value['kind'] != '' or value['unit'] != '' or value['value'] is not None:
            raise ValueError('M5 unavailable quality must retain empty kind/unit and null value')
    elif value['status'] == 'available':
        if nominal is None or value['kind'] != kind or value['unit'] != 'm':
            raise ValueError('M5 height quality kind/unit or no-data nominal invalid')
        _numbers(value['value'], 2, 'height interval')
        if not value['value'][0] <= nominal <= value['value'][1]:
            raise ValueError('M5 height interval must contain the nominal height')
    else:
        raise ValueError('M5 quality status is not supported')


def validate_spec(spec):
    """Validate one small immutable fixture tile. Does not normalize or mutate input."""
    _fields(spec, 'schema_version fixture_only enabled_by_default identity source_time horizontal '
                  'vertical grid map_grid registration eligibility limits', 'configuration')
    if (spec['schema_version'] != 'm5_terrain_fixture.v1' or spec['fixture_only'] is not True or
            spec['enabled_by_default'] is not False):
        raise ValueError('M5 fixture must be explicit and disabled by default')
    limits = spec['limits']
    _fields(limits, ' '.join(LIMITS), 'limits')
    if any(type(limits[k]) is not int or limits[k] != v for k, v in LIMITS.items()):
        raise ValueError('M5 limits differ from frozen fixture bounds')
    identity = spec['identity']
    _fields(identity, 'terrain_id dataset_version tile_id product_kind source_kind source_ref', 'identity')
    for key, value in identity.items():
        _text(value, key)
    if identity['source_kind'] != 'fixture' or identity['product_kind'] != 'DTM':
        raise ValueError('M5 only accepts declared fixture DTM, not real or unknown products')
    source = spec['source_time']
    _fields(source, 'acquisition_ns publication_ns precision_ns clock_id dataset_epoch', 'source time')
    for key in ('acquisition_ns', 'publication_ns', 'precision_ns'):
        _time(source[key], key)
    if source['precision_ns'] == 0 or source['publication_ns'] < source['acquisition_ns']:
        raise ValueError('M5 source time precision/order invalid')
    if source['clock_id'] != 'dataset:m5-fixture' or source['dataset_epoch'] != 'fixture-epoch-0':
        raise ValueError('M5 source time requires the declared synthetic dataset clock/epoch')
    horizontal = spec['horizontal']
    _fields(horizontal, 'crs_id frame_id axis_order unit', 'horizontal datum')
    if horizontal != dict(crs_id='fixture:terrain_xy_v1', frame_id='terrain_fixture',
                          axis_order=['x', 'y'], unit='m'):
        raise ValueError('M5 requires the explicit synthetic horizontal datum/axes/meters')
    vertical = spec['vertical']
    _fields(vertical, 'datum_id height_type unit operation required_grids', 'vertical datum')
    if vertical != dict(datum_id='fixture:terrain_height_zero_v1', height_type='local_height',
                        unit='m', operation='fixed_translation_fixture_v1', required_grids=[]):
        raise ValueError('M5 requires local fixture datum; geoid grids/real conversions unsupported')

    grid = spec['grid']
    _fields(grid, 'rows columns heights no_data_mask affine sample_anchor height_quality', 'grid')
    for axis in ('rows', 'columns'):
        if type(grid[axis]) is not int or not 1 <= grid[axis] <= limits['max_axis_samples']:
            raise ValueError('M5 grid axis exceeds fixture sample limits')
    size = grid['rows'] * grid['columns']
    if size > min(limits['max_samples_per_tile'], limits['max_total_samples']):
        raise ValueError('M5 tile/total sample limit exceeded')
    for name in ('heights', 'no_data_mask', 'height_quality'):
        _array(grid[name], size, name)
    for height, missing, quality in zip(grid['heights'], grid['no_data_mask'], grid['height_quality']):
        if type(missing) is not bool:
            raise ValueError('M5 no_data_mask contains a nonboolean value')
        if missing:
            if height is not None:
                raise ValueError('M5 no-data requires null height')
        else:
            _number(height, 'height')
        _quality(quality, height, 'height_interval')
    if grid['sample_anchor'] != 'center':
        raise ValueError('M5 only accepts explicit center samples')
    affine = grid['affine']
    _numbers(affine, 6, 'affine')
    if affine[2] != 0 or affine[4] != 0 or affine[1] <= 0 or affine[5] >= 0:
        raise ValueError('M5 only supports north-up grids, without rotation/shear')

    registration = spec['registration']
    _fields(registration, 'registration_id source_frame target_frame source status run_id clock_id '
                         'valid_interval_ns T_map_terrain horizontal_alignment height_quality', 'registration')
    for key in ('registration_id', 'run_id', 'clock_id'):
        _text(registration[key], key)
    if (registration['source_frame'] != 'terrain_fixture' or registration['target_frame'] != 'map' or
            registration['source'] != 'fixture' or registration['status'] != 'available' or
            registration['horizontal_alignment'] != 'exact_fixture_v1' or
            registration['clock_id'] != 'sim:' + registration['run_id']):
        raise ValueError('M5 registration frames/domain/status must be explicit fixture values')
    _interval(registration['valid_interval_ns'], 'registration validity')
    matrix = registration['T_map_terrain']
    _numbers(matrix, 16, 'T_map_terrain')
    if any(matrix[i] != float(i // 4 == i % 4) for i in range(16) if i not in (3, 7, 11)):
        raise ValueError('M5 registration supports fixed translation only')
    if not any(matrix[i] for i in (3, 7, 11)):
        raise ValueError('M5 fixture requires nonzero named translation')
    _quality(registration['height_quality'], matrix[11], 'height_offset_interval')
    target = spec['map_grid']
    _fields(target, 'crs_id vertical_datum_id frame_id unit origin_xy resolution_xy', 'map grid')
    _numbers(target['origin_xy'], 2, 'map origin')
    _numbers(target['resolution_xy'], 2, 'map resolution')
    if (target['crs_id'] != 'fixture:map_xy_v1' or target['vertical_datum_id'] != 'fixture:map_height_zero_v1' or
            target['frame_id'] != 'map' or target['unit'] != 'm' or
            target['resolution_xy'] != [affine[1], -affine[5]]):
        raise ValueError('M5 map grid must share fixture axes and resolution; no resampling')
    for corner, shift, origin, resolution in zip((affine[0], affine[3]), (matrix[3], matrix[7]),
                                                 target['origin_xy'], target['resolution_xy']):
        offset = (Fraction(str(corner)) + Fraction(str(shift)) - Fraction(str(origin))) / Fraction(str(resolution))
        if offset.denominator != 1:
            raise ValueError('M5 source and map lattice are not whole-cell aligned')

    eligibility = spec['eligibility']
    _fields(eligibility, 'policy run_id clock_id valid_interval_ns', 'eligibility')
    if (eligibility['policy'] != 'fixture_run_authorization_v1' or
            eligibility['run_id'] != registration['run_id'] or eligibility['clock_id'] != registration['clock_id']):
        raise ValueError('M5 requires explicit run authorization; no source-to-simulation clock subtraction')
    _interval(eligibility['valid_interval_ns'], 'eligibility')
    if not (registration['valid_interval_ns'][0] <= eligibility['valid_interval_ns'][0] <
            eligibility['valid_interval_ns'][1] <= registration['valid_interval_ns'][1]):
        raise ValueError('M5 eligibility must be contained in registration validity')


def validate_request(spec, request):
    """Check private request syntax/domain/center lattice, without returning terrain results."""
    validate_spec(spec)
    validate_request_shape(request)
    registration = spec['registration']
    if any(request[k] != registration[k] for k in ('run_id', 'clock_id')) or request['frame_id'] != 'map':
        raise ValueError('M5 request domain/frame mismatch')
    for coordinate, origin, resolution in zip(request['point_xy'], spec['map_grid']['origin_xy'],
                                             spec['map_grid']['resolution_xy']):
        index = (Fraction(str(coordinate)) - Fraction(str(origin))) / Fraction(str(resolution)) - Fraction(1, 2)
        if index.denominator != 1:
            raise ValueError('M5 request requires direct sample centers; interpolation unsupported')


def validate_request_shape(request):
    """Syntax only; a stateful layer separately reports unavailable domain/time conditions."""
    _fields(request, 'run_id clock_id frame_id query_timestamp point_xy', 'query request')
    for key in ('run_id', 'clock_id', 'frame_id'):
        _text(request[key], key)
    _time(request['query_timestamp'], 'query time')
    _numbers(request['point_xy'], 2, 'query point')


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('M5 duplicate JSON key: ' + key)
        result[key] = value
    return result


def _nonfinite_constant(value):
    raise ValueError('M5 JSON nonfinite constant: ' + value)


def load_fixture(path):
    """Read at most 16KiB+1 before decoding a single private JSON fixture."""
    with open(path, 'rb') as stream:
        payload = stream.read(LIMITS['max_input_bytes'] + 1)
    if len(payload) > LIMITS['max_input_bytes']:
        raise ValueError('M5 input byte limit exceeded before JSON decoding')
    try:
        spec = json.loads(payload.decode('utf-8'), object_pairs_hook=_unique_pairs,
                          parse_constant=_nonfinite_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('M5 input JSON encoding/depth invalid') from exc
    validate_spec(spec)
    return spec
