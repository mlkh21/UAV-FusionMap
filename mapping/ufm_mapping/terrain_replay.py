"""Bounded private M5 fixture event replay; no occupancy replay or ROS transport."""
from .m5_contract import LIMITS
from .terrain_fixture import TerrainFixture


def replay_terrain(spec, events):
    if not isinstance(events,list) or len(events) > LIMITS['max_receipt_events']:
        raise ValueError('M5 replay requires a list within the frozen event limit')
    registration = spec['registration']
    layer = TerrainFixture(spec,registration['run_id'],registration['clock_id'])
    receipts = []
    for sequence,event in enumerate(events):
        if not isinstance(event,dict) or type(event.get('sequence')) is not int or event['sequence'] != sequence:
            raise ValueError('M5 replay sequence is not contiguous')
        operation = event['operation']
        if operation not in ('install','install_identical','install_conflicting','install_bad_tile',
                             'query','clock_reset','disable'):
            raise ValueError('M5 replay operation unsupported: ' + str(operation))
        timestamp = event['timestamp_ns']
        if operation in ('query','clock_reset') and event['request']['query_timestamp'] != timestamp:
            raise ValueError('M5 replay event/query times disagree')
        layer.observe_clock(timestamp)
        row = dict(sequence=sequence,operation=operation,timestamp_ns=event['timestamp_ns'])
        if operation.startswith('install'):
            before = layer.snapshot()
            try:
                changed = layer.install(event['input'],event['timestamp_ns'])
                row.update(outcome='installed' if changed else 'idempotent',reason='')
            except ValueError as exc:
                row.update(outcome='rejected',reason=str(exc))
                if layer.snapshot() != before:
                    raise RuntimeError('M5 refused install mutated committed state') from exc
        elif operation == 'disable':
            layer.disable()
            row.update(outcome='disabled',reason='')
        else:
            row['result'] = layer.query(event['request'])
            row['outcome'] = row['result']['status']
        row['terrain_revision'] = layer.snapshot()['terrain_revision']
        receipts.append(row)
    return dict(receipts=receipts,final_snapshot=layer.snapshot())
