"""Independent saved protocol examples; no production contract/codec imports."""
import copy
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]


def expected():
    return json.loads((ROOT / 'tests/fixtures/m5_iface_expectations.json').read_text())


def quality(bounds=None, kind='height_interval', source='fixture_height_bound_v1'):
    return dict(status='unavailable' if bounds is None else 'available', kind='' if bounds is None else kind,
                value=bounds, unit='' if bounds is None else 'm', source=source)


def request():
    return dict(terrain_id='m5-terrain-fixture', run_id='m5-fixture', clock_id='sim:m5-fixture', frame_id='map',
                query_timestamp=100, point_xy=[111., 179.], pin_version=True,
                expected_provider_instance_id='terrain-instance-a', expected_terrain_revision=1)


def result(index=0):
    row = expected()['samples'][index]
    return dict(protocol_version=1, provider_instance_id='terrain-instance-a',
        terrain_id='m5-terrain-fixture', run_id='m5-fixture', clock_id='sim:m5-fixture', frame_id='map',
        query_timestamp=100, point_xy=row['point_xy'], evaluation_timestamp=100, terrain_revision=1,
        status=row['status'], reason=row['reason'], context=expected()['context'], height=row['height'],
        source_index=row['source_index'], source_xy=row['source_xy'], height_quality=quality(row['map_interval']),
        sample_quality=quality(row['sample_interval']))


def unavailable():
    row = result()
    row.update(status='unavailable', reason='clock_unavailable', context=None, height=None,
               source_index=None, source_xy=None, height_quality=quality(), sample_quality=quality(),
               evaluation_timestamp=None)
    return row


def status():
    return dict(protocol_version=1, provider_instance_id='terrain-instance-a', terrain_id='m5-terrain-fixture',
        run_id='m5-fixture', clock_id='sim:m5-fixture', frame_id='map', status_sequence=1, terrain_revision=1,
        evaluation_timestamp=100, state='current', reason='', context=expected()['context'], last_attempt_id=1,
        last_install_outcome='installed', last_install_reason='')


# Explicit independent ROS field order/types from the approved design.
LAYOUT = {
 'TerrainHeightQuality': 'status:uint8 kind:string value:float64[2] unit:string source:string',
 'TerrainContext': ('terrain_id:string dataset_version:string tile_id:string profile:string product_kind:string '
    'source_kind:string evidence_role:string source_ref:string run_id:string clock_id:string acquisition_ns:int64 '
    'publication_ns:int64 precision_ns:int64 source_clock_id:string dataset_epoch:string source_horizontal_crs_id:string '
    'source_frame:string source_axis_order:string[2] source_vertical_datum_id:string source_height_type:string '
    'vertical_operation:string required_grids:string[] target_horizontal_crs_id:string target_vertical_datum_id:string '
    'target_frame:string length_unit:string rows:uint32 columns:uint32 affine:float64[6] sample_anchor:string '
    'map_origin_xy:float64[2] map_resolution_xy:float64[2] registration_id:string registration_source:string '
    'horizontal_alignment:string T_map_terrain:float64[16] registration_valid_interval_ns:int64[2] '
    'registration_quality:TerrainHeightQuality eligibility_policy:string eligibility_valid_interval_ns:int64[2] installed_timestamp:int64'),
 'TerrainQueryRequest': ('terrain_id:string run_id:string clock_id:string frame_id:string query_timestamp:int64 '
    'point_xy:float64[2] pin_version:bool expected_provider_instance_id:string expected_terrain_revision:uint64'),
 'TerrainQueryResult': ('protocol_version:uint16 provider_instance_id:string terrain_id:string run_id:string clock_id:string '
    'frame_id:string query_timestamp:int64 point_xy:float64[2] evaluation_timestamp_available:bool evaluation_timestamp:int64 '
    'terrain_revision:uint64 status:uint8 reason:string context_available:bool context:TerrainContext height_available:bool '
    'height:float64 source_index_available:bool source_index:uint32[2] source_xy_available:bool source_xy:float64[2] '
    'height_quality:TerrainHeightQuality sample_quality:TerrainHeightQuality'),
 'TerrainStatus': ('protocol_version:uint16 provider_instance_id:string terrain_id:string run_id:string clock_id:string '
    'frame_id:string status_sequence:uint64 terrain_revision:uint64 evaluation_timestamp_available:bool evaluation_timestamp:int64 '
    'state:uint8 reason:string context_available:bool context:TerrainContext last_attempt_id:uint64 '
    'last_install_outcome:uint8 last_install_reason:string'),
 'TerrainQueryResponse': 'result:TerrainQueryResult',
}


def zero(kind):
    if '[' in kind:
        base, count = kind[:-1].split('[')
        return [zero(base) for _ in range(int(count or 0))]
    if kind in LAYOUT:
        return {f: zero(t) for f, t in (x.split(':') for x in LAYOUT[kind].split())}
    return '' if kind == 'string' else False if kind == 'bool' else 0


def wire_object(name, value):
    row = copy.deepcopy(value)
    for field, kind in (x.split(':') for x in LAYOUT[name].split()):
        if field.endswith('_available'):
            row[field] = value[field[:-10]] is not None
        elif row[field] is None:
            row[field] = zero(kind)
        elif kind in LAYOUT:
            row[field] = wire_object(kind, row[field])
    saved = expected()
    enum = {'TerrainHeightQuality': ('status', 'quality_status'), 'TerrainQueryResult': ('status', 'query_status'),
            'TerrainStatus': ('state', 'state')}.get(name)
    if enum:
        row[enum[0]] = saved[enum[1]][value[enum[0]]]
    if name == 'TerrainStatus':
        row['last_install_outcome'] = saved['install_outcome'][value['last_install_outcome']]
    return row


def independent_bytes(name, row):
    def pack(kind, value):
        if '[' in kind:
            base, count = kind[:-1].split('[')
            return (b'' if count else struct.pack('<I', len(value))) + b''.join(pack(base, x) for x in value)
        if kind in LAYOUT:
            return independent_bytes(kind, value)
        if kind == 'string':
            encoded = value.encode('utf-8')
            return struct.pack('<I', len(encoded)) + encoded
        return struct.pack('<' + dict(bool='?', uint8='B', uint16='H', uint32='I', uint64='Q', int64='q', float64='d')[kind], value)
    return b''.join(pack(t, row[f]) for f, t in (x.split(':') for x in LAYOUT[name].split()))
