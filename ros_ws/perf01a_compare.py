"""预登记同负载AB/BA观察器对照，串行新建run，保留所有失败。"""
import argparse
import datetime
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys

from perf01a_metrics import percentile_set


def candidate_decision(results):
    modes = sorted({r['mode'] for r in results})
    comparisons = []
    for mode in modes:
        pairs = sorted({r['pair'] for r in results if r['mode'] == mode})
        for pair in pairs:
            rows = {r['backend']: r for r in results if r['mode'] == mode and r['pair'] == pair}
            if set(rows) != {'standard', 'numpy'} or any(r.get('p99_ms') is None for r in rows.values()):
                return dict(accepted=False, reason='incomplete paired comparison')
            before, after = rows['standard']['p99_ms'], rows['numpy']['p99_ms']
            comparisons.append(dict(mode=mode, pair=pair, standard_ms=before, numpy_ms=after,
                                    reduction_fraction=(before - after) / before))
    accepted = bool(comparisons) and all(r['exit'] == 0 and r['summary']['passed'] for r in results)
    for mode in modes:
        reductions = [r['reduction_fraction'] for r in comparisons if r['mode'] == mode]
        accepted = accepted and len(reductions) >= 3 and min(reductions) > 0 and statistics.median(reductions) >= .10
    return dict(accepted=accepted, pairs=comparisons,
                rule='all functional checks; >=3 pairs/mode; all P99 reductions positive; median reduction >=10%')


def base_samples(events):
    stages = {}
    for event in events:
        if event['status'] == 'valid':
            stages.setdefault(event['parent_sample_id'], {})[event['stage']] = event['monotonic_ns']
    required = {'radar_receive', 'occupancy_ready', 'map_snapshot_publish'}
    return [dict(sensor_to_occupancy_ns=row['occupancy_ready'] - row['radar_receive'],
                 sensor_to_map_ns=row['map_snapshot_publish'] - row['radar_receive'])
            for row in stages.values() if required <= row.keys()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration-s', type=float, default=10.)
    parser.add_argument('--pairs', type=int, default=3)
    parser.add_argument('--port', type=int, default=11500)
    parser.add_argument('--label', default='segmented-baseline')
    parser.add_argument('--image-buff-size', type=int, default=65536)
    parser.add_argument('--no-segmented-timing', action='store_true')
    parser.add_argument('--modes', nargs='+', choices=('full', 'light', 'metadata'), default=['full', 'light'])
    parser.add_argument('--wire-profile', action='store_true')
    parser.add_argument('--sample-resources', action='store_true')
    parser.add_argument('--receive-backends', nargs='+', choices=('standard', 'numpy'), default=['standard'])
    args = parser.parse_args()
    if not 0 < args.duration_s <= 60 or not 1 <= args.pairs <= 10:
        parser.error('duration must be in (0,60], pairs in [1,10]')
    if len(set(args.modes)) != len(args.modes) or len(set(args.receive_backends)) != len(args.receive_backends):
        parser.error('modes and receive-backends must be unique')
    if 'metadata' in args.modes and not args.wire_profile:
        parser.error('metadata mode requires --wire-profile')
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    output = root / '.runtime/runs' / ('perf01a-compare-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    output.mkdir(parents=True, exist_ok=False)
    plan = []
    variants = [(mode, backend) for mode in args.modes for backend in args.receive_backends]
    for pair in range(args.pairs):
        offset = pair % len(variants)
        for mode, backend in variants[offset:] + variants[:offset]:
            group = mode if len(args.receive_backends) == 1 else mode + ':' + backend
            plan.append(dict(pair=pair, mode=mode, backend=backend, group=group, command=[sys.executable,
                str(root / 'ros_ws/perf01a_run.py'), '--duration-s', str(args.duration_s),
                '--scenario', 'full_ir', '--observer-mode', mode,
                '--port', str(args.port + len(plan)), '--image-buff-size', str(args.image_buff_size),
                '--receive-backend', backend] +
                ([] if args.no_segmented_timing else ['--segmented-timing']) +
                (['--wire-profile'] if args.wire_profile else []) +
                (['--sample-resources'] if args.sample_resources else [])))
    manifest = dict(label=args.label, platform=platform.platform(), python=sys.executable,
                    duration_s=args.duration_s, plan=plan, percentile='nearest-rank; no sample exclusions',
                    comparison='paired P99 differences; descriptive, not a significance test')
    if len(args.receive_backends) > 1:
        manifest['candidate_acceptance'] = ('all functional checks; >=3 pairs/mode; every paired P99 lower; '
                                            'median reduction >=10%; 20ms target reported separately')
    with (output / 'manifest.json').open('x') as handle:
        json.dump(manifest, handle, indent=2)
    results, reports, sample_groups = [], [], {item['group']: [] for item in plan}
    for index, item in enumerate(plan):
        log = output / ('run-%02d.log' % index)
        with log.open('x') as handle:
            process = subprocess.run(item['command'], stdout=handle, stderr=subprocess.STDOUT)
        lines = log.read_text().splitlines()
        summary = next((json.loads(line) for line in reversed(lines) if line.startswith('{"run":')), None)
        row = dict(item, exit=process.returncode, summary=summary)
        results.append(row)
        if summary:
            report = json.loads((Path(summary['run']) / 'perf-report.json').read_text())
            reports.append((item, report))
            event_path = Path(summary['run']) / 'events.json'
            if event_path.exists():
                sample_groups[item['group']].extend(base_samples(json.loads(event_path.read_text())))
            row['p99_ms'] = report.get('latency_percentiles', {}).get('sensor_to_occupancy_ns', {}).get('p99')
            if row['p99_ms'] is not None:
                row['p99_ms'] /= 1e6
        print(json.dumps(row), flush=True)
    pooled = {}
    for mode in sample_groups:
        samples = sample_groups[mode]
        pooled[mode] = dict(samples=len(samples),
            sensor_to_occupancy_ms=percentile_set([s['sensor_to_occupancy_ns'] / 1e6 for s in samples]),
            sensor_to_map_ms=percentile_set([s['sensor_to_map_ns'] / 1e6 for s in samples]))
    paired = []
    for pair in range(args.pairs):
        rows = {r['mode']: r for r in results if r['pair'] == pair}
        if len(args.receive_backends) == 1 and all(rows.get(m, {}).get('p99_ms') is not None for m in ('full', 'light')):
            paired.append(rows['full']['p99_ms'] - rows['light']['p99_ms'])
    passed = len(reports) == len(plan) and all(r['passed'] for _, r in reports)
    result = dict(functional_passed=passed, results=results, pooled=pooled,
                  paired_full_minus_light_p99_ms=paired)
    if len(args.receive_backends) > 1:
        result['candidate_decision'] = candidate_decision(results)
    with (output / 'comparison.json').open('x') as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(dict(comparison=str(output), functional_passed=passed)), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
