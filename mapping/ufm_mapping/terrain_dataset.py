"""Public dataset schema and lossless adapter to the private M5 input checker."""
import copy

from ufm_terrain_contract.bounds import REQUEST_BYTES, bounded_json, fields, read_json
from ufm_terrain_contract.contract import validate_context
from .m5_contract import validate_spec

DATASET_FIELDS = ('schema_version profile identity source_time horizontal vertical grid map_grid '
                  'registration eligibility limits')


def validate_dataset(value):
    fields(value, DATASET_FIELDS)
    bounded_json(value, REQUEST_BYTES)
    if value['schema_version'] != 'ufm.terrain.dataset.v1' or value['profile'] != 'm5_fixture_v1':
        raise ValueError('terrain_dataset_schema_or_profile')
    validate_spec(_private(value))


def _private(value):
    result = {k: copy.deepcopy(v) for k, v in value.items() if k not in ('schema_version', 'profile')}
    result.update(schema_version='m5_terrain_fixture.v1', fixture_only=True, enabled_by_default=False)
    return result


def to_private_fixture(value):
    """Only after strict public validation; never drop unknown fields to accept input."""
    validate_dataset(value)
    return _private(value)


def from_private_fixture(value):
    validate_spec(value)
    result = {k: copy.deepcopy(v) for k, v in value.items()
              if k not in ('schema_version', 'fixture_only', 'enabled_by_default')}
    result.update(schema_version='ufm.terrain.dataset.v1', profile='m5_fixture_v1')
    validate_dataset(result)
    return result


def load_dataset(path):
    value = read_json(path, REQUEST_BYTES)
    validate_dataset(value)
    return value


def dataset_context(value, installed_timestamp):
    """Project public dataset metadata only; does not install, query or create a provider."""
    validate_dataset(value)
    identity, source = value['identity'], value['source_time']
    horizontal, vertical = value['horizontal'], value['vertical']
    grid, target = value['grid'], value['map_grid']
    registration, eligibility = value['registration'], value['eligibility']
    context = dict(identity, profile=value['profile'], evidence_role='prior',
        run_id=registration['run_id'], clock_id=registration['clock_id'],
        acquisition_ns=source['acquisition_ns'], publication_ns=source['publication_ns'],
        precision_ns=source['precision_ns'], source_clock_id=source['clock_id'], dataset_epoch=source['dataset_epoch'],
        source_horizontal_crs_id=horizontal['crs_id'], source_frame=horizontal['frame_id'],
        source_axis_order=horizontal['axis_order'], source_vertical_datum_id=vertical['datum_id'],
        source_height_type=vertical['height_type'], vertical_operation=vertical['operation'],
        required_grids=vertical['required_grids'], target_horizontal_crs_id=target['crs_id'],
        target_vertical_datum_id=target['vertical_datum_id'], target_frame=target['frame_id'], length_unit=target['unit'],
        rows=grid['rows'], columns=grid['columns'], affine=grid['affine'], sample_anchor=grid['sample_anchor'],
        map_origin_xy=target['origin_xy'], map_resolution_xy=target['resolution_xy'],
        registration_id=registration['registration_id'], registration_source=registration['source'],
        horizontal_alignment=registration['horizontal_alignment'], T_map_terrain=registration['T_map_terrain'],
        registration_valid_interval_ns=registration['valid_interval_ns'], registration_quality=registration['height_quality'],
        eligibility_policy=eligibility['policy'], eligibility_valid_interval_ns=eligibility['valid_interval_ns'],
        installed_timestamp=installed_timestamp)
    validate_context(context)
    return copy.deepcopy(context)
