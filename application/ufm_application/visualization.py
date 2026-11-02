"""Read-only views of public snapshots; missing space never becomes free."""
import copy
import math


STATES = ('occupied', 'free', 'unknown', 'stale', 'unavailable')
COLORS = {'occupied': (.89, .26, .31, 1.), 'free': (.12, .64, .55, .65),
          'unknown': (.94, .69, .21, .9), 'stale': (.56, .54, .69, .65),
          'unavailable': (.50, .55, .58, .3)}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_snapshot(snapshot, cell_limit=20000):
    header = snapshot['header']
    for key in ('run_id', 'clock_id', 'frame_id', 'source_type'):
        if not isinstance(header[key], str) or not header[key]:
            raise ValueError('snapshot requires ' + key)
    if header['status'] not in ('valid', 'degraded', 'unavailable'):
        raise ValueError('invalid snapshot status')
    if type(header['timestamp']) is not int or header['timestamp'] < 0:
        raise ValueError('invalid snapshot timestamp')
    if not isinstance(snapshot['map_id'], str) or not snapshot['map_id']:
        raise ValueError('snapshot map_id required')
    if type(snapshot['revision']) is not int or snapshot['revision'] < 0:
        raise ValueError('invalid revision')
    for field in ('resolution', 'shape', 'origin'):
        if len(snapshot[field]) != 3 or any(not finite(v) for v in snapshot[field]):
            raise ValueError('invalid grid ' + field)
    if any(v <= 0 for v in snapshot['resolution']) or any(
            type(v) is not int or v <= 0 for v in snapshot['shape']):
        raise ValueError('grid resolution and shape must be positive')
    if len(snapshot['coverage']) != 6 or any(not finite(v) for v in snapshot['coverage']):
        raise ValueError('invalid coverage')
    for axis in range(3):
        low, high = snapshot['coverage'][2 * axis:2 * axis + 2]
        if not (math.isclose(low, snapshot['origin'][axis], rel_tol=0., abs_tol=1e-8) and
                math.isclose(high, low + snapshot['resolution'][axis] * snapshot['shape'][axis], rel_tol=0., abs_tol=1e-8)):
            raise ValueError('coverage differs from grid')
    if not isinstance(snapshot['source_types'], list) or not snapshot['source_types'] or any(
            not isinstance(v, str) or not v for v in snapshot['source_types']):
        raise ValueError('source types required')
    if len(snapshot['cells']) > cell_limit:
        raise ValueError('snapshot exceeds visualization cell limit')
    seen = set()
    for cell in snapshot['cells']:
        index = cell['index']
        if len(index) != 3 or any(type(v) is not int or not 0 <= v < snapshot['shape'][a]
                                  for a, v in enumerate(index)) or tuple(index) in seen:
            raise ValueError('invalid or duplicate cell index')
        seen.add(tuple(index))
        if not finite(cell['probability']) or not 0 <= cell['probability'] <= 1:
            raise ValueError('invalid occupancy probability')
        if type(cell['observed']) is not bool:
            raise ValueError('observed must be boolean')
        if type(cell['last_observed_timestamp']) is not int or not (
                0 <= cell['last_observed_timestamp'] <= header['timestamp']):
            raise ValueError('invalid evidence timestamp')
        confidence = cell['confidence']
        if confidence is not None and (not finite(confidence) or not 0 <= confidence <= 1):
            raise ValueError('invalid confidence')
        quality = cell['uncertainty']
        if quality is not None:
            if quality['status'] not in ('available', 'unavailable'):
                raise ValueError('invalid uncertainty status')
            available = quality['status'] == 'available'
            if any(not isinstance(quality[k], str) or available and not quality[k].strip()
                   for k in ('kind', 'unit', 'source')):
                raise ValueError('invalid uncertainty metadata')
            values = quality['value']
            if available and (not isinstance(values, list) or not values or any(not finite(v) for v in values)):
                raise ValueError('invalid uncertainty payload')
            if not available and values is not None:
                raise ValueError('unavailable uncertainty must retain None')
    return snapshot


class SnapshotView:
    def __init__(self, ttl_ns, free_threshold=None, occupied_threshold=None):
        if type(ttl_ns) is not int or ttl_ns < 0:
            raise ValueError('explicit nonnegative TTL required')
        if (free_threshold is None) != (occupied_threshold is None):
            raise ValueError('both display thresholds required')
        if free_threshold is not None and not (finite(free_threshold) and finite(occupied_threshold)
                and 0 <= free_threshold < occupied_threshold <= 1):
            raise ValueError('invalid display thresholds')
        self.ttl_ns = ttl_ns
        self.free_threshold, self.occupied_threshold = free_threshold, occupied_threshold

    def frame(self, snapshot, timestamp, clock_id, transport_ok=True):
        validate_snapshot(snapshot)
        header = snapshot['header']
        available = (transport_ok and header['status'] == 'valid' and
                     type(timestamp) is int and timestamp >= header['timestamp'] and
                     clock_id == header['clock_id'])
        cells = []
        counts = dict.fromkeys(STATES, 0)
        for cell in snapshot['cells']:
            if not available:
                status = 'unavailable'
            elif not cell['observed']:
                status = 'unknown'
            elif timestamp - cell['last_observed_timestamp'] > self.ttl_ns:
                status = 'stale'
            elif self.free_threshold is None:
                status = 'unknown'
            elif cell['probability'] <= self.free_threshold:
                status = 'free'
            elif cell['probability'] >= self.occupied_threshold:
                status = 'occupied'
            else:
                status = 'unknown'
            counts[status] += 1
            cells.append(dict(index=list(cell['index']), state=status,
                center=[snapshot['origin'][a] + (cell['index'][a] + .5) * snapshot['resolution'][a]
                        for a in range(3)], probability=cell['probability']))
        return dict(map_id=snapshot['map_id'], revision=snapshot['revision'],
                    header=copy.deepcopy(header), timestamp=timestamp, available=available,
                    cells=cells, counts=counts, resolution=list(snapshot['resolution']),
                    coverage=list(snapshot['coverage']), sources=list(snapshot['source_types']),
                    unlisted_space='unknown', display_policy=dict(ttl_ns=self.ttl_ns,
                        free_threshold=self.free_threshold, occupied_threshold=self.occupied_threshold))


def load_recording(value):
    """Read public snapshots only; never load a map's private state."""
    snapshots = value.get('snapshots', [])
    if not isinstance(snapshots, list) or not 0 < len(snapshots) <= 120:
        raise ValueError('recording must contain 1..120 public snapshots')
    identity = None
    last_revision = -1
    last_timestamp = -1
    for snapshot in snapshots:
        validate_snapshot(snapshot)
        header = snapshot['header']
        current = (header['run_id'], header['clock_id'], header['frame_id'], snapshot['map_id'])
        if identity is not None and current != identity:
            raise ValueError('recording mixes map/run/clock/frame')
        if snapshot['revision'] <= last_revision:
            raise ValueError('recording revisions must increase')
        if header['timestamp'] < last_timestamp:
            raise ValueError('recording evidence timestamps cannot decrease')
        last_timestamp = header['timestamp']
        identity, last_revision = current, snapshot['revision']
    return copy.deepcopy(snapshots)
