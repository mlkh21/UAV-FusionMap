"""Named offline test suite; it neither relaxes motion v1 nor starts a simulator."""
import copy
import json
from pathlib import Path

from ufm_scene_contract import contract as c
from ufm_scene_contract.profile import load_json, validate_profile

ROOT = Path(__file__).resolve().parents[2]
BASE_PROFILE = 'configs/sim_scene_motion_fixture.json'
LIMITS = dict(manifest_bytes=262144, depth=8, nodes=8192, text_bytes=128,
    boxes_per_template=8, epochs_per_case=2, receipts_per_stream=512,
    receipt_bytes=16777216, case_artifact_bytes=268435456,
    suite_artifact_bytes=3221225472, suite_wall_ns=1800000000000,
    angle_error_rad=.000005, range_error_m=.011, boundary_distance_m=.02, boundary_ray_limit=48)

# Each entry is a named test contract, not an arbitrary IC/scene override.
CASE_LAYOUT = (
    ('S01', [0, 0, 90], 'legacy'),
    ('S02', [0, 0, 0], 'north_wall'),
    ('S03', [0, 0, 180], 'south_wall'),
    ('S04', [10, 5, 90], 'east_wall'),
    ('S05', [0, 0, 90], 'occlusion_boxes'),
    ('S06', [0, 0, 90], 'empty'),
    ('S07', [0, 0, 90], 'moving_box'),
    ('S08', [0, 0, 90], 'east_wall'),
    ('S09', [0, 0, 90], 'east_wall'))


def _bounded(value):
    remaining = LIMITS['nodes']
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        remaining -= 1
        if remaining < 0 or depth > LIMITS['depth']:
            raise ValueError('motion_suite_structure_limit')
        if type(item) is dict:
            if len(item) > 64:
                raise ValueError('motion_suite_object_limit')
            for key, child in item.items():
                c.text(key)
                pending.append((child, depth+1))
        elif type(item) is list:
            if len(item) > 512:
                raise ValueError('motion_suite_list_limit')
            pending.extend((child, depth+1) for child in item)
        elif type(item) is str:
            c.text(item, empty=True)
        elif item is not None and type(item) is not bool:
            c.number(item)


def load_suite(path, *, base_profile_path=None):
    # Read at most the bound plus one byte, including when the file grows after stat.
    with Path(path).open('rb') as stream:
        raw = stream.read(LIMITS['manifest_bytes']+1)
    if len(raw) > LIMITS['manifest_bytes']:
        raise ValueError('motion_suite_file_limit')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('motion_suite_duplicate_key')
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError('motion_suite_nonfinite')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=nonfinite)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('motion_suite_encoding_or_depth') from exc
    validate_suite(value)
    validate_profile(load_json(base_profile_path or ROOT / BASE_PROFILE))
    return value


