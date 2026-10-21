"""异步实验身份核账与分段报告；只读取本次原始审计。"""
from collections import Counter, defaultdict
import math

from perf01a_metrics import percentile_set


def state_drain_ready(source, status, run_id):
    """Never finish until the actual source clock covers every published state."""
    return (status.get('run_id') == run_id and source.get('state_count', 0) > 0
            and status.get('received') == source['state_count']
            and status.get('published') == source['state_count']
            and status.get('pending') == 0
            and int(status.get('clock_ns', -1)) >= source['last_ns'])


def diagnose_oracle_reasons(expected, decisions, infrared, max_wait_ns,
                            max_wall_wait_ns, max_delta_ns):
    """Explain dual-clock rejection mismatches without changing preregistered verdicts."""
    mismatches = []
    seen = Counter()
    for decision in decisions:
        sequence = str(decision['radar_id'].rsplit(':', 1)[-1])
        seen[sequence] += 1
        if seen[sequence] > 1:
            mismatches.append(dict(radar_id=decision['radar_id'],
                                   classification='duplicate_decision'))
            continue
        preregistered = expected.get(sequence, expected.get(int(sequence)))
        if preregistered is None:
            mismatches.append(dict(radar_id=decision['radar_id'], classification='unregistered'))
            continue
        actual_ir = (int(decision['infrared_id'].rsplit(':', 1)[-1])
                     if decision.get('infrared_id') else None)
        if (preregistered['reason'], preregistered['infrared_sequence']) == (
                decision['reason'], actual_ir):
            continue
        row = dict(radar_id=decision['radar_id'], expected=preregistered['reason'],
                   actual=decision['reason'], classification='unexplained')
        if preregistered['reason'] == 'infrared_unavailable' and decision['reason'] == 'radar_ir_timeout':
            stamp = decision['timestamp']
            clock = decision['decision_clock_ns']
            now = decision['decision_monotonic_ns']
            run_id = decision['radar_id'].rsplit(':', 2)[-2]
            candidates = [ir for ir in infrared
                          if ir.get('run_id') == run_id and ir.get('clock_id') == 'sim:' + run_id
                          and ir['sample_id'].startswith('fixture.infrared:' + run_id + ':')
                          and ir.get('disposition') == 'not_adopted'
                          and ir.get('reason') == 'wall_timeout'
                          and ir.get('terminal_ns') is not None and ir['terminal_ns'] > now
                          and ir['timestamp_ns'] <= clock and ir['received_ns'] <= now
                          and ir.get('received_clock_ns') is not None
                          and ir['received_clock_ns'] <= stamp + max_wait_ns
                          and now - ir['received_ns'] < max_wall_wait_ns
                          ]
            if candidates:
                nearest = min(candidates, key=lambda ir: (abs(ir['timestamp_ns'] - stamp),
                                                           ir['timestamp_ns'], ir['sample_id']))
                if (abs(nearest['timestamp_ns'] - stamp) > max_delta_ns
                        and nearest['timestamp_ns'] + max_wall_wait_ns <= clock):
                    row.update(classification='wall_clock_carryover',
                               candidate_id=nearest['sample_id'],
                               candidate_timestamp_ns=nearest['timestamp_ns'],
                               candidate_wall_age_ns=now - nearest['received_ns'],
                               candidate_sim_age_ns=clock - nearest['timestamp_ns'])
        mismatches.append(row)
    for sequence in sorted({str(key) for key in expected} - set(seen), key=int):
        mismatches.append(dict(radar_sequence=sequence, classification='missing_decision'))
    return dict(strict_oracle_passed=not mismatches, mismatches=mismatches)


