"""Freeze M3 motion expectations before execution, or replay saved ones without an oracle."""
import argparse
import copy
import datetime
import io
import json
import math
from pathlib import Path
import sys

from ufm_mapping.rolling_interval_probability_map import RollingIntervalProbabilityMap
from ufm_mapping.rolling_probability_map import RollingProbabilityMap
from ufm_mapping.m3_contract import validate_interval_quality, wire_probability
from ufm_ros_contract.perf01a_codec import (from_ros_occupancy, from_ros_snapshot,
                                         to_ros_occupancy, to_ros_snapshot)
from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result


def _wire(message):
    stream = io.BytesIO()
    message.serialize(stream)
    return type(message)().deserialize(stream.getvalue())


def _state(candidate):
    return copy.deepcopy((candidate.snapshot(), candidate._log_odds, candidate._seen,
                          candidate._input_timestamp, candidate._geometry_timestamp, candidate.origin))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='saved fixtures.json; no oracle imported when replaying')
    parser.add_argument('--output-root', type=Path,
                        default=Path(__file__).resolve().parents[1] / '.runtime/runs')
    args = parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run_id = 'm3-rolling-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = args.output_root.resolve() / run_id
    run.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, errors=[], run_id=run_id, python=sys.executable,
        input=None if args.input is None else str(args.input.resolve()),
        map_accumulation_executed=False,
        scope='offline synthetic M3 rolling/time/state acceptance; no ROS runtime or real calibration')
    outputs = []
    try:
        if args.input is None:
            from m3_fixture import load_spec
            from m3_rolling_scenarios import scenarios
            source = dict(spec=load_spec())
            source['cases'] = scenarios(source['spec'], run_id)
        else:
            source = json.loads(args.input.read_text())
        # Preserve inputs/expectations before creating any map; comparisons read this frozen copy.
        with (run / 'fixtures.json').open('x') as handle:
            json.dump(source, handle, indent=2)
        with (run / 'config.json').open('x') as handle:
            json.dump(source['spec'], handle, indent=2)
        source = json.loads((run / 'fixtures.json').read_text())
        if not source['cases']:
            raise ValueError('empty M3 rolling fixture artifact')
        for case in source['cases']:
            spec = case['spec']
            if not case['steps']:
                raise ValueError('empty M3 rolling scenario')
            header = case['steps'][0]['observation']['header']
            candidate = RollingIntervalProbabilityMap(spec, header['run_id'], header['clock_id'])
            baseline = RollingProbabilityMap(spec['arithmetic'], header['run_id'], header['clock_id'])
            receipts = []
            for index, step in enumerate(case['steps']):
                label = case['name'] + ':' + str(index)
                row = from_ros_occupancy(_wire(to_ros_occupancy(step['observation'])))
                report['map_accumulation_executed'] = True
                changed, baseline_changed = candidate.update(row), baseline.update(row)
                snapshot, expected = candidate.snapshot(), step['expected']
                if changed != expected['changed'] or changed != baseline_changed:
                    raise ValueError('M3 contribution/coverage change differs: ' + label)
                if (snapshot['origin'] != expected['origin'] or snapshot['revision'] != expected['revision'] or
                        snapshot['header']['timestamp'] != expected['map_timestamp'] or
                        len(snapshot['cells']) != expected['cell_count']):
                    raise ValueError('M3 origin, revision, evidence time or coverage differs: ' + label)
                if (set(candidate._cells) != set(candidate._log_odds) or
                        len(candidate._cells) > spec['arithmetic']['max_active_cells'] or
                        candidate.retained_identity_count > spec['arithmetic']['identity_history_limit']):
                    raise ValueError('M3 bounded cell/state/identity contract differs: ' + label)
                queries = []
                for query in step['queries']:
                    request = dict(map_id=spec['arithmetic']['map_id'], frame_id='odom',
                        run_id=header['run_id'], clock_id=header['clock_id'],
                        query_timestamp=query['timestamp'], point=query['point'], max_age_ns=999_000_000)
                    result, original = candidate.query(**request), baseline.query(**request)
                    reference = query['expected']
                    for key in ('probability', 'status', 'observed', 'last_observed_timestamp', 'revision', 'index'):
                        if result[key] != original[key]:
                            raise ValueError('M3 nominal path differs from M2: ' + label + ':' + key)
                    for key in ('status', 'observed', 'last_observed_timestamp', 'revision'):
                        if result[key] != reference[key]:
                            raise ValueError('M3 differs from frozen ' + key + ': ' + label)
                    if 'reason' in reference and result['reason'] != reference['reason']:
                        raise ValueError('M3 frozen query reason differs: ' + label)
                    if reference['probability'] is None:
                        if result['probability'] is not None:
                            raise ValueError('M3 invented evidence: ' + label)
                    elif not math.isclose(result['probability'], reference['probability'], rel_tol=0., abs_tol=1e-12):
                        raise ValueError('M3 differs from frozen probability: ' + label)
                    quality = result['uncertainty']
                    available = quality is not None and quality['status'] == 'available'
                    if available != reference['quality_available'] or result['confidence'] is not None:
                        raise ValueError('M3 frozen quality availability differs: ' + label)
                    if result['observed']:
                        validate_interval_quality(result['probability'], quality, spec, output=True)
                        expected_source = spec['interval_profile']['output_source' if available else 'unavailable_source']
                        if quality['source'] != expected_source:
                            raise ValueError('M3 cumulative source differs: ' + label)
                    if available:
                        bounds = reference['interval']
                        if (not isinstance(bounds, list) or len(bounds) != 2 or
                                any(not math.isclose(a, b, rel_tol=0., abs_tol=1e-12)
                                    for a, b in zip(quality['value'], bounds))):
                            raise ValueError('M3 differs from frozen interval: ' + label)
                    elif reference['interval'] is not None:
                        raise ValueError('M3 discarded a frozen interval: ' + label)
                    wire_query = from_ros_query_result(_wire(to_ros_query_result(result)))
                    expected_wire_mean = None if result['probability'] is None else wire_probability(result['probability'])
                    if wire_query['probability'] != expected_wire_mean:
                        raise ValueError('M3 query wire nominal differs: ' + label)
                    if result['observed']:
                        if wire_query['uncertainty'] != quality:
                            raise ValueError('M3 query wire changed quality: ' + label)
                        validate_interval_quality(wire_query['probability'], wire_query['uncertainty'],
                                                  spec, output=True, wire=True)
                    elif wire_query['probability'] is not None or wire_query['uncertainty']['status'] != 'unavailable':
                        raise ValueError('M3 wire invented missing evidence: ' + label)
                    for key in result:
                        if key not in ('probability', 'uncertainty') and wire_query[key] != result[key]:
                            raise ValueError('M3 query wire field differs: ' + label + ':' + key)
                    queries.append(dict(request=request, result=result, wire_result=wire_query))
                wire_snapshot = from_ros_snapshot(_wire(to_ros_snapshot(snapshot)))
                if (wire_snapshot['origin'] != snapshot['origin'] or wire_snapshot['revision'] != snapshot['revision'] or
                        wire_snapshot['header'] != snapshot['header'] or len(wire_snapshot['cells']) != len(snapshot['cells'])):
                    raise ValueError('M3 snapshot wire geometry differs: ' + label)
                for cell, original_cell in zip(wire_snapshot['cells'], snapshot['cells']):
                    if (cell['probability'] != wire_probability(original_cell['probability']) or
                            any(cell[key] != original_cell[key] for key in cell if key != 'probability')):
                        raise ValueError('M3 snapshot wire cell differs: ' + label)
                    validate_interval_quality(cell['probability'], cell['uncertainty'], spec, output=True, wire=True)
                if candidate.snapshot() != snapshot:
                    raise ValueError('M3 reads refreshed or changed state: ' + label)
                receipts.append(dict(changed=changed, snapshot=snapshot, wire_snapshot=wire_snapshot,
                    queries=queries, counts=dict(cells=len(candidate._cells), states=len(candidate._log_odds),
                                                identities=candidate.retained_identity_count)))
            probes = []
            for probe in case.get('probes', []):
                before = _state(candidate)
                try:
                    changed = candidate.update(probe['observation'])
                    outcome, reason = 'fused' if changed else 'not_fused', ''
                except ValueError as exc:
                    outcome, reason = 'rejected', str(exc)
                if outcome != probe['outcome'] or _state(candidate) != before:
                    raise ValueError('M3 probe changed state or differed from expected outcome')
                probes.append(dict(outcome=outcome, reason=reason, state_unchanged=True))
            outputs.append(dict(name=case['name'], receipts=receipts, probes=probes))
        report.update(passed=True, scenario_count=len(outputs),
            observation_count=sum(len(case['receipts']) for case in outputs),
            query_count=sum(len(row['queries']) for case in outputs for row in case['receipts']),
            probe_count=sum(len(case['probes']) for case in outputs), nominal_exactly_matches_m2=True,
            query_statuses=sorted({query['result']['status'] for case in outputs
                                   for row in case['receipts'] for query in row['queries']}))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
    for name, value in (('results.json', outputs), ('report.json', report)):
        with (run / name).open('x') as handle:
            json.dump(value, handle, indent=2)
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
