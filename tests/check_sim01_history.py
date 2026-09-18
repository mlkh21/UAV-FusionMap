"""固定SIM-00B历史样本的源→坐标→时钟门控重建；不是ROS/bag或实时验收。"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import yaml

from ufm_simulation.mavlink_source import decode_source_packet
from ufm_simulation.source_timeline import SourceTimeline
from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.clock_gate import StateClockGate


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def check_history(input_path, config):
    run_id = input_path.parent.name
    timeline = SourceTimeline(
        run_id, warmup_stable_sim_ns=int(config['warmup_stable_sim_ns']),
        startup_timeout_wall_s=config['startup_timeout_wall_s'],
        pending_limit=config['pending_limit'],
        pending_timeout_wall_s=config['pending_timeout_wall_s'],
        source_timeout_wall_s=config['source_timeout_wall_s'])
    gate = StateClockGate(run_id, config['pending_limit'], config['pending_timeout_wall_s'])
    events_count = Counter()
    diagnostic_count = Counter()
    source_ids, adapter_ids = set(), set()
    source_by_id = {}
    stamps, source_stamps = [], []
    max_input_state_ns = None
    rejected = []
    lines = 0

    def verify(state, adapted):
        header = state['header']
        require(header['run_id'] == run_id and header['clock_id'] == 'sim:' + run_id,
                'run_or_clock_changed')
        require(header['status'] == 'valid', 'unexpected_nonvalid_state')
        require(header['frame_id'] == ('odom' if adapted else 'world_ned'), 'wrong_reference_frame')
        body = 'base_link' if adapted else 'body_frd'
        require(state['body_frame_id'] == body and state['velocity_frame_id'] == body,
                'wrong_body_or_velocity_frame')
        require(header['source_type'] == ('derived' if adapted else 'simulation'), 'wrong_source_type')
        require(state['state_source'] == 'estimated', 'wrong_state_source')
        require(state['quality']['confidence'] is None, 'invented_confidence')
        require(state['quality']['uncertainty']['status'] == 'unavailable'
                and state['quality']['uncertainty']['value'] is None, 'invented_covariance')
        clock = gate.last_clock_ns if adapted else timeline.last_clock_ns
        require(clock is not None and header['timestamp'] <= clock, 'state_ahead_of_clock')
        seen = adapter_ids if adapted else source_ids
        require(header['sample_id'] not in seen, 'duplicate_published_sample')
        seen.add(header['sample_id'])
        if adapted:
            require(header['sample_id'].startswith('sensors.state:'), 'wrong_adapted_identity')
            original_id = header['sample_id'][len('sensors.state:'):]
            source = source_by_id[original_id]
            require(header['timestamp'] == source['header']['timestamp'], 'sampling_time_changed')
            require(state['quality'] == source['quality'], 'unknown_quality_not_preserved')
            require(not stamps or header['timestamp'] > stamps[-1], 'adapted_time_not_increasing')
            stamps.append(header['timestamp'])
        else:
            require(not source_stamps or header['timestamp'] > source_stamps[-1], 'source_time_not_increasing')
            source_stamps.append(header['timestamp'])
            source_by_id[header['sample_id']] = state

    with input_path.open() as stream:
        for lines, line in enumerate(stream, 1):
            row = json.loads(line)
            try:
                sample = decode_source_packet(
                    bytes.fromhex(row['wire_hex']), row['framing'],
                    sysid=config['sysid'], compid=config['compid'],
                    norm_tolerance=config['quaternion_norm_tolerance'])
            except ValueError as exc:
                rejected.append({'line': lines, 'reason': str(exc)})
                continue
            if sample is None:
                continue
            if sample['type'] == 'odometry':
                ns = sample['state']['header']['timestamp']
                max_input_state_ns = ns if max_input_state_ns is None else max(max_input_state_ns, ns)
            now = row['receipt_monotonic']
            for event in timeline.consume(sample, now):
                events_count[event['type']] += 1
                if event['type'] == 'diagnostic':
                    diagnostic_count[event['reason']] += 1
                elif event['type'] == 'clock':
                    # 保持源事件顺序：先覆盖接收端clock，再递交本轮状态。
                    for state in gate.consume_clock(event['timestamp'], now):
                        verify(state, True)
                elif event['type'] == 'state':
                    verify(event['state'], False)
                    adapted = adapt_state(event['state'], config, config['quaternion_norm_tolerance'])
                    for state in gate.consume_state(adapted, now):
                        verify(state, True)
            require(timeline.phase != 'FAULT' and not gate.locked, 'unexpected_terminal_state')

    result = {
        'scope': 'fixed historical interface reconstruction; no ROS, bag or real-time validation',
        'input': str(input_path), 'python': sys.executable, 'run_id': run_id, 'input_lines': lines,
        'phase': timeline.phase, 'events': dict(events_count), 'source_counters': dict(timeline.counters),
        'adapter_gate_counters': dict(gate.counters), 'diagnostics': dict(diagnostic_count),
        'source_valid_count': len(source_stamps), 'adapter_valid_count': len(stamps),
        'first_valid_ns': stamps[0] if stamps else None, 'last_valid_ns': stamps[-1] if stamps else None,
        'last_clock_ns': timeline.last_clock_ns, 'gate_pending_count': gate.pending_count,
        'source_pending_evidence': {'max_input_state_ns': max_input_state_ns,
                                    'last_source_output_ns': source_stamps[-1] if source_stamps else None},
        'rejections': rejected, 'passed': False}
    errors = []
    checks = {
        'history_counts': (events_count['clock'] == 6051
                           and timeline.counters['accepted_odometry'] == 2407
                           and diagnostic_count == {'preparing_estimator_reset': 2}
                           and len(source_stamps) == len(stamps) == 2103),
        'no_rejections': not rejected,
        'active_unlocked': timeline.phase == 'ACTIVE' and not gate.locked,
        'no_remaining_states': (gate.pending_count == 0 and bool(source_stamps)
                                and source_stamps[-1] == max_input_state_ns
                                and max_input_state_ns <= timeline.last_clock_ns),
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(name)
    result.update(checks=checks, errors=errors, passed=not errors)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    config_path = Path(__file__).resolve().parents[1] / 'configs/sim01_state.yaml'
    # open x 在任何运行前拒绝覆盖已有证据。
    with args.output.open('x') as output:
        try:
            with config_path.open() as stream:
                config = yaml.safe_load(stream)
            result = check_history(args.input.resolve(), config)
            result['config'] = str(config_path)
        except Exception as exc:
            result = {'passed': False, 'error': type(exc).__name__ + ': ' + str(exc),
                      'input': str(args.input.resolve()), 'python': sys.executable}
        json.dump(result, output, indent=2, ensure_ascii=False)
        output.write('\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