def summarize_timing(events, decisions, producer_rows, receipts, endpoint_probe=False):
    stages = defaultdict(dict)
    errors = []
    for event in events:
        root, stage = event['parent_sample_id'], event['stage']
        if stage in stages[root]:
            errors.append('duplicate stage: ' + root + ':' + stage)
        stages[root][stage] = event
    spans, segments = defaultdict(list), defaultdict(list)
    samples = []
    generated = {r['sample_id']: r for r in producer_rows}
    received = {r['sample_id']: r for r in receipts}
    for decision in decisions:
        if decision['reason']:
            continue
        radar_id = decision['radar_id']
        root = 'sensors.bundle:' + radar_id
        row = stages[root]
        required = ('radar_receive', 'sensor_bundle_ready', 'occupancy_ready',
                    'map_snapshot_publish', 'timing.bundle_encode', 'timing.bundle_publish',
                    'timing.bundle_callback', 'timing.bundle_decode', 'timing.perception',
                    'timing.occupancy_publish', 'timing.occupancy_callback',
                    'timing.map_update', 'timing.map_publish')
        if any(key not in row for key in required):
            errors.append('missing timing stages: ' + root)
            continue
        for key, event in row.items():
            if key.startswith('timing.'):
                if event['business_timestamp'] != decision['timestamp']:
                    errors.append('timing timestamp changed: ' + root)
                spans[key[7:]].append(event['metric_value_ns'])

        def start(key):
            event = row['timing.' + key]
            return event['monotonic_ns'] - event['metric_value_ns']

        boundaries = [
            ('receive', row['radar_receive']['monotonic_ns']),
            ('pairing_wait_and_build', row['sensor_bundle_ready']['monotonic_ns']),
            ('ready_to_encode', start('bundle_encode')),
            ('bundle_encode', row['timing.bundle_encode']['monotonic_ns']),
            ('encode_to_send', start('bundle_publish')),
            ('bundle_send_to_callback', start('bundle_callback')),
            ('callback_to_decode', start('bundle_decode')),
            ('bundle_decode', row['timing.bundle_decode']['monotonic_ns']),
            ('decode_to_perception', start('perception')),
            ('perception', row['timing.perception']['monotonic_ns']),
            ('perception_to_ready', row['occupancy_ready']['monotonic_ns']),
            ('ready_to_occupancy_send', start('occupancy_publish')),
            ('occupancy_send_to_callback', start('occupancy_callback')),
            ('callback_to_map_update', start('map_update')),
            ('map_update', row['timing.map_update']['monotonic_ns']),
            ('snapshot_encode_publish', row['timing.map_publish']['monotonic_ns']),
            ('map_publish_to_event', row['map_snapshot_publish']['monotonic_ns']),
        ]
        parts = {name: end - boundaries[i - 1][1]
                 for i, (name, end) in enumerate(boundaries) if i}
        if any(value < 0 for value in parts.values()):
            errors.append('timing boundary regression: ' + root)
            continue
        for key, value in parts.items():
            segments[key].append(value)
        generation = generated.get(radar_id, {}).get('generated_monotonic_ns')
        reception = received.get(radar_id, {}).get('receive_monotonic_ns')
        sample = dict(root=root, segments_ns=parts,
                      sensor_to_occupancy_ns=row['occupancy_ready']['monotonic_ns'] - boundaries[0][1],
                      sensor_to_map_ns=boundaries[-1][1] - boundaries[0][1])
        if endpoint_probe:
            sample['endpoint_latencies_ns'] = dict(
                radar_to_occupancy_publish_call_ns=(
                    row['timing.occupancy_publish']['monotonic_ns'] - boundaries[0][1]),
                radar_to_occupancy_callback_ns=(
                    start('occupancy_callback') - boundaries[0][1]),
                radar_to_map_update_end_ns=(
                    row['timing.map_update']['monotonic_ns'] - boundaries[0][1]),
                radar_to_map_snapshot_publish_ns=(
                    row['map_snapshot_publish']['monotonic_ns'] - boundaries[0][1]))
        if generation is not None and reception is not None:
            sample['generation_to_receive_ns'] = reception - generation
            sample['generation_to_occupancy_ns'] = row['occupancy_ready']['monotonic_ns'] - generation
            if sample['generation_to_receive_ns'] < 0:
                errors.append('generation/receipt regression: ' + radar_id)
        samples.append(sample)
    result = dict(errors=sorted(set(errors)), samples=samples,
                spans_ns={k: percentile_set(v) for k, v in spans.items()},
                critical_path_ns={k: percentile_set(v) for k, v in segments.items()},
                end_to_end_ns={key: percentile_set([r[key] for r in samples if key in r])
                               for key in ('sensor_to_occupancy_ns', 'sensor_to_map_ns',
                                           'generation_to_receive_ns', 'generation_to_occupancy_ns')})
    if endpoint_probe:
        endpoint_names = ('radar_to_occupancy_publish_call_ns',
                          'radar_to_occupancy_callback_ns',
                          'radar_to_map_update_end_ns',
                          'radar_to_map_snapshot_publish_ns')
        result['endpoint_latencies_ns'] = {
            name: percentile_set([row['endpoint_latencies_ns'][name] for row in samples])
            for name in endpoint_names}
        result['endpoint_semantics'] = (
            'same-sample Radar callback to endpoint; publish call ends at the local ROS publish call, '
            'callback is downstream callback entry, map update is update call end, '
            'snapshot is map event after publish; independent percentiles are not additive')
    return result


