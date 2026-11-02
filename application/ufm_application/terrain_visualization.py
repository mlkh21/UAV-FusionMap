"""Pure public terrain group to marker rows; missing heights never become z=0."""
import copy
from ufm_terrain_contract.bounds import MESSAGE_BYTES, RECORDING_BYTES, bounded_json, fields, integer, text
from ufm_terrain_contract.contract import validate_result, validate_status
COLORS = {
    'valid': (0.18, 0.68, 0.48, 0.85),
    'stale': (0.88, 0.58, 0.14, 0.68),
}


def marker_rows(group):
    if not group or group.get('mode') not in ('live', 'recorded'):
        return []
    context = group['context']
    rows = []
    for result in group['results']:
        if result['status'] not in COLORS or result['height'] is None:
            continue
        color = COLORS[result['status']]
        if result['status'] == 'valid' and result['height_quality']['status'] == 'unavailable':
            color = (0.22, 0.56, 0.88, 0.85)
        rows.append(dict(status=result['status'], point=[result['point_xy'][0], result['point_xy'][1], result['height']],
                         source_index=list(result['source_index']), source_xy=list(result['source_xy']),
                         color=color, mode=group['mode'], provider_instance_id=group['provider_instance_id'],
                         terrain_revision=group['terrain_revision'], frame_id=context['target_frame']))
    return rows


def recorded_groups(receipt):
    """Read only public replay outputs, never dataset or private fixture files."""
    fields(receipt,'mode playback_session_id provider_instance_id results statuses event_count passed')
    bounded_json(receipt,RECORDING_BYTES)
    if receipt['mode']!='recorded' or receipt['passed'] is not True:
        raise ValueError('terrain_recorded_receipt')
    text(receipt['playback_session_id']);text(receipt['provider_instance_id'])
    integer(receipt['event_count'],64)
    if receipt['event_count']>64 or type(receipt['results']) is not list or len(receipt['results'])>64:
        raise ValueError('terrain_recorded_result_limit')
    if type(receipt['statuses']) is not list or len(receipt['statuses'])>64:
        raise ValueError('terrain_recorded_status_limit')
    for status in receipt['statuses']:
        validate_status(status)
        if status['provider_instance_id']!=receipt['provider_instance_id']:
            raise ValueError('terrain_recorded_status_instance')
    groups=[]
    current=None
    for result in receipt['results']:
        validate_result(result,provider_instance_id=receipt['provider_instance_id'])
        if result['context'] is None:
            current=None
            continue
        key=(result['terrain_revision'],result['query_timestamp'],result['evaluation_timestamp'],result['context'])
        if current is None or current[0]!=key:
            group=dict(mode='recorded',provider_instance_id=receipt['provider_instance_id'],
                playback_session_id=receipt['playback_session_id'],terrain_revision=result['terrain_revision'],
                context=copy.deepcopy(result['context']),results=[])
            groups.append(group)
            current=(key,group)
        rows=current[1]['results']
        # A repeated center is another receipt, not another geometry sample.
        rows[:]=[r for r in rows if r['point_xy']!=result['point_xy']]
        rows.append(copy.deepcopy(result))
        if len(rows)>16:raise ValueError('terrain_recorded_group_limit')
    return groups
