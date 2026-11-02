"""Emit validated M2-SW-01 inputs and independent expectations; never run an accumulator."""
import argparse
import datetime
import json
from pathlib import Path
import sys

from m2_fixture import CONFIG, SCENARIOS, load_spec, observation
from m2_oracle import expected_sequence
from ufm_mapping.m2_contract import validate_fixture_observation
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, to_ros_occupancy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=CONFIG)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    run_id = 'm2-fixture-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = root / '.runtime/runs' / run_id
    run.mkdir(parents=True, exist_ok=False)
    report = dict(run_id=run_id, passed=False, errors=[], python=sys.executable,
        scope='M2-SW-01 fixture contract and independent arithmetic oracle only',
        map_accumulation_executed=False, source_config=str(args.config.resolve()))
    try:
        spec = load_spec(args.config)
        with (run / 'config.json').open('x') as handle:
            json.dump(spec, handle, indent=2)
        cases = []
        for name, kinds in SCENARIOS.items():
            rows = [observation(spec, run_id + ':' + name, index, kind)
                    for index, kind in enumerate(kinds)]
            for row in rows:
                validate_fixture_observation(row, spec)
                if from_ros_occupancy(to_ros_occupancy(row)) != row:
                    raise ValueError('fixture ROS round trip differs: ' + name)
            cases.append(dict(name=name, steps=list(kinds), observations=rows,
                              expectations=expected_sequence(kinds, spec)))
        with (run / 'fixtures.json').open('x') as handle:
            json.dump(cases, handle, indent=2)
        report.update(passed=True, scenario_count=len(cases),
                      observation_count=sum(len(case['observations']) for case in cases))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
    with (run / 'report.json').open('x') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