def validate_suite(value):
    _bounded(value)
    c.fields(value, 'schema_version suite_id base_motion_profile cases resource_limits')
    if (value['schema_version'] != 'sim_motion_multiscene_fixture.v1' or
            value['suite_id'] != 'sim-motion-multiscene-v1' or value['base_motion_profile'] != BASE_PROFILE):
        raise ValueError('motion_suite_version_or_identity')
    limits = value['resource_limits']
    c.fields(limits, ' '.join(LIMITS))
    for key, wanted in LIMITS.items():
        if type(limits[key]) is not type(wanted) or limits[key] != wanted:
            raise ValueError('motion_suite_budget')
    cases = value['cases']
    if type(cases) is not list or len(cases) != len(CASE_LAYOUT):
        raise ValueError('motion_suite_case_count')
    for row, (case_id, ic, geometry) in zip(cases, CASE_LAYOUT):
        c.fields(row, 'case_id ic_degrees geometry_id epochs fault expected_id native')
        c.vector(row['ic_degrees'], 3)
        if (row['case_id'] != case_id or row['geometry_id'] != geometry or
                row['ic_degrees'] != ic or row['expected_id'] != 'multiscene:' + case_id):
            raise ValueError('motion_suite_case_binding')
        if type(row['native']) is not bool or row['native'] != (case_id in ('S05', 'S07')):
            raise ValueError('motion_suite_native')
        epochs = row['epochs']
        if type(epochs) is not list or len(epochs) != (2 if case_id == 'S07' else 0):
            raise ValueError('motion_suite_epochs')
        for epoch, (step, position) in zip(epochs, ((100, [100, 0, 8]), (225, [12, 0, 8]))):
            c.fields(epoch, 'after_step obstacle_name position')
            c.integer(epoch['after_step'], 250)
            c.vector(epoch['position'], 3)
            if (epoch['after_step'] != step or epoch['position'] != position or
                    epoch['obstacle_name'] != 'obstacle_wall'):
                raise ValueError('motion_suite_epoch_binding')
        fault = row['fault']
        if case_id != 'S08':
            if fault is not None:
                raise ValueError('motion_suite_unexpected_fault')
        else:
            c.fields(fault, 'sensor_kind step_index')
            c.integer(fault['sensor_kind'], 2)
            c.integer(fault['step_index'], 250)
            if fault != dict(sensor_kind=1, step_index=125):
                raise ValueError('motion_suite_fault_binding')


def geometry_template(geometry_id):
    def box(name, position, size, material='FusionHot'):
        return dict(name=name, kind='box', position=position, size=size, material=material)
    templates = dict(
        legacy=dict(inherit_legacy=True, include_ground=True, objects=[]),
        north_wall=dict(inherit_legacy=False, include_ground=False,
            objects=[box('obstacle_wall', [0, 12, 8], [12, 1, 12])]),
        south_wall=dict(inherit_legacy=False, include_ground=False,
            objects=[box('obstacle_wall', [0, -12, 8], [12, 1, 12])]),
        east_wall=dict(inherit_legacy=False, include_ground=False,
            objects=[box('obstacle_wall', [12, 0, 8], [1, 12, 12])]),
        occlusion_boxes=dict(inherit_legacy=False, include_ground=False, objects=[
            box('obstacle_near', [8.5, 0, 8], [1, 6, 6]),
            box('obstacle_far', [12.5, 0, 8], [1, 2, 2], 'FusionCold')]),
        empty=dict(inherit_legacy=False, include_ground=False, objects=[]),
        moving_box=dict(inherit_legacy=False, include_ground=False,
            objects=[box('obstacle_wall', [12, 0, 8], [1, 12, 12])]))
    c.text(geometry_id)
    if geometry_id not in templates:
        raise ValueError('motion_suite_geometry_id')
    return templates[geometry_id]


def validate_geometry(geometry_id, value):
    _bounded(value)
    c.fields(value, 'inherit_legacy include_ground objects')
    objects = value['objects']
    if type(objects) is not list or len(objects) > LIMITS['boxes_per_template']:
        raise ValueError('motion_suite_boxes')
    for obj in objects:
        c.fields(obj, 'name kind position size material')
        c.vector(obj['position'], 3)
        c.vector(obj['size'], 3)
        if any(x <= 0 for x in obj['size']):
            raise ValueError('motion_suite_box_size')
    if (type(value['inherit_legacy']) is not bool or type(value['include_ground']) is not bool or
            value != geometry_template(geometry_id)):
        raise ValueError('motion_suite_geometry_binding')


def case_spec(suite, case_id):
    validate_suite(suite)
    c.text(case_id)
    for row in suite['cases']:
        if row['case_id'] == case_id:
            result = copy.deepcopy(row)
            result['geometry'] = geometry_template(row['geometry_id'])
            result['map_settings'] = None if case_id == 'S01' else dict(
                origin=[-40, -40, -8], resolution=[.5, .5, .5], shape=[160, 160, 64],
                staleness_limit_ns=500000000, max_active_cells=20000)
            return result
    raise ValueError('motion_suite_case_id')
