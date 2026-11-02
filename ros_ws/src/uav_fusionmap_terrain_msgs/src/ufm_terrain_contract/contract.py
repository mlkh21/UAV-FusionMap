"""Public logical v1 terrain values. Optional wire slots are None here."""
from fractions import Fraction as F

from .bounds import (MESSAGE_BYTES, REQUEST_BYTES, array, bounded_json, fields,
                     integer, interval, number, reason, text)

QUALITY_STATUS = {'unavailable': 0, 'available': 1}
QUERY_STATUS = {'valid': 0, 'unknown': 1, 'stale': 2, 'unavailable': 3}
STATES = dict(disabled=0, waiting_clock=1, empty=2, current=3, expired=4, unavailable=5, locked=6)
OUTCOMES = dict(none=0, installed=1, idempotent=2, rejected=3)
REQUEST_FIELDS = ('terrain_id run_id clock_id frame_id query_timestamp point_xy pin_version '
                  'expected_provider_instance_id expected_terrain_revision')
CONTEXT_FIELDS = ('terrain_id dataset_version tile_id profile product_kind source_kind evidence_role source_ref '
    'run_id clock_id acquisition_ns publication_ns precision_ns source_clock_id dataset_epoch '
    'source_horizontal_crs_id source_frame source_axis_order source_vertical_datum_id source_height_type '
    'vertical_operation required_grids target_horizontal_crs_id target_vertical_datum_id target_frame '
    'length_unit rows columns affine sample_anchor map_origin_xy map_resolution_xy registration_id '
    'registration_source horizontal_alignment T_map_terrain registration_valid_interval_ns registration_quality '
    'eligibility_policy eligibility_valid_interval_ns installed_timestamp')
RESULT_FIELDS = ('protocol_version provider_instance_id terrain_id run_id clock_id frame_id query_timestamp '
    'point_xy evaluation_timestamp terrain_revision status reason context height source_index source_xy '
    'height_quality sample_quality')
STATUS_FIELDS = ('protocol_version provider_instance_id terrain_id run_id clock_id frame_id status_sequence '
    'terrain_revision evaluation_timestamp state reason context last_attempt_id last_install_outcome last_install_reason')


def unavailable_quality(source=''):
    return dict(status='unavailable', kind='', value=None, unit='', source=source)


def validate_quality(value, kind=None, nominal=None):
    fields(value, 'status kind value unit source')
    text(value['source'], empty=value['status'] == 'unavailable')
    if value['status'] == 'unavailable':
        if value['kind'] != '' or value['unit'] != '' or value['value'] is not None:
            raise ValueError('terrain_unavailable_quality_slots')
    elif value['status'] == 'available':
        if (value['kind'] not in ('height_interval', 'height_offset_interval') or
                kind is not None and value['kind'] != kind or value['unit'] != 'm'):
            raise ValueError('terrain_quality_role_or_unit')
        array(value['value'], 2)
        low, high = value['value']
        if low > high or nominal is not None and not low <= nominal <= high:
            raise ValueError('terrain_quality_interval')
    else:
        raise ValueError('terrain_quality_enum')


def validate_request(value):
    fields(value, REQUEST_FIELDS)
    for key in ('terrain_id', 'run_id', 'clock_id', 'frame_id'):
        text(value[key])
    integer(value['query_timestamp'])
    array(value['point_xy'], 2)
    if type(value['pin_version']) is not bool:
        raise ValueError('terrain_pin_flag')
    text(value['expected_provider_instance_id'], empty=not value['pin_version'])
    integer(value['expected_terrain_revision'], 64)
    if value['pin_version']:
        if value['expected_terrain_revision'] == 0:
            raise ValueError('terrain_pin_revision')
    elif value['expected_provider_instance_id'] != '' or value['expected_terrain_revision'] != 0:
        raise ValueError('terrain_unpinned_slots')
    bounded_json(value, REQUEST_BYTES)


