"""Offline M2-SW-03 H-K receipts, independent expected states and bounded-state checks."""
import datetime
import json
import math
from pathlib import Path
import sys

from m2_fixture import load_spec
from m2_motion_fixture import motion_observation
from m2_rolling_scenarios import scenarios
from ufm_mapping.rolling_probability_map import RollingProbabilityMap
from ufm_ros_contract.perf01a_codec import (from_ros_occupancy, from_ros_snapshot,
                                         to_ros_occupancy, to_ros_snapshot)
from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result


def main():
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    run_id = 'm2-rolling-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, errors=[], run_id=run_id, python=sys.executable,
        scope='offline synthetic M2 rolling/time/state checks; no ROS runtime or real inputs')
    results, source = [], []
    try:
        spec = load_spec()
        with (run / 'config.json').open('x') as handle:
            json.dump(spec, handle, indent=2)
        source = scenarios(spec, run_id)
        for case in source:
            header = case['steps'][0]['observation']['header']
            local_map = RollingProbabilityMap(spec, header['run_id'], header['clock_id'])
            receipts = []
            for index, step in enumerate(case['steps']):
                row, expected = step['observation'], step['expected']
                decoded = from_ros_occupancy(to_ros_occupancy(row))
                changed = local_map.update(decoded)
                request = dict(map_id=spec['map_id'], frame_id='odom', run_id=header['run_id'],
                    clock_id=header['clock_id'], query_timestamp=row['header']['timestamp'],
                    max_age_ns=999_000_000, point=step['query_point'])
                response = local_map.query(**request)
                snapshot = local_map.snapshot()
                for key in ('status', 'observed', 'last_observed_timestamp', 'revision'):
                    if response[key] != expected[key]:
                        raise ValueError('%s:%d query %s differs' % (case['name'], index, key))
                if expected['probability'] is None:
                    if response['probability'] is not None:
                        raise ValueError('unknown/unavailable invented probability')
                elif not math.isclose(response['probability'], expected['probability'], rel_tol=0., abs_tol=1e-12):
                    raise ValueError('rolling result differs from independent probability expectation')
                if (snapshot['origin'] != expected['origin'] or
                        snapshot['header']['timestamp'] != expected['map_timestamp'] or
                        snapshot['revision'] != expected['revision']):
                    raise ValueError('rolling origin, revision or evidence time differs')
                wire = from_ros_query_result(to_ros_query_result(response))
                wire_snapshot = from_ros_snapshot(to_ros_snapshot(snapshot))
                if wire['status'] != expected['status'] or wire_snapshot['revision'] != expected['revision']:
                    raise ValueError('rolling public message round trip differs')
                receipts.append(dict(changed=changed, query=response, snapshot=snapshot))
            results.append(dict(name=case['name'], receipts=receipts))

        bounded_spec = dict(spec, max_active_cells=2, identity_history_limit=3)
        local_map = RollingProbabilityMap(bounded_spec, run_id + ':bounded', 'sim:' + run_id + ':bounded')
        counts, bounded_observations = [], []
        for index in range(40):
            row = motion_observation(bounded_spec, run_id + ':bounded', index,
                                     points=((8.25 + index % 3, .25, .25),))
            bounded_observations.append(row)
            local_map.update(row)
            counts.append(dict(step=index, cells=len(local_map.snapshot()['cells']),
                               identities=local_map.retained_identity_count, log_odds=len(local_map._log_odds)))
        if any(row['cells'] > 2 or row['identities'] > 3 or row['log_odds'] > 2 for row in counts):
            raise ValueError('bounded candidate exceeded configured structure limits')
        results.append(dict(name='bounded_40_steps', config=bounded_spec,
                            observations=bounded_observations, counts=counts,
                            final_snapshot=local_map.snapshot()))
        report.update(passed=True, motion_scenario_count=len(source),
                      motion_observation_count=sum(len(case['steps']) for case in source),
                      bounded_observation_count=40)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
    for name, value in (('fixtures.json', source), ('results.json', results), ('report.json', report)):
        with (run / name).open('x') as handle:
            json.dump(value, handle, indent=2)
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