def summarize_async_wire(audits, infrared_receipts, decisions):
    """Join real ROS serialization intervals by identity, without calling them network time."""
    errors = []

    def select(role, operation):
        selected = {}
        for row in audits[role]['rows']:
            if row['operation'] != operation:
                continue
            sample = row['sample_id']
            if sample in selected:
                errors.append('duplicate wire sample: %s:%s' % (role, sample))
            selected[sample] = row
        return selected

    ir_sent = select('infrared', 'serialize:InfraredFrame')
    ir_received = select('sensor', 'deserialize:InfraredFrame')
    ir_callback = select('sensor', 'callback:InfraredFrame')
    bundle_sent = select('sensor', 'serialize:SensorBundle')
    bundle_received = select('perception', 'deserialize:SensorBundle')
    bundle_callback = select('perception', 'callback:SensorBundle')
    infrared_ids = {row['sample_id'] for row in infrared_receipts}
    bundle_ids = {'sensors.bundle:' + d['radar_id'] for d in decisions if not d['reason']}
    def check_ids(name, expected, *groups):
        for group in groups:
            if set(group) != expected:
                errors.append(name + ': identity/count differs across wire stages')

    check_ids('infrared', infrared_ids, ir_sent, ir_received, ir_callback)
    check_ids('bundle', bundle_ids, bundle_sent, bundle_received, bundle_callback)
    receipt_by_id = {row['sample_id']: row for row in infrared_receipts}
    if len(receipt_by_id) != len(infrared_receipts):
        errors.append('infrared: duplicate receipt')

    def parts(name, ids, senders, receivers, callbacks):
        collected = defaultdict(list)
        for identity in ids & senders.keys() & receivers.keys() & callbacks.keys():
            sent, received, callback = senders[identity], receivers[identity], callbacks[identity]
            start, end = sent['start_ns'], sent['end_ns']
            receive_start, receive_end, entered = (received['start_ns'], received['end_ns'],
                                                    callback['callback_ns'])
            if (sent['wire_bytes'] != received['wire_bytes'] or
                    any(a < 0 for a in (start, end, receive_start, receive_end, entered)) or
                    not start <= end <= receive_start <= receive_end <= entered):
                errors.append(name + ': wire bytes or monotonic interval differs: ' + identity)
                continue
            for field, value in (('serialize_ns', end - start),
                                 ('serialized_to_deserialize_ns', receive_start - end),
                                 ('deserialize_ns', receive_end - receive_start),
                                 ('deserialize_to_callback_ns', entered - receive_end)):
                collected[field].append(value)
            if name == 'infrared' and identity in receipt_by_id:
                receipt = receipt_by_id[identity]
                if entered != receipt['receive_monotonic_ns']:
                    errors.append('infrared: callback/receipt boundary differs: ' + identity)
                for field in ('lock_wait_ns', 'decode_ns', 'cache_and_emit_ns'):
                    collected[field].append(receipt[field])
        return {key: percentile_set(values) for key, values in collected.items()}

    infrared = parts('infrared', infrared_ids, ir_sent, ir_received, ir_callback)
    bundle = parts('bundle', bundle_ids, bundle_sent, bundle_received, bundle_callback)
    return dict(errors=sorted(set(errors)), infrared=infrared, bundle=bundle,
                semantics='serialized-to-deserialize includes queues, copying, transport and scheduling')