def validate_context(value):
    fields(value, CONTEXT_FIELDS)
    fixed = dict(profile='m5_fixture_v1', product_kind='DTM', source_kind='fixture', evidence_role='prior',
        source_clock_id='dataset:m5-fixture', dataset_epoch='fixture-epoch-0',
        source_horizontal_crs_id='fixture:terrain_xy_v1', source_frame='terrain_fixture',
        source_axis_order=['x', 'y'], source_vertical_datum_id='fixture:terrain_height_zero_v1',
        source_height_type='local_height', vertical_operation='fixed_translation_fixture_v1', required_grids=[],
        target_horizontal_crs_id='fixture:map_xy_v1', target_vertical_datum_id='fixture:map_height_zero_v1',
        target_frame='map', length_unit='m', sample_anchor='center', registration_source='fixture',
        horizontal_alignment='exact_fixture_v1', eligibility_policy='fixture_run_authorization_v1')
    if any(value[k] != v for k, v in fixed.items()):
        raise ValueError('terrain_context_profile_or_datum')
    for key in ('terrain_id', 'dataset_version', 'tile_id', 'source_ref', 'run_id', 'clock_id', 'registration_id'):
        text(value[key])
    if value['clock_id'] != 'sim:' + value['run_id']:
        raise ValueError('terrain_context_clock_domain')
    for key in ('acquisition_ns', 'publication_ns', 'precision_ns', 'installed_timestamp'):
        integer(value[key])
    if value['precision_ns'] == 0 or value['publication_ns'] < value['acquisition_ns']:
        raise ValueError('terrain_context_source_time')
    for key in ('rows', 'columns'):
        integer(value[key], 32)
        if not 1 <= value[key] <= 4:
            raise ValueError('terrain_context_axis_limit')
    a, matrix = value['affine'], value['T_map_terrain']
    array(a, 6)
    array(matrix, 16)
    if a[1] <= 0 or a[5] >= 0 or a[2] != 0 or a[4] != 0:
        raise ValueError('terrain_context_affine')
    if (any(matrix[i] != int(i // 4 == i % 4) for i in range(16) if i not in (3, 7, 11)) or
            not any(matrix[i] for i in (3, 7, 11))):
        raise ValueError('terrain_context_translation')
    array(value['map_origin_xy'], 2)
    array(value['map_resolution_xy'], 2)
    if value['map_resolution_xy'] != [a[1], -a[5]]:
        raise ValueError('terrain_context_resolution')
    for corner, shift, origin, resolution in zip((a[0], a[3]), (matrix[3], matrix[7]),
            value['map_origin_xy'], value['map_resolution_xy']):
        offset = (F(str(corner)) + F(str(shift)) - F(str(origin))) / F(str(resolution))
        if offset.denominator != 1:
            raise ValueError('terrain_context_lattice')
    reg, eligibility = value['registration_valid_interval_ns'], value['eligibility_valid_interval_ns']
    interval(reg)
    interval(eligibility)
    if not reg[0] <= eligibility[0] < eligibility[1] <= reg[1]:
        raise ValueError('terrain_context_authorization')
    if not eligibility[0] <= value['installed_timestamp'] < eligibility[1]:
        raise ValueError('terrain_context_install_time')
    validate_quality(value['registration_quality'], 'height_offset_interval', matrix[11])
    bounded_json(value, MESSAGE_BYTES)


def _envelope(value):
    if type(value['protocol_version']) is not int or value['protocol_version'] != 1:
        raise ValueError('terrain_protocol_version')
    for key in ('provider_instance_id', 'terrain_id', 'run_id', 'clock_id', 'frame_id'):
        text(value[key])
    integer(value['terrain_revision'], 64)
    if value['evaluation_timestamp'] is not None:
        integer(value['evaluation_timestamp'])
    reason(value['reason'])


def _bound_context(value):
    context = value['context']
    validate_context(context)
    if (value['terrain_revision'] == 0 or value['evaluation_timestamp'] is None or
            any(value[k] != context[k] for k in ('terrain_id', 'run_id', 'clock_id')) or
            value['frame_id'] != context['target_frame']):
        raise ValueError('terrain_context_identity_or_revision')
    now = value['evaluation_timestamp']
    start, end = context['registration_valid_interval_ns']
    if not start <= now < end or now < context['installed_timestamp']:
        raise ValueError('terrain_context_evaluation_time')
    return context


def validate_result(value, request=None, provider_instance_id=None):
    fields(value, RESULT_FIELDS)
    _envelope(value)
    integer(value['query_timestamp'])
    array(value['point_xy'], 2)
    if type(value['status']) is not str or value['status'] not in QUERY_STATUS:
        raise ValueError('terrain_result_enum')
    validate_quality(value['height_quality'], 'height_interval')
    validate_quality(value['sample_quality'], 'height_interval')
    if request is not None:
        validate_request(request)
        if any(value[k] != request[k] for k in ('terrain_id', 'run_id', 'clock_id', 'frame_id',
                                               'query_timestamp', 'point_xy')):
            raise ValueError('terrain_request_echo_mismatch')
        if request['pin_version'] and value['status'] != 'unavailable' and (
                value['provider_instance_id'] != request['expected_provider_instance_id'] or
                value['terrain_revision'] != request['expected_terrain_revision']):
            raise ValueError('terrain_pin_mismatch')
    if provider_instance_id is not None and value['provider_instance_id'] != provider_instance_id:
        raise ValueError('terrain_instance_mismatch')
    if value['status'] == 'unavailable':
        if (not value['reason'] or any(value[k] is not None for k in
                ('context', 'height', 'source_index', 'source_xy')) or
                any(value[k]['status'] != 'unavailable' for k in ('height_quality', 'sample_quality'))):
            raise ValueError('terrain_unavailable_payload')
        if value['reason'] == 'request_domain_mismatch' and value['terrain_revision'] != 0:
            raise ValueError('terrain_foreign_revision')
    else:
        context = _bound_context(value)
        stamp, now = value['query_timestamp'], value['evaluation_timestamp']
        reg = context['registration_valid_interval_ns']
        eligible = context['eligibility_valid_interval_ns']
        if not max(context['installed_timestamp'], eligible[0], reg[0]) <= stamp <= now or stamp >= reg[1]:
            raise ValueError('terrain_result_query_time')
        expired = max(stamp, now) >= eligible[1]
        if (value['status'] == 'stale') != expired:
            raise ValueError('terrain_expiry_status')
        if value['status'] == 'stale' and value['reason'] != 'terrain_expired':
            raise ValueError('terrain_stale_reason')
        a, matrix = context['affine'], context['T_map_terrain']
        col = (F(str(value['point_xy'][0])) - F(str(matrix[3])) - F(str(a[0]))) / F(str(a[1])) - F(1, 2)
        row = (F(str(value['point_xy'][1])) - F(str(matrix[7])) - F(str(a[3]))) / F(str(a[5])) - F(1, 2)
        if row.denominator != 1 or col.denominator != 1:
            raise ValueError('terrain_result_noncenter')
        inside = 0 <= row < context['rows'] and 0 <= col < context['columns']
        if inside:
            array(value['source_index'], 2, lambda x: integer(x, 32))
            array(value['source_xy'], 2)
            expected_xy = [float(F(str(a[0])) + (col + F(1, 2)) * F(str(a[1]))),
                           float(F(str(a[3])) + (row + F(1, 2)) * F(str(a[5])))]
            if value['source_index'] != [int(row), int(col)] or value['source_xy'] != expected_xy:
                raise ValueError('terrain_source_sample_mismatch')
        elif value['source_index'] is not None or value['source_xy'] is not None or value['height'] is not None:
            raise ValueError('terrain_outside_payload')
        if value['height'] is None:
            if any(value[k]['status'] != 'unavailable' for k in ('height_quality', 'sample_quality')):
                raise ValueError('terrain_missing_height_quality')
        else:
            number(value['height'])
            validate_quality(value['height_quality'], nominal=value['height'])
            if value['sample_quality']['status'] == 'available':
                try:
                    translated = [float(F(str(x)) + F(str(matrix[11]))) for x in value['sample_quality']['value']]
                except OverflowError as exc:
                    raise ValueError('terrain_quality_translation_overflow') from exc
                if not translated[0] <= value['height'] <= translated[1]:
                    raise ValueError('terrain_sample_quality_nominal')
            complete = all(q['status'] == 'available' for q in
                           (value['sample_quality'], context['registration_quality']))
            if (value['height_quality']['status'] == 'available') != complete:
                raise ValueError('terrain_missing_quality_contribution')
            if complete:
                for i, bound in enumerate(value['height_quality']['value']):
                    total = F(str(value['sample_quality']['value'][i])) + F(str(context['registration_quality']['value'][i]))
                    if (i == 0 and F.from_float(float(bound)) > total or
                            i == 1 and F.from_float(float(bound)) < total):
                        raise ValueError('terrain_quality_inward_bound')
        if value['status'] == 'valid' and (value['height'] is None or not inside or value['reason'] != ''):
            raise ValueError('terrain_valid_payload')
        if value['status'] == 'unknown' and (value['height'] is not None or
                value['reason'] != ('no_data' if inside else 'outside_coverage')):
            raise ValueError('terrain_unknown_payload')
    bounded_json(value, MESSAGE_BYTES)


def validate_status(value):
    fields(value, STATUS_FIELDS)
    _envelope(value)
    for key in ('status_sequence', 'last_attempt_id'):
        integer(value[key], 64)
    if value['status_sequence'] == 0:
        raise ValueError('terrain_status_sequence')
    if (type(value['state']) is not str or value['state'] not in STATES or
            type(value['last_install_outcome']) is not str or value['last_install_outcome'] not in OUTCOMES):
        raise ValueError('terrain_status_enum')
    reason(value['last_install_reason'])
    if value['last_install_outcome'] == 'none':
        if value['last_attempt_id'] != 0 or value['last_install_reason'] != '':
            raise ValueError('terrain_install_none_slots')
    elif value['last_attempt_id'] == 0 or (value['last_install_outcome'] == 'rejected' and not value['last_install_reason']):
        raise ValueError('terrain_install_attempt')
    if value['state'] in ('current', 'expired'):
        context = _bound_context(value)
        expired = value['evaluation_timestamp'] >= context['eligibility_valid_interval_ns'][1]
        if expired != (value['state'] == 'expired'):
            raise ValueError('terrain_status_expiry')
    elif value['context'] is not None:
        raise ValueError('terrain_status_context')
    if value['state'] == 'waiting_clock' and value['evaluation_timestamp'] is not None:
        raise ValueError('terrain_waiting_clock_time')
    if value['last_install_outcome'] in ('installed', 'idempotent') and value['terrain_revision'] == 0:
        raise ValueError('terrain_install_revision')
    bounded_json(value, MESSAGE_BYTES)
