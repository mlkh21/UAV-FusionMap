"""Freeze validated M3 inputs and independent rational expectations; no map execution."""
import argparse
import datetime
import io
import json
from pathlib import Path
import sys

from m3_fixture import CONFIG, interval_quality, load_spec, observation, scenarios
from m3_oracle import expected_sequence
from ufm_mapping.m3_contract import (validate_fixture_observation, validate_interval_quality,
                                     wire_probability)
from ufm_ros_contract.perf01a_codec import from_ros_occupancy, to_ros_occupancy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--output-root', type=Path,
                        default=Path(__file__).resolve().parents[1] / '.runtime/runs')
    args = parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run_id = 'm3-fixture-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')
    run = args.output_root.resolve() / run_id
    run.mkdir(parents=True, exist_ok=False)
    report = dict(run_id=run_id, passed=False, errors=[], python=sys.executable,
        source_config=str(args.config.resolve()), map_accumulation_executed=False,
        scope='M3-SW-01 fixture contract and independent expectations; no accumulator or ROS runtime')
    try:
        spec = load_spec(args.config)
        with (run / 'config.json').open('x') as handle:
            json.dump(spec, handle, indent=2)
        cases = []
        for name, events in scenarios(spec).items():
            rows = []
            for index, event in enumerate(events):
                row = observation(spec, run_id + ':' + name, index, event)
                validate_fixture_observation(row, spec)
                message, buffer = to_ros_occupancy(row), io.BytesIO()
                message.serialize(buffer)
                decoded = from_ros_occupancy(type(message)().deserialize(buffer.getvalue()))
                validate_fixture_observation(decoded, spec)
                if decoded != row:
                    raise ValueError('M3 actual ROS serialization round trip differs: ' + name)
                rows.append(decoded)
            expectations = expected_sequence(events, spec['arithmetic'])
            for expected in expectations:
                if expected['observed']:
                    quality = interval_quality(spec, expected['interval'], output=True)
                    validate_interval_quality(expected['probability'], quality, spec, output=True)
                    validate_interval_quality(wire_probability(expected['probability']), quality,
                                              spec, output=True, wire=True)
            cases.append(dict(name=name, events=events, observations=rows, expectations=expectations))
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