def transport_accounting(schedule, producer, received, adopted_ids):
    """未采用是业务选择；只有已发布身份缺少接收证据才算意外传输损失。"""
    errors = []
    rows = producer['rows']
    expected = {row['sequence']: row for row in schedule}
    actual = {row['sequence']: row for row in rows}
    if len(actual) != len(rows) or set(actual) != set(expected):
        errors.append('generation identities differ from schedule')
    for sequence in set(actual) & set(expected):
        a, e = actual[sequence], expected[sequence]
        if any(a.get(key) != e.get(key) for key in ('timestamp_ns', 'arrival_ns', 'drop')):
            errors.append('generation schedule metadata differs')
        if bool(a['published']) == bool(e['drop']):
            errors.append('publish outcome differs from registered omission')
    published = [r['sample_id'] for r in rows if r['published']]
    reception_ids = [r['sample_id'] for r in received]
    if len(set(published)) != len(published):
        errors.append('duplicate publication')
    if len(set(reception_ids)) != len(reception_ids):
        errors.append('duplicate reception')
    unexpected_missing = sorted(set(published) - set(reception_ids))
    unexpected_received = sorted(set(reception_ids) - set(published))
    if unexpected_missing or unexpected_received:
        errors.append('transport identity mismatch')
    by_id = {r['sample_id']: r for r in rows}
    for row in received:
        source = by_id.get(row['sample_id'])
        if source is not None and row['timestamp'] != source['timestamp_ns']:
            errors.append('sampling timestamp changed in transport')
    adopted = set(adopted_ids)
    if adopted - set(reception_ids):
        errors.append('adopted input has no receipt')
    return dict(generated=len(rows), published=len(published), received=len(reception_ids),
                adopted_unique=len(adopted), adoption_references=len(adopted_ids),
                not_adopted=len(set(reception_ids) - adopted),
                injected_missing=sum(bool(r['drop']) for r in schedule),
                unexpected_lost=len(unexpected_missing), unexpected_lost_ids=unexpected_missing,
                unexpected_received_ids=unexpected_received, errors=sorted(set(errors)))


def _map_index(point, transform, resolution=(0.5, 0.5, 0.5), origin=(-16.0, -8.0, -4.0)):
    if len(point) != 3 or len(transform) != 16:
        raise ValueError('dynamic map oracle requires point and 4x4 transform')
    homogeneous = [point[0], point[1], point[2], 1.0]
    coordinates = [sum(transform[4 * axis + col] * homogeneous[col] for col in range(4))
                   for axis in range(3)]
    return tuple(int(math.floor((coordinates[axis] - origin[axis]) / resolution[axis]))
                 for axis in range(3))


def _validate_dynamic_cells(records, accepted, errors):
    """Use received Bundle geometry as an independent continuous-to-grid oracle."""
    expected = {}
    bundle_by_timestamp = {row['timestamp']: row for row in records['bundle']}
    for decision in accepted:
        stamp = decision['timestamp']
        row = bundle_by_timestamp.get(stamp)
        if row is None or 'radar_points' not in row or 'radar_to_odom' not in row:
            errors.append('map: dynamic oracle inputs missing from bundle receipt')
            continue
        if len(row['radar_points']) != 1:
            errors.append('map: dynamic oracle expects one Radar point per Bundle')
            continue
        try:
            index = _map_index(row['radar_points'][0], row['radar_to_odom'])
        except (TypeError, ValueError, IndexError):
            errors.append('map: dynamic oracle input geometry invalid')
            continue
        expected[index] = stamp
        actual = {tuple(cell['index']): cell for cell in next(
            (item for item in records['map'] if item['timestamp'] == stamp), {'cells': []})['cells']}
        if set(actual) != set(expected):
            errors.append('map: dynamic occupied cell set changed')
            continue
        for index, observed_timestamp in expected.items():
            cell = actual[index]
            if (not cell['observed'] or abs(cell['probability'] - .9) > 1e-6 or
                    cell['timestamp'] != observed_timestamp):
                errors.append('map: dynamic occupied cell semantics changed')
    return errors


