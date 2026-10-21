"""只读核对生产/消费审计，并分解bundle实际线格式区间。"""
from collections import defaultdict

from perf01a_metrics import percentile_set
from perf01a_validation import expected_sequences, validate_receipts


def wire_report(audits, events, records, count, profile, run_id, period_ns, observer_mode):
    errors, selected = [], {}
    expected = expected_sequences(count, profile)
    metadata = observer_mode == 'metadata'
    plans = [('sensor', 'publish:InfraredFrame', 'infrared', True),
             ('sensor', 'publish:SensorBundle', 'bundle', True),
             ('sensor', 'serialize:InfraredFrame', 'infrared', not metadata),
             ('sensor', 'serialize:SensorBundle', 'bundle', True),
             ('perception', 'deserialize:SensorBundle', 'bundle', True),
             ('perception', 'callback:SensorBundle', 'bundle', True),
             ('observer', 'deserialize:InfraredFrame', 'infrared', not metadata),
             ('observer', 'deserialize:SensorBundle', 'bundle', not metadata)]
    for role, operation, key, present in plans:
        rows = [r for r in audits[role]['rows'] if r['operation'] == operation]
        selected[(role, operation)] = rows
        if not present:
            if rows:
                errors.append(role + ':' + operation + ': unexpected wire traffic')
            continue
        checks = validate_receipts({key: rows, 'map': records['map']}, count, profile, run_id, period_ns, 'light')
        errors.extend(role + ':' + operation + ': ' + error for error in checks)
        if any(r['clock_id'] != 'sim:' + run_id for r in rows):
            errors.append(role + ':' + operation + ': clock mismatch')
        if operation.startswith('publish:'):
            peers = (1 if metadata else 2) if key == 'bundle' else (0 if metadata else 1)
            if any(r['connections'] != peers for r in rows):
                errors.append(role + ':' + operation + ': subscriber topology differs')
    allowed = {(role, op) for role, op, _, _ in plans}
    for role, audit in audits.items():
        if any((role, r['operation']) not in allowed for r in audit['rows']):
            errors.append(role + ': unexpected audit operation')
    stats = {}
    for (role, operation), rows in selected.items():
        if not operation.startswith(('serialize:', 'deserialize:')):
            continue
        if any(r['end_ns'] < r['start_ns'] or r['thread_cpu_ns'] < 0 or r['wire_bytes'] <= 0 for r in rows):
            errors.append(role + ':' + operation + ': invalid wire interval')
        stats[role + '.' + operation] = dict(count=len(rows),
            wall_ns=percentile_set([r['end_ns'] - r['start_ns'] for r in rows]),
            thread_cpu_ns=percentile_set([r['thread_cpu_ns'] for r in rows]),
            wire_bytes=sorted({r['wire_bytes'] for r in rows}))
    sender = {r['sample_id']: r for r in selected[('sensor', 'serialize:SensorBundle')]}
    receiver = {r['sample_id']: r for r in selected[('perception', 'deserialize:SensorBundle')]}
    endpoints = defaultdict(dict)
    for event in events:
        if event['stage'] in ('timing.bundle_publish', 'timing.bundle_callback'):
            endpoints[event['parent_sample_id']][event['stage']] = event
    samples = []
    for sequence in expected['bundle']:
        identity = 'sensors.bundle:fixture.radar:%s:%d' % (run_id, sequence)
        ends = endpoints[identity]
        if identity not in sender or identity not in receiver or len(ends) != 2:
            errors.append('bundle wire chain incomplete: ' + identity)
            continue
        sent, received = sender[identity], receiver[identity]
        if sent['wire_bytes'] != received['wire_bytes']:
            errors.append('bundle wire size differs: ' + identity)
        published = ends['timing.bundle_publish']
        start = published['monotonic_ns'] - published['metric_value_ns']
        callback = ends['timing.bundle_callback']['monotonic_ns']
        parts = dict(publish_to_serialize_ns=sent['start_ns'] - start,
                     serialize_ns=sent['end_ns'] - sent['start_ns'],
                     queue_transport_schedule_ns=received['start_ns'] - sent['end_ns'],
                     deserialize_ns=received['end_ns'] - received['start_ns'],
                     deserialize_to_callback_ns=callback - received['end_ns'])
        if any(value < 0 for value in parts.values()):
            errors.append('wire interval regression: ' + identity)
        samples.append(dict(sample_id=identity, parts=parts, total_ns=callback - start))
    return dict(errors=list(dict.fromkeys(errors)), operations=stats, samples=samples,
                parts_ns={key: percentile_set([s['parts'][key] for s in samples])
                          for key in samples[0]['parts']} if samples else {},
                raw_ir_semantics=('producer publish attempts only; zero raw IR subscribers' if metadata
                                  else 'observer receives independent raw IR'),
                bundle_semantics='sensor serialization and perception deserialize/callback audited')
