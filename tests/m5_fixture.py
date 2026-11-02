"""Small private terrain inputs and explicit mutations; no terrain candidate."""
import copy
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'configs/m5_terrain_fixture.yaml'


def load_spec():
    return yaml.safe_load(CONFIG.read_text())


def set_path(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = copy.deepcopy(replacement)


def input_cases(spec):
    """Acceptance expectations are declared here before any candidate exists."""
    cases = [dict(name='T1_T2_baseline_centers', accepts=True, spec=copy.deepcopy(spec))]
    variants = (
        ('T3_zero_height', ('grid', 'heights', 0), 0., True),
        ('T4_no_data_has_height', ('grid', 'heights', 2), 12., False),
        ('T4_valid_height_null', ('grid', 'heights', 0), None, False),
        ('T4_mask_integer', ('grid', 'no_data_mask', 0), 0, False),
        ('T4_mask_false_null', ('grid', 'no_data_mask', 2), False, False),
        ('T7_missing_datum_id', ('vertical', 'datum_id'), '', False),
        ('T7_required_grid_missing', ('vertical', 'required_grids'), ['missing-geoid.gtx'], False),
        ('T7_optional_grid_skipped', ('vertical', 'required_grids'), ['@missing-geoid.gtx'], False),
        ('T7_ballpark_operation', ('vertical', 'operation'), 'ballpark', False),
        ('T7_ellipsoidal_without_conversion', ('vertical', 'height_type'), 'ellipsoidal', False),
        ('T7_missing_target_vertical_datum', ('map_grid', 'vertical_datum_id'), '', False),
        ('T8_equal_eligibility_bounds', ('eligibility', 'valid_interval_ns'), [100,100], False),
        ('T8_eligibility_after_registration', ('eligibility', 'valid_interval_ns'), [100,301], False),
        ('T8_bad_registration_bounds', ('registration', 'valid_interval_ns'), [300,0], False),
        ('T9_no_authorization', ('eligibility', 'policy'), '', False),
        ('T9_wall_clock_substitution', ('source_time', 'clock_id'), 'sim:m5-fixture', False),
        ('T9_false_precision_zero', ('source_time', 'precision_ns'), 0, False),
        ('T9_publication_before_acquisition', ('source_time', 'publication_ns'), 9, False),
        ('T10_foreign_clock', ('registration', 'clock_id'), 'other', False),
        ('T10_eligibility_wrong_run', ('eligibility', 'run_id'), 'other', False),
        ('T10_missing_registration', ('registration', 'status'), 'unavailable', False),
        ('T10_wrong_frame', ('registration', 'target_frame'), 'odom', False),
        ('T12_too_many_axis_samples', ('grid', 'rows'), 5, False),
        ('T12_no_boolean_capacity', ('limits', 'max_tiles'), True, False),
        ('T12_cannot_enlarge_byte_limit', ('limits', 'max_input_bytes'), 32768, False),
        ('T14_dsm_is_not_dtm', ('identity', 'product_kind'), 'DSM', False),
        ('T14_unknown_product', ('identity', 'product_kind'), 'unknown', False),
        ('T14_real_source', ('identity', 'source_kind'), 'measured', False),
        ('T14_lat_lon_axes', ('horizontal', 'axis_order'), ['lat','lon'], False),
        ('T14_feet_units', ('vertical', 'unit'), 'ft', False),
        ('T14_pixel_corner', ('grid', 'sample_anchor'), 'corner', False),
        ('T14_rotation', ('grid', 'affine', 2), .1, False),
        ('T14_map_resolution_mismatch', ('map_grid', 'resolution_xy'), [1.,2.], False),
        ('T14_half_cell_registration', ('registration', 'T_map_terrain', 3), 10.5, False),
        ('T15_probability_is_not_height', ('grid', 'height_quality', 0, 'kind'), 'occupancy_probability_interval', False),
        ('T15_variance_is_not_interval', ('grid', 'height_quality', 0, 'unit'), 'm2', False),
        ('T15_interval_excludes_nominal', ('grid', 'height_quality', 0, 'value'), [0.,1.], False),
        ('T15_registration_interval_excludes_shift', ('registration', 'height_quality', 'value'), [-.1,.1], False),
        ('T15_no_data_has_quality', ('grid', 'height_quality', 2),
            dict(status='available', kind='height_interval', value=[0.,1.], unit='m', source='fixture'), False),
    )
    for name, path, replacement, accepts in variants:
        value = copy.deepcopy(spec)
        set_path(value, path, replacement)
        if name == 'T3_zero_height':
            value['grid']['height_quality'][0] = unavailable_quality()
        cases.append(dict(name=name, accepts=accepts, spec=value))
    for name, path in (('T15_missing_sample_quality', ('grid','height_quality',0)),
                       ('T15_missing_registration_quality', ('registration','height_quality'))):
        value = copy.deepcopy(spec)
        set_path(value, path, unavailable_quality())
        cases.append(dict(name=name, accepts=True, spec=value))
    for field in ('lidar', 'target', 'observed_mask'):
        value = copy.deepcopy(spec)
        value['grid'][field] = []
        cases.append(dict(name='T13_reject_' + field, accepts=False, spec=value))
    return cases


def unavailable_quality():
    return dict(status='unavailable', kind='', value=None, unit='', source='fixture_quality_missing_v1')


def query_request(spec, timestamp, point=(111.,179.)):
    return dict(run_id=spec['registration']['run_id'], clock_id=spec['registration']['clock_id'],
                frame_id='map', query_timestamp=timestamp, point_xy=list(point))


def future_events(spec, expected):
    """Materialize saved declarations without running install/query/expiration logic."""
    events = copy.deepcopy(expected['future_events'])
    for event in events:
        if event['operation'].startswith('install'):
            payload = copy.deepcopy(spec)
            payload['identity']['dataset_version'] = event['version']
            if event['operation'] == 'install_conflicting':
                payload['grid']['heights'][0] = 20.
                payload['grid']['height_quality'][0]['value'] = [19.75,20.25]
            elif event['operation'] == 'install_bad_tile':
                payload['grid']['no_data_mask'][0] = True
            event['input'] = payload
        else:
            event['request'] = query_request(spec,event['timestamp_ns'])
    return events
