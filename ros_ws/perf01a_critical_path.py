"""Read-only per-sample IR/Bundle timing join for completed async runs."""
import argparse
import json
from pathlib import Path

from perf01a_metrics import percentile_set


def indexed(rows, key, label):
    result = {}
    for row in rows:
        identity = row[key]
        if identity in result:
            raise ValueError('duplicate %s: %s' % (label, identity))
        result[identity] = row
    return result


def wire_rows(audit, operation):
    return indexed((row for row in audit['rows'] if row['operation'] == operation),
                   'sample_id', operation)


def analyze(report, matcher, infrared_audit, infrared_wire, sensor_wire, perception_wire):
    if not report['passed'] or report['errors'] or report['segmented']['errors'] or report['wire']['errors']:
        raise ValueError('source run has failed or incomplete timing/wire gates')
    run_id = report['run_id']
    if matcher['run_id'] != run_id or infrared_audit['run_id'] != run_id:
        raise ValueError('source run identity differs')
    radar = indexed(matcher['receipts']['radar'], 'sample_id', 'radar receipt')
    infrared = indexed(matcher['receipts']['infrared'], 'sample_id', 'infrared receipt')
    produced = indexed(infrared_audit['rows'], 'sample_id', 'infrared producer')
    decisions = indexed((row for row in matcher['decisions'] if not row['reason']),
                        'radar_id', 'accepted radar decision')
    samples = indexed(report['segmented']['samples'], 'root', 'timed sample')
    if {'sensors.bundle:' + key for key in decisions} != set(samples):
        raise ValueError('timed samples differ from accepted decisions')
    ir_sent = wire_rows(infrared_wire, 'serialize:InfraredFrame')
    ir_received = wire_rows(sensor_wire, 'deserialize:InfraredFrame')
    ir_callback = wire_rows(sensor_wire, 'callback:InfraredFrame')
    bundle_sent = wire_rows(sensor_wire, 'serialize:SensorBundle')
    bundle_received = wire_rows(perception_wire, 'deserialize:SensorBundle')
    bundle_callback = wire_rows(perception_wire, 'callback:SensorBundle')
    rows = []
    for root, sample in samples.items():
        if not root.startswith('sensors.bundle:'):
            raise ValueError('unexpected bundle identity: ' + root)
        decision = decisions[root[len('sensors.bundle:'):]]
        radar_row = radar[decision['radar_id']]
        ir_id = decision['infrared_id']
        ir_row = infrared[ir_id]
        ir_producer = produced[ir_id]
        sent, received, callback = ir_sent[ir_id], ir_received[ir_id], ir_callback[ir_id]
        bs, br, bc = bundle_sent[root], bundle_received[root], bundle_callback[root]
        start = radar_row['receive_monotonic_ns']
        ready = decision['decision_monotonic_ns']
        ir_entered = ir_row['receive_monotonic_ns']
        if (callback['callback_ns'] != ir_entered or
                sent['wire_bytes'] != received['wire_bytes'] or
                bs['wire_bytes'] != br['wire_bytes'] or
                bs['infrared_id'] != ir_id or br['infrared_id'] != ir_id or
                bc['callback_ns'] < br['end_ns'] or
                not ir_producer['published']):
            raise ValueError('wire/receipt identity or boundary differs: ' + root)
        if (ir_row['timestamp'] != sent['timestamp'] or
                radar_row['timestamp'] != decision['timestamp'] or
                sample['sensor_to_occupancy_ns'] < 0):
            raise ValueError('sampling reference differs: ' + root)
        parts = dict(
            ir_generate_to_publish_ns=ir_producer['publish_monotonic_ns'] - ir_producer['generated_monotonic_ns'],
            ir_publish_to_serialize_ns=sent['start_ns'] - ir_producer['publish_monotonic_ns'],
            ir_serialize_ns=sent['end_ns'] - sent['start_ns'],
            ir_queue_transport_schedule_ns=received['start_ns'] - sent['end_ns'],
            ir_deserialize_ns=received['end_ns'] - received['start_ns'],
            ir_deserialize_to_callback_ns=ir_entered - received['end_ns'],
            ir_callback_lock_ns=ir_row['lock_wait_ns'],
            ir_callback_decode_ns=ir_row['decode_ns'],
            ir_cache_emit_ns=ir_row['cache_and_emit_ns'],
            radar_to_decision_ns=ready - start,
            ir_to_decision_ns=ready - ir_entered,
            last_input_callback_to_decision_ns=ready - max(ir_entered, start),
            decision_to_bundle_serialize_ns=bs['start_ns'] - ready,
            bundle_serialize_ns=bs['end_ns'] - bs['start_ns'],
            bundle_queue_transport_schedule_ns=br['start_ns'] - bs['end_ns'],
            bundle_deserialize_ns=br['end_ns'] - br['start_ns'],
            bundle_deserialize_to_callback_ns=bc['callback_ns'] - br['end_ns'],
        )
        if any(value < 0 for value in parts.values()):
            raise ValueError('wall-clock stage order differs: ' + root)
        if abs((ready - start) - sample['segments_ns']['pairing_wait_and_build']) > 1_000_000:
            raise ValueError('decision/segment timing differs: ' + root)
        rows.append(dict(root=root, infrared_id=ir_id, sensor_to_occupancy_ns=sample['sensor_to_occupancy_ns'],
                         ir_callback_minus_radar_callback_ns=ir_entered - start,
                         parts_ns=parts))
    rows.sort(key=lambda row: row['sensor_to_occupancy_ns'], reverse=True)
    return dict(run_id=run_id, count=len(rows),
                stats_ns={key: percentile_set([row['parts_ns'][key] for row in rows])
                          for key in rows[0]['parts_ns']} if rows else {},
                sensor_to_occupancy_ns=percentile_set([row['sensor_to_occupancy_ns'] for row in rows]),
                samples=rows,
                semantics='signed IR callback offset; queue_transport_schedule includes queues, copying, transport and scheduling; independent P99 cannot be summed')


