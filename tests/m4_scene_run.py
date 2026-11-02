"""Replay saved M4-SW-01 inputs/answers through the explicit candidate; never import the oracle."""
import argparse
import copy
import datetime
from fractions import Fraction
import io
import json
import math
from pathlib import Path
import struct
import sys

from ufm_mapping.scene_map import SceneMap
from ufm_ros_contract.perf01a_codec import to_ros_snapshot, from_ros_snapshot
from ufm_ros_contract.query_codec import to_ros_query_result, from_ros_query_result


def compare(actual, expected):
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(compare(actual[k], expected[k]) for k in actual)
    if isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
        return len(actual) == len(expected) and all(compare(a, b) for a, b in zip(actual, expected))
    if isinstance(actual, float) and isinstance(expected, float):
        return math.isclose(actual, expected, rel_tol=0., abs_tol=1e-12)
    return type(actual) is type(expected) and actual == expected


def wire(value, encode, decode):
    message, stream = encode(value), io.BytesIO()
    message.serialize(stream)
    return decode(type(message)().deserialize(stream.getvalue()))


def expected_wire(value):
    result = copy.deepcopy(value)
    if 'uncertainty' in result and result['uncertainty'] is None:
        result['uncertainty'] = dict(status='unavailable', kind='', value=None, unit='', source='')
    for cell in result.get('cells', [result]):
        for key in ('probability', 'confidence'):
            if key in cell and cell[key] is not None:
                cell[key] = struct.unpack('!f', struct.pack('!f', cell[key]))[0]
    return result


def check_ownership(candidate, case, expected):
    # Test-only private audit; application never consumes the directory.
    def index(name):
        scene, registration = case['spec']['scene'], case['spec']['registration']
        return tuple(int((Fraction(str(p)) + Fraction(str(registration['T_map_odom'][4*i+3])) -
                          Fraction(str(scene['origin'][i]))) // Fraction(str(scene['resolution'][i])))
                     for i, p in enumerate(case['versions'][name]['point']))
    state = candidate._state
    actual = dict(active=sorted(state.active), sealed=[sorted(g['cells']) for g in state.sealed.values()])
    target = dict(active=sorted(index(name) for name in expected['active']),
                  sealed=[sorted(index(name) for name in group) for group in expected['sealed']])
    return actual == target


def run_cases(cases):
    results = []
    for case in cases:
        spec = case['spec']
        registration = spec['registration']
        candidate = SceneMap(spec, registration['run_id'], registration['clock_id'])
        steps = []
        for number, item in enumerate(case['steps']):
            label = '%s step %d' % (case['name'], number)
            before = candidate.snapshot()
            reason = ''
            try:
                changed = candidate.update(item['observation'])
                outcome = 'fused' if changed else 'not_fused'
            except (ValueError, KeyError, TypeError) as exc:
                outcome, reason = 'rejected', type(exc).__name__ + ':' + str(exc)
            expected = item['expected']
            snapshot = candidate.snapshot()
            if outcome != item['declaration']['outcome']:
                raise ValueError(label + ' outcome differs: ' + outcome + ' ' + reason)
            if outcome != 'fused' and before != snapshot:
                raise ValueError(label + ' refused input changed public snapshot')
            if not compare(snapshot, expected['snapshot']):
                raise ValueError(label + ' snapshot differs from frozen answer')
            if not check_ownership(candidate, case, expected['ownership']):
                raise ValueError(label + ' ownership/FIFO differs from frozen answer')
            if candidate._state.structure_timestamp != expected['structure_timestamp']:
                raise ValueError(label + ' structure time differs from frozen answer')
            encoded = wire(snapshot, to_ros_snapshot, from_ros_snapshot)
            if not compare(encoded, expected_wire(expected['snapshot'])):
                raise ValueError(label + ' serialized snapshot differs from frozen answer')
            queries = []
            for query in expected['queries']:
                result = candidate.query(**query['request'])
                if not compare(result, query['result']):
                    raise ValueError(label + ' query differs from frozen answer: ' + str(result))
                decoded = wire(result, to_ros_query_result, from_ros_query_result)
                if not compare(decoded, expected_wire(query['result'])):
                    raise ValueError(label + ' serialized query differs from frozen answer')
                queries.append(dict(request=query['request'], result=result))
            if snapshot != candidate.snapshot():
                raise ValueError(label + ' queries changed map')
            steps.append(dict(outcome=outcome, reason=reason, snapshot=snapshot, queries=queries))
        results.append(dict(name=case['name'], steps=steps))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, default=Path(__file__).resolve().parents[1]/'.runtime/runs')
    args = parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    run = args.output_root / ('m4-scene-' + now.strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, errors=[], python=sys.executable, source=str(args.input.resolve()),
        scene_map_executed=True, ros_master_started=False,
        scope='fixed synthetic registration Scene candidate and saved independent answers only')
    try:
        cases = json.loads(args.input.read_text())
        if not isinstance(cases, list) or not cases:
            raise ValueError('saved M4 cases must be a nonempty list')
        (run/'fixtures.json').write_text(json.dumps(cases, indent=2))
        result = run_cases(cases)
        if any(name in sys.modules for name in ('m4_oracle', 'm4_fixture', 'm3_oracle')):
            raise RuntimeError('saved replay unexpectedly imported oracle/fixture builder')
        (run/'results.json').write_text(json.dumps(result, indent=2))
        report.update(passed=True, scenario_count=len(result),
            observation_count=sum(len(c['steps']) for c in result),
            query_count=sum(len(s['queries']) for c in result for s in c['steps']),
            statuses=sorted({q['result']['status'] for c in result for s in c['steps'] for q in s['queries']}))
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
    (run/'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
