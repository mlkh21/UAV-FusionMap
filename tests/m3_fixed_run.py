"""Execute fixed M3 against saved inputs/expectations; never import or recompute an oracle."""
import argparse
import datetime
import io
import json
import math
from pathlib import Path
import sys

from ufm_mapping.fixed_interval_probability_map import FixedIntervalProbabilityMap
from ufm_mapping.fixed_probability_map import FixedProbabilityMap
from ufm_mapping.m3_contract import validate_interval_quality
from ufm_ros_contract.perf01a_codec import from_ros_snapshot, to_ros_snapshot
from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result


def _wire(message):
    stream = io.BytesIO()
    message.serialize(stream)
    return type(message)().deserialize(stream.getvalue())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True,
                        help='saved M3-SW-01 fixtures.json with config.json alongside')
    parser.add_argument('--output-root', type=Path,
                        default=Path(__file__).resolve().parents[1] / '.runtime/runs')
    args = parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run_id = 'm3-fixed-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = args.output_root.resolve() / run_id
    run.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, errors=[], run_id=run_id, python=sys.executable,
        input=str(args.input.resolve()), map_accumulation_executed=False,
        scope='fixed synthetic M3 accumulation only; no ROS runtime or real quality acceptance')
    outputs = []
    try:
        spec = json.loads(args.input.with_name('config.json').read_text())
        cases = json.loads(args.input.read_text())
        if not cases:
            raise ValueError('empty saved M3 fixture artifact')
        with (run / 'config.json').open('x') as handle:
            json.dump(spec, handle, indent=2)
        arithmetic, profile = spec['arithmetic'], spec['interval_profile']
        point = [arithmetic['origin'][axis] + (arithmetic['cell_index'][axis] + .5) *
                 arithmetic['resolution'][axis] for axis in range(3)]
        for case in cases:
            observations, expectations = case['observations'], case['expectations']
            if not observations or len(observations) != len(expectations):
                raise ValueError('M3 saved input/expectation length differs')
            header = observations[0]['header']
            candidate = FixedIntervalProbabilityMap(spec, header['run_id'], header['clock_id'])
            baseline = FixedProbabilityMap(arithmetic, header['run_id'], header['clock_id'])
            results, previous_revision = [], 0
            for index, (row, expected) in enumerate(zip(observations, expectations)):
                label = case['name'] + ':' + str(index)
                report['map_accumulation_executed'] = True
                changed = candidate.update(row)
                baseline_changed = baseline.update(row)
                if changed != (expected['revision'] != previous_revision) or changed != baseline_changed:
                    raise ValueError('M3 contribution differs: ' + label)
                previous_revision = expected['revision']
                request = dict(map_id=arithmetic['map_id'], frame_id='odom', run_id=header['run_id'],
                    clock_id=header['clock_id'], query_timestamp=row['header']['timestamp'],
                    max_age_ns=arithmetic['evidence_ttl_ns'], point=point)
                snapshot = candidate.snapshot()
                result, m2_result = candidate.query(**request), baseline.query(**request)
                for key in ('probability', 'status', 'observed', 'last_observed_timestamp', 'revision', 'index'):
                    if result[key] != m2_result[key]:
                        raise ValueError('M3 nominal path differs from M2: ' + label + ':' + key)
                for key in ('status', 'observed', 'last_observed_timestamp', 'revision'):
                    if result[key] != expected[key]:
                        raise ValueError('M3 differs from saved ' + key + ': ' + label)
                if expected['probability'] is None:
                    if result['probability'] is not None:
                        raise ValueError('M3 invented nominal evidence: ' + label)
                elif not math.isclose(result['probability'], expected['probability'], rel_tol=0., abs_tol=1e-12):
                    raise ValueError('M3 differs from saved nominal probability: ' + label)
                if result['confidence'] is not None:
                    raise ValueError('M3 invented calibrated confidence')
                quality = result['uncertainty']
                available = quality is not None and quality['status'] == 'available'
                if available != expected['quality_available']:
                    raise ValueError('M3 differs from saved quality availability: ' + label)
                if result['observed']:
                    validate_interval_quality(result['probability'], quality, spec, output=True)
                    source = profile['output_source' if available else 'unavailable_source']
                    if quality['source'] != source or quality['kind'] != profile['kind']:
                        raise ValueError('M3 cumulative quality source differs')
                if available:
                    if (not isinstance(expected['interval'], list) or len(expected['interval']) != 2 or
                            any(not math.isclose(a, b, rel_tol=0., abs_tol=1e-12)
                                for a, b in zip(quality['value'], expected['interval']))):
                        raise ValueError('M3 differs from saved interval: ' + label)
                elif expected['interval'] is not None:
                    raise ValueError('M3 silently discarded a saved available interval: ' + label)
                if snapshot['header']['timestamp'] != (expected['last_observed_timestamp'] or 0):
                    raise ValueError('M3 snapshot refreshed evidence time')
                if len(snapshot['cells']) != int(expected['observed']):
                    raise ValueError('M3 saved single-cell fixture coverage differs')
                wire_query = from_ros_query_result(_wire(to_ros_query_result(result)))
                wire_snapshot = from_ros_snapshot(_wire(to_ros_snapshot(snapshot)))
                for key in result:
                    if key not in ('probability', 'uncertainty') and wire_query[key] != result[key]:
                        raise ValueError('M3 query wire field differs: ' + key)
                if result['observed']:
                    if wire_query['uncertainty'] != quality:
                        raise ValueError('M3 wire quality changed')
                    validate_interval_quality(wire_query['probability'], wire_query['uncertainty'],
                                              spec, output=True, wire=True)
                elif wire_query['probability'] is not None or wire_query['uncertainty']['status'] != 'unavailable':
                    raise ValueError('M3 wire invented evidence')
                for cell in wire_snapshot['cells']:
                    validate_interval_quality(cell['probability'], cell['uncertainty'], spec,
                                              output=True, wire=True)
                if candidate.snapshot() != snapshot:
                    raise ValueError('M3 read or wire conversion changed state')
                results.append(dict(changed=changed, query=result, snapshot=snapshot,
                                    wire_query=wire_query, wire_snapshot=wire_snapshot))
            outputs.append(dict(name=case['name'], results=results))
        report.update(passed=True, scenario_count=len(outputs),
                      observation_count=sum(len(case['results']) for case in outputs),
                      nominal_exactly_matches_m2=True)
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