def analyze_match_trace(report, matcher):
    """Correlate exact pairing with state/clock inputs and held matcher locks."""
    if not report['passed'] or report['errors'] or report['profile']['pairing_policy'] != 'exact':
        raise ValueError('passing exact-pairing source run required')
    if matcher['run_id'] != report['run_id'] or matcher['errors']:
        raise ValueError('matcher source identity or errors differ')
    trace = matcher['match_trace']
    locks = indexed(trace['locks'], 'lock_id', 'matcher lock')
    waits = analyze_wait_trace(trace, locks) if 'worker_polls' in trace else None
    states = indexed(trace['state_inputs'], 'sample_id', 'matcher state input')
    sensors = indexed(trace['sensor_inputs'], 'sample_id', 'matcher sensor input')
    for row in locks.values():
        if not 0 <= row['entered_ns'] <= row['acquired_ns'] <= row['released_ns']:
            raise ValueError('matcher lock time regression')
    for row in list(states.values()) + list(sensors.values()):
        if row['lock_id'] not in locks or not (locks[row['lock_id']]['acquired_ns'] <=
                row['begin_ns'] <= row['matcher_end_ns'] <= row['end_ns'] <=
                locks[row['lock_id']]['released_ns']):
            raise ValueError('state input lock/time mismatch')
    radar = indexed(matcher['receipts']['radar'], 'sample_id', 'radar receipt')
    infrared = indexed(matcher['receipts']['infrared'], 'sample_id', 'infrared receipt')
    accepted = [d for d in matcher['decisions'] if not d['reason']]
    samples = indexed(report['segmented']['samples'], 'root', 'timed sample')
    if len(accepted) != len(samples):
        raise ValueError('accepted decision/timing count differs')
    result = []
    for decision in accepted:
        root = 'sensors.bundle:' + decision['radar_id']
        if root not in samples:
            raise ValueError('accepted decision timing missing: ' + root)
        trigger = decision['trigger']
        lock = locks[trigger['lock_id']]
        decided = decision['decision_monotonic_ns']
        if (lock['role'] != 'worker' or trigger['source'] != 'advance' or
                not lock['acquired_ns'] <= trigger['begin_ns'] <= decided <= lock['released_ns']):
            raise ValueError('unexpected exact decision trigger or lock: ' + root)
        stamp = decision['timestamp']
        # Do not infer state identity from its sequence: locate by unique exact timestamp.
        state_candidates = [s for s in states.values() if s['timestamp'] == stamp and
                            s['matcher_end_ns'] <= decided]
        clock_candidates = [r for r in locks.values() if r['role'] == 'clock' and
                            r['timestamp'] >= stamp and r['released_ns'] <= decided]
        if len(state_candidates) != 1 or not clock_candidates:
            raise ValueError('exact state/clock input evidence missing: ' + root)
        state = state_candidates[0]
        clock = min(clock_candidates, key=lambda r: r['released_ns'])
        r = radar[decision['radar_id']]['receive_monotonic_ns']
        ir = infrared[decision['infrared_id']]['receive_monotonic_ns']
        radar_input = sensors[decision['radar_id']]
        ir_input = sensors[decision['infrared_id']]
        if (radar_input['kind'] != 'radar' or ir_input['kind'] != 'infrared' or
                radar_input['timestamp'] != stamp or ir_input['timestamp'] != stamp or
                radar_input['begin_ns'] < r or ir_input['begin_ns'] < ir):
            raise ValueError('sensor matcher input identity/time differs: ' + root)
        ready = max(radar_input['matcher_end_ns'], ir_input['matcher_end_ns'],
                    state['matcher_end_ns'],
                    clock['released_ns'])
        if ready > decided:
            raise ValueError('required input after decision: ' + root)
        held = {}
        for item in locks.values():
            span = max(0, min(decided, item['released_ns']) - max(ready, item['acquired_ns']))
            if span:
                held[item['role']] = held.get(item['role'], 0) + span
        row = dict(root=root, sensor_to_occupancy_ns=samples[root]['sensor_to_occupancy_ns'],
                           trigger=trigger['source'], state_sample_id=state['sample_id'],
                           state_end_ns=state['matcher_end_ns'], clock_timestamp=clock['timestamp'],
                           clock_end_ns=clock['released_ns'], ir_receive_ns=ir,
                           ir_matcher_input_end_ns=ir_input['matcher_end_ns'],
                           last_required_input_ns=ready, decision_ns=decided,
                           ready_to_worker_lock_ns=max(0, lock['acquired_ns'] - ready),
                           worker_lock_to_decision_ns=decided - lock['acquired_ns'],
                           lock_held_since_ready_ns=held)
        if waits is not None:
            poll = waits['worker_polls'][lock['lock_id']]
            row['worker_wait'] = dict(
                ready_to_worker_entry_ns=lock['entered_ns'] - ready,
                worker_entry_to_lock_ns=lock['acquired_ns'] - lock['entered_ns'],
                sleep_overlap_since_ready_ns=max(0, min(lock['entered_ns'], poll['wake_ns']) -
                                                 max(ready, poll['sleep_start_ns'])),
                blocking_locks=[dict(lock_id=item['lock_id'], role=item['role'],
                    overlap_ns=min(lock['acquired_ns'], item['released_ns']) -
                               max(ready, item['acquired_ns']),
                    uncovered=waits['lock_gaps'][item['lock_id']])
                    for item in locks.values() if item['lock_id'] != lock['lock_id'] and
                    min(lock['acquired_ns'], item['released_ns']) -
                    max(ready, item['acquired_ns']) >= 1_000_000])
        result.append(row)
    result.sort(key=lambda row: row['sensor_to_occupancy_ns'], reverse=True)
    output = dict(run_id=report['run_id'], count=len(result), samples=result,
                semantics='state/clock completion and ROS callback receipt are observed; lock-held time is overlap, not matcher CPU; gaps can include scheduling and untraced work')
    if 'stages' in trace:
        output['stage_trace'] = analyze_stages(trace['stages'], locks)
    if waits is not None:
        output['wait_trace'] = dict(count=len(waits['worker_polls']),
            semantics='sleep overlap can coincide with another lock; lock gap CPU is same-thread only; no implied network or scheduling attribution')
    return output


