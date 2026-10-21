"""同机单调时钟分段核算；区间分位数不相加，保留逐样本分解。"""
from collections import defaultdict
import math

from perf01a_metrics import percentile_set
from perf01a_validation import expected_sequences


SENSOR = ('fixture_generation', 'pairing', 'radar_encode', 'radar_publish')
INFRARED = ('infrared_generation', 'infrared_encode', 'infrared_publish')
ACCEPTED = ('bundle_encode', 'bundle_publish', 'bundle_callback', 'bundle_decode',
            'perception', 'occupancy_encode', 'occupancy_publish', 'occupancy_callback',
            'occupancy_decode', 'map_update', 'map_snapshot', 'map_encode', 'map_publish')


def expected_timing(count, profile, run_id):
    sequences = expected_sequences(count, profile)
    infrared, accepted = set(sequences['infrared']), set(sequences['bundle'])
    return {'sensors.bundle:fixture.radar:%s:%d' % (run_id, i):
            set(SENSOR + (INFRARED if i in infrared else ()) +
                (ACCEPTED if i in accepted else ())) for i in range(count)}


def timing_report(events, expected, period_ns):
    rows = defaultdict(dict)
    errors, samples = [], []
    durations, segments = defaultdict(list), defaultdict(list)
    for event in events:
        root, stage = event['parent_sample_id'], event['stage']
        if stage in rows[root]:
            errors.append('duplicate sample stage: ' + stage)
        rows[root][stage] = event
    if set(rows) != set(expected):
        errors.append('timing root identities differ')
    for root, required in expected.items():
        stages = rows[root]
        actual = {s[7:] for s in stages if s.startswith('timing.')}
        if actual != required:
            errors.append('timing stages differ: ' + root)
            continue
        spans = {s: (stages['timing.' + s]['monotonic_ns'] -
                     stages['timing.' + s]['metric_value_ns'],
                     stages['timing.' + s]['monotonic_ns']) for s in required}
        stamp = int(root.rsplit(':', 1)[1]) * period_ns
        for name, (start, end) in spans.items():
            event = stages['timing.' + name]
            if start < 0 or end < start or event['business_timestamp'] != stamp or event['status'] != 'valid':
                errors.append('invalid timing span: ' + name)
            durations[name].append(end - start)
        if not set(ACCEPTED) <= required:
            continue
        if not all(s in stages for s in ('radar_receive', 'occupancy_ready', 'map_snapshot_publish')):
            errors.append('timing base stage missing: ' + root)
            continue
        # 每行分界点构成连续、互不重叠的关键路径；publish调用耗时单列，不能再加到传输段。
        boundaries = [
            ('origin', stages['radar_receive']['monotonic_ns']),
            ('generation_setup', spans['fixture_generation'][0]),
            ('fixture_generation', spans['fixture_generation'][1]),
            ('generation_to_pairing', spans['pairing'][0]),
            ('pairing', spans['pairing'][1]),
            ('pairing_to_bundle_encode', spans['bundle_encode'][0]),
            ('bundle_encode', spans['bundle_encode'][1]),
            ('encode_to_bundle_send', spans['bundle_publish'][0]),
            ('bundle_send_to_callback', spans['bundle_callback'][0]),
            ('callback_to_bundle_decode', spans['bundle_decode'][0]),
            ('bundle_decode', spans['bundle_decode'][1]),
            ('decode_to_perception', spans['perception'][0]),
            ('perception', spans['perception'][1]),
            ('perception_to_ready', stages['occupancy_ready']['monotonic_ns']),
            ('ready_to_occupancy_send', spans['occupancy_publish'][0]),
            ('occupancy_send_to_callback', spans['occupancy_callback'][0]),
            ('callback_to_map_update', spans['map_update'][0]),
            ('map_update', spans['map_update'][1]),
            ('snapshot_encode_publish', spans['map_publish'][1]),
            ('map_publish_to_event', stages['map_snapshot_publish']['monotonic_ns']),
        ]
        parts = {name: end - boundaries[i - 1][1]
                 for i, (name, end) in enumerate(boundaries) if i}
        if any(value < 0 for value in parts.values()):
            errors.append('timing boundary regression: ' + root)
            continue
        for name, value in parts.items():
            segments[name].append(value)
        samples.append(dict(root=root, segments_ns=parts,
            sensor_to_occupancy_ns=stages['occupancy_ready']['monotonic_ns'] - boundaries[0][1],
            sensor_to_map_ns=boundaries[-1][1] - boundaries[0][1]))
    ordered = sorted(samples, key=lambda r: r['sensor_to_occupancy_ns'])
    return dict(errors=list(dict.fromkeys(errors)), samples=samples,
                spans_ns={k: percentile_set(v) for k, v in durations.items()},
                critical_path_ns={k: percentile_set(v) for k, v in segments.items()},
                occupancy_p99_sample=(ordered[math.ceil(.99 * len(ordered)) - 1] if ordered else None))
