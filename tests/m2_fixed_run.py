"""Run fixed M2 against saved M2-SW-01 inputs/expectations, without invoking the oracle."""
import argparse
import datetime
import json
import math
from pathlib import Path
import sys

from ufm_mapping.fixed_probability_map import FixedProbabilityMap
from ufm_ros_contract.perf01a_codec import from_ros_snapshot, to_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True,
                        help='M2-SW-01 fixtures.json; its config.json must be alongside it')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    run_id = 'm2-fixed-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, errors=[], run_id=run_id, python=sys.executable,
        scope='fixed-grid synthetic M2 only; no ROS runtime or real sensing',
        input=str(args.input.resolve()), map_accumulation_executed=False)
    outputs = []
    try:
        spec = json.loads(args.input.with_name('config.json').read_text())
        cases = json.loads(args.input.read_text())
        if not cases:
            raise ValueError('empty M2-SW-01 fixture artifact')
        with (run / 'config.json').open('x') as handle:
            json.dump(spec, handle, indent=2)
        point = [spec['origin'][axis] + (spec['cell_index'][axis] + .5) * spec['resolution'][axis]
                 for axis in range(3)]
        for case in cases:
            rows, expected, kinds = case['observations'], case['expectations'], case['steps']
            if not rows or len(rows) != len(expected) or len(kinds) != len(rows):
                raise ValueError('M2 fixture input/expectation length mismatch')
            header = rows[0]['header']
            local_map = FixedProbabilityMap(spec, header['run_id'], header['clock_id'])
            results, revision = [], 0
            for index, (row, reference, kind) in enumerate(zip(rows, expected, kinds)):
                report['map_accumulation_executed'] = True
                changed = local_map.update(row)
                contributed = kind in ('occupied', 'free')
                revision += int(contributed)
                if changed != contributed:
                    raise ValueError('M2 contribution mismatch: %s:%d' % (case['name'], index))
                request = dict(map_id=spec['map_id'], frame_id=spec['frame_id'],
                    run_id=header['run_id'], clock_id=header['clock_id'],
                    query_timestamp=row['header']['timestamp'], point=point,
                    max_age_ns=spec['evidence_ttl_ns'])
                result = local_map.query(**request)
                if (result['observed'] != reference['observed'] or
                        result['last_observed_timestamp'] != reference['last_observed_timestamp'] or
                        result['revision'] != revision):
                    raise ValueError('M2 identity, revision or evidence time differs: ' + case['name'])
                probability = reference['probability']
                if probability is None:
                    if result['probability'] is not None or result['status'] != 'unavailable':
                        raise ValueError('M2 invented evidence: ' + case['name'])
                elif not math.isclose(result['probability'], probability, rel_tol=0., abs_tol=1e-12):
                    raise ValueError('M2 differs from saved rational oracle: ' + case['name'])
                wire_query = from_ros_query_result(to_ros_query_result(result))
                if (wire_query['last_observed_timestamp'] != result['last_observed_timestamp'] or
                        wire_query['status'] != result['status'] or
                        (probability is not None and not math.isclose(wire_query['probability'],
                            probability, rel_tol=0., abs_tol=1e-6))):
                    raise ValueError('M2 query wire contract differs: ' + case['name'])
                snapshot = local_map.snapshot()
                wire_snapshot = from_ros_snapshot(to_ros_snapshot(snapshot))
                if wire_snapshot['revision'] != revision:
                    raise ValueError('M2 snapshot wire revision differs')
                results.append(dict(changed=changed, query=result, snapshot=snapshot))
            outputs.append(dict(name=case['name'], results=results))
        report.update(passed=True, scenario_count=len(outputs),
                      observation_count=sum(len(case['results']) for case in outputs))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
    with (run / 'results.json').open('x') as handle:
        json.dump(outputs, handle, indent=2)
    with (run / 'report.json').open('x') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