def analyze_wait_trace(trace, locks):
    """Validate optional worker sleep and within-lock uninstrumented spans."""
    polls = indexed(trace['worker_polls'], 'lock_id', 'worker poll')
    stages = trace['stages']
    gaps = {}
    for lock_id, lock in locks.items():
        start_cpu = lock['cpu_acquired_ns']
        end_cpu = lock['cpu_released_ns']
        if (not 0 <= start_cpu <= end_cpu or
                end_cpu - start_cpu != lock['lock_thread_cpu_ns']):
            raise ValueError('lock thread CPU boundary differs')
        cursor, cpu_cursor = lock['acquired_ns'], start_cpu
        wall_gap = cpu_gap = 0
        rows = sorted((s for s in stages if s['lock_id'] == lock_id),
                      key=lambda s: (s['start_ns'], -s['end_ns']))
        for stage in rows:
            sc, ec = stage['thread_cpu_start_ns'], stage['thread_cpu_end_ns']
            if (not lock['acquired_ns'] <= stage['start_ns'] <= stage['end_ns'] <= lock['released_ns']
                    or not start_cpu <= sc <= ec <= end_cpu or ec - sc != stage['thread_cpu_ns']):
                raise ValueError('stage thread CPU boundary differs')
            if stage['end_ns'] <= cursor:
                continue  # Nested stage already covered by its parent.
            if stage['start_ns'] < cursor or sc < cpu_cursor:
                raise ValueError('stage intervals overlap without nesting')
            wall_gap += stage['start_ns'] - cursor
            cpu_gap += sc - cpu_cursor
            cursor, cpu_cursor = stage['end_ns'], ec
        wall_gap += lock['released_ns'] - cursor
        cpu_gap += end_cpu - cpu_cursor
        gaps[lock_id] = dict(wall_ns=wall_gap, thread_cpu_ns=cpu_gap)
    for lock_id, poll in polls.items():
        lock = locks.get(lock_id)
        if (lock is None or lock['role'] != 'worker' or
                not 0 <= poll['sleep_start_ns'] <= poll['wake_ns'] <= lock['entered_ns'] <=
                lock['acquired_ns'] or poll['sleep_thread_cpu_ns'] < 0):
            raise ValueError('worker poll/lock boundary differs')
    if set(polls) != {key for key, lock in locks.items() if lock['role'] == 'worker'}:
        raise ValueError('worker poll/lock identity differs')
    return dict(worker_polls=polls, lock_gaps=gaps)


