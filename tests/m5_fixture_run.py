"""Freeze private M5 inputs and independent expectations; never execute a terrain layer."""
import argparse
import copy
import datetime
import json
from pathlib import Path
import sys

from m5_fixture import CONFIG, future_events, input_cases, load_spec, query_request
from m5_oracle import EXPECTED_FILE, load_expected
from ufm_mapping.m5_contract import load_fixture, validate_request


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, default=CONFIG.parent.parent / '.runtime/runs')
    args = parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%dT%H%M%S%f')
    run = args.output_root.resolve() / ('m5-fixture-' + stamp)
    run.mkdir(parents=True, exist_ok=False)
    report = dict(run=str(run), passed=False, python=sys.executable, errors=[],
        terrain_layer_executed=False, occupancy_updated=False, ros_master_started=False,
        real_dem_loaded=False, scope='M5-SW-01 private contract, input checks and independent expectations')
    try:
        spec, expected = load_spec(), load_expected()
        save(run / 'config.json', spec)
        # Preserve the independent table before checking inputs. Candidate results never generate it.
        with (run / 'expectations.json').open('xb') as stream:
            stream.write(EXPECTED_FILE.read_bytes())
        cases = input_cases(spec)
        save(run / 'inputs.json', cases)
        save(run / 'future-events.json', future_events(spec,expected))
        frozen = json.loads((run / 'inputs.json').read_text())
        checks = []
        for case in frozen:
            path = run / (case['name'] + '.json')
            save(path, case['spec'])
            before, error = copy.deepcopy(case['spec']), ''
            try:
                decoded = load_fixture(path)
                if decoded != before:raise RuntimeError('JSON fixture payload changed')
                accepted = True
            except ValueError as exc:
                accepted, error = False, str(exc)
            if accepted != case['accepts']:raise RuntimeError('input expectation mismatch: ' + case['name'])
            checks.append(dict(name=case['name'], accepted=accepted, expected=case['accepts'], reason=error))
        requests = [query_request(spec, timestamp) for timestamp in expected['groups'][7]['times_ns']]
        for request in requests:
            validate_request(spec,request)
        save(run / 'requests.json', requests)
        report.update(passed=True, input_cases=len(checks), accepted=sum(c['accepted'] for c in checks),
            rejected=sum(not c['accepted'] for c in checks), checks=checks,
            saved_expected_groups=len(expected['groups']), future_events=len(expected['future_events']),
            syntax_valid_requests=len(requests), pending='terrain query statuses, versions, atomicity and quality propagation')
    except Exception as exc:
        report['errors'].append(type(exc).__name__ + ': ' + str(exc))
    save(run / 'report.json', report)
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