def validate_maps(records, decisions, run_id, expected_cells=None, motion=False, map_oracle=None):
    errors = []
    accepted = [d for d in decisions if not d['reason']]
    stamps = [d['timestamp'] for d in accepted]
    roots = ['sensors.bundle:' + d['radar_id'] for d in accepted]
    for key, prefix in (('bundle', ''), ('occupancy', 'perception.occupancy:')):
        if [r['sample_id'] for r in records[key]] != [prefix + r for r in roots]:
            errors.append(key + ': identity/order mismatch')
    for key in ('bundle', 'occupancy', 'map'):
        if [r['timestamp'] for r in records[key]] != stamps:
            errors.append(key + ': reference timestamps differ')
        if any(r['run_id'] != run_id or r['clock_id'] != 'sim:' + run_id or r['status'] != 0
               for r in records[key]):
            errors.append(key + ': invalid run/clock/status')
    for row, decision in zip(records['bundle'], accepted):
        if (row['radar_id'] != decision['radar_id'] or
                row['infrared_id'] != decision['infrared_id'] or
                not 0 <= row['radar_ir_delta_ns'] <= 5_000_000 or
                not 0 <= row['pose_age_ns'] <= 10_000_000 or
                row['radar_timestamp'] != row['timestamp'] or
                abs(row['infrared_timestamp'] - row['radar_timestamp']) != row['radar_ir_delta_ns'] or
                row['radar_timestamp'] - row['state_timestamp'] != row['pose_age_ns']):
            errors.append('bundle: chosen input or time gate mismatch')
    if [r['revision'] for r in records['map']] != list(range(1, len(stamps) + 1)):
        errors.append('map revisions differ')
    if map_oracle == 'radar_points':
        _validate_dynamic_cells(records, accepted, errors)
        return sorted(set(errors))
    expected_cells = expected_cells or {}
    for row in records['map']:
        cells = row['cells']
        expected_index = expected_cells.get(row['timestamp'], [32, 24, 8])
        if not motion and (len(cells) != 1 or cells[0]['index'] != list(expected_index) or
                not cells[0]['observed'] or cells[0]['timestamp'] != row['timestamp'] or
                abs(cells[0]['probability'] - .9) > 1e-6):
            errors.append('map: occupied/unknown semantics changed')
    return sorted(set(errors))