def analyze_stages(rows, locks):
    """Validate scalar spans against acquired locks; keep wall and thread CPU separate."""
    from collections import defaultdict
    by_name = defaultdict(list)
    by_lock = defaultdict(list)
    for row in rows:
        lock = locks.get(row['lock_id'])
        if (lock is None or not lock['acquired_ns'] <= row['start_ns'] <= row['end_ns'] <=
                lock['released_ns'] or row['thread_cpu_ns'] < 0 or
                not isinstance(row['name'], str) or not row['name']):
            raise ValueError('stage lock/time/cpu boundary differs')
        if row['name'] == 'decision.emit' and row['sample_id'] is None:
            raise ValueError('decision stage identity missing')
        by_name[row['name']].append(row)
        by_lock[row['lock_id']].append(row)
    top_locks = {}
    for role in ('state', 'clock', 'worker'):
        selected = sorted((row for row in locks.values() if row['role'] == role),
                          key=lambda row: row['released_ns'] - row['acquired_ns'], reverse=True)[:5]
        top_locks[role] = [dict(lock_id=row['lock_id'], sample_id=row['sample_id'],
                                timestamp=row['timestamp'],
                                wall_ns=row['released_ns'] - row['acquired_ns'],
                                stages=[dict(name=s['name'], sample_id=s['sample_id'],
                                             wall_ns=s['end_ns'] - s['start_ns'],
                                             thread_cpu_ns=s['thread_cpu_ns'])
                                        for s in sorted(by_lock[row['lock_id']], key=lambda s: s['start_ns'])])
                           for row in selected]
    return dict(count=len(rows),
                by_name={name: dict(wall_ns=percentile_set([r['end_ns'] - r['start_ns'] for r in group]),
                                    thread_cpu_ns=percentile_set([r['thread_cpu_ns'] for r in group]))
                         for name, group in by_name.items()}, top_locks=top_locks,
                semantics='per-thread CPU and monotonic wall spans; nested spans and independent percentiles must not be summed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path, nargs='+', help='completed run directories (read-only)')
    parser.add_argument('--top', type=int, default=3, help='tail samples to print per run')
    parser.add_argument('--match-trace', action='store_true', help='join optional state/clock/worker lock trace')
    args = parser.parse_args()
    if args.top < 1:
        parser.error('--top must be positive')
    names = ('perf-report.json', 'matcher-audit.json', 'infrared-audit.json',
             'infrared-wire.json', 'sensor-wire.json', 'perception-wire.json')
    for directory in args.run:
        with_files = [json.loads((directory / name).read_text()) for name in names]
        result = analyze(*with_files)
        if args.match_trace:
            result['match_trace'] = analyze_match_trace(with_files[0], with_files[1])
            result['match_trace']['samples'] = result['match_trace']['samples'][:args.top]
        result['samples'] = result['samples'][:args.top]
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