def validate_motion(records, decisions, profile, aging):
    """Oracle uses fixed world geometry and the selected state's *timestamp*.

    Raw Radar coordinates, carried pose, transformed point, sparse map revisions
    and clock-domain aging are checked separately; no production fixture helper
    or map implementation is called here.
    """
    errors = []
    speed = profile['speed_mps']
    obstacles = profile['obstacles_odom']
    accepted = [d for d in decisions if not d['reason']]
    expected_cells = {}
    measured_errors = []
    boundary_sensitive = 0
    for row in records['bundle']:
        stamp, state_stamp = row['timestamp'], row['state_timestamp']
        age = (stamp - state_stamp) / 1e9
        position = row['state_position']
        velocity = row['state_velocity']
        transform = row['radar_to_odom']
        if len(transform) != 16:
            errors.append('motion: state position or radar-to-odom transform differs')
            continue
        if (abs(position[0]) > 1e-5 or abs(position[1] - speed * state_stamp / 1e9) > 1e-5
                or abs(position[2]) > 1e-5 or any(abs(value - expected) > 1e-5
                for value, expected in zip(velocity, (speed, 0., 0.)))
                or any(abs(a - b) > 1e-5 for a, b in zip(
                    (transform[0], transform[1], transform[4], transform[5],
                     transform[3], transform[7], transform[11]),
                    (0., -1., 1., 0., 0., position[1], 0.)))):
            errors.append('motion: state position or radar-to-odom transform differs')
        if len(row['radar_points']) != len(obstacles):
            errors.append('motion: radar point count differs from world scene')
            continue
        indices = []
        for point, (east, north, up) in zip(row['radar_points'], obstacles):
            expected_relative = (north - speed * stamp / 1e9, -east, up)
            if any(abs(value - expected) > 1e-4 for value, expected in zip(point, expected_relative)):
                errors.append('motion: radar point differs from sampling-time world scene')
            actual = tuple(sum(transform[4 * axis + col] * (point[col] if col < 3 else 1.)
                               for col in range(4)) for axis in range(3))
            target = (east, north - speed * age, up)
            error = math.dist(actual, (east, north, up))
            measured_errors.append(error)
            if any(abs(value - expected) > 1e-4 for value, expected in zip(actual, target)):
                errors.append('motion: carried historical transform differs from expected world point')
            if error > speed * row['pose_age_ns'] / 1e9 + 1e-4:
                errors.append('motion: historical pose error exceeds measured age budget')
            # Occupancy quantizes the carried transform, not the ideal world point.
            # Check the world error separately; do not snap a near-boundary voxel.
            index = tuple(math.floor((actual[axis] - (-16., -8., -4.)[axis]) / .5)
                          for axis in range(3))
            if any(abs((target[axis] - (-16., -8., -4.)[axis]) / .5 -
                       round((target[axis] - (-16., -8., -4.)[axis]) / .5)) < 2e-4
                   for axis in range(3)):
                boundary_sensitive += 1
            indices.append(index)
        expected_cells[stamp] = indices
    for row in records['occupancy']:
        if sorted(tuple(index) for index in row['voxels']) != sorted(expected_cells.get(row['timestamp'], [])):
            errors.append('motion: occupancy quantization differs from carried transform')
    latest = {}
    for row in records['map']:
        for index in expected_cells.get(row['timestamp'], []):
            latest[index] = row['timestamp']
        actual = {tuple(cell['index']): cell for cell in row['cells']}
        if (set(actual) != set(latest) or any(
                actual[index]['timestamp'] != timestamp or not actual[index]['observed']
                or abs(actual[index]['probability'] - .9) > 1e-6
                for index, timestamp in latest.items() if index in actual)):
            errors.append('motion: map cells/unknown or observation timestamps differ')
    if len(accepted) != len(records['bundle']) or len(records['map']) != len(accepted):
        errors.append('motion: accepted/map receipt count differs')
    rows = aging.get('rows', [])
    if not rows:
        errors.append('motion: no map clock-aging audit')
    stale_seen = fresh_after_stale = stale_during_fault = fresh_after_recovery = False
    fault_start = profile.get('fault_start_ns', 0)
    fault_stop = profile.get('fault_stop_ns', 0)
    recovery_start = profile.get('recovery_start_ns', 0)
    for row in rows:
        cells = {tuple(c['index']): c['timestamp'] for c in row['cells']}
        stale = {index for index, timestamp in cells.items()
                 if row['query_timestamp'] - timestamp > aging['staleness_limit_ns']}
        if {tuple(index) for index in row['stale']} != stale:
            errors.append('motion: map clock-aging result differs from last observation')
        if stale:
            stale_seen = True
            if fault_start <= row['query_timestamp'] < fault_stop:
                stale_during_fault = True
        elif stale_seen and cells:
            fresh_after_stale = True
            if row['query_timestamp'] >= recovery_start and any(
                    timestamp >= recovery_start for timestamp in cells.values()):
                fresh_after_recovery = True
    return dict(errors=sorted(set(errors)), max_world_error_m=max(measured_errors, default=None),
                boundary_sensitive_points=boundary_sensitive,
                stale_seen=stale_seen, fresh_after_stale=fresh_after_stale,
                stale_during_fault=stale_during_fault, fresh_after_recovery=fresh_after_recovery,
                verified_maps=len(records['map']), clock_age_queries=len(rows))
