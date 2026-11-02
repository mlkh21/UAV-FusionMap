"""Save independent M5 time expectations before running candidate/resource checks."""
import argparse
import datetime
import json
from pathlib import Path
import sys


def save(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def read(path):
    return json.loads(path.read_text())


def execute(saved):
    from m5_time_validation import execute_case, resource_probe
    from ufm_mapping.factory import create_map
    from test_local_map_query import observation
    inputs = read(saved/'inputs.json')
    cases = inputs['cases']
    if len(cases) != 4 or [len(c['events']) for c in cases] != [64,11,5,4]:
        raise ValueError('M5 frozen combination acceptance set incomplete')
    occupancy = create_map()
    occupancy.update(observation())
    before = occupancy.snapshot()
    results = [dict(name=c['name'],result=execute_case(c)) for c in cases]
    resources = resource_probe(inputs['resource_spec'])
    if occupancy.snapshot() != before:
        raise AssertionError('terrain sequence/resources mutated existing occupancy snapshot')
    return dict(passed=True,cases=results,resources=resources,occupancy_snapshot_unchanged=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,help='replay saved inputs; do not rebuild expectations')
    parser.add_argument('--output-root',type=Path,default=Path(__file__).resolve().parents[1]/'.runtime/runs')
    args = parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%dT%H%M%S%f')
    run = args.output_root.resolve()/('m5-time-'+stamp)
    run.mkdir(parents=True,exist_ok=False)
    report = dict(run=str(run),python=sys.executable,passed=False,errors=[],
                  occupancy_updated=False,ros_master_started=False,real_dem_loaded=False,rss_measured=False)
    try:
        if args.input:
            inputs = read(args.input/'inputs.json')
        else:
            from m5_fixture import load_spec
            from m5_time_scenarios import scenarios, capacity_spec
            spec = load_spec()
            inputs = dict(cases=scenarios(spec),resource_spec=capacity_spec(spec))
        save(run/'inputs.json',inputs)
        # Re-read the frozen declarations; candidate results cannot change them.
        result = execute(run)
        save(run/'results.json',result)
        report.update(passed=True,sequence_cases=len(result['cases']),
            occupancy_snapshot_unchanged=result['occupancy_snapshot_unchanged'],
            replay_events=sum(len(c['result']['receipts']) for c in result['cases']),
            resource_versions=result['resources']['successful_versions'],
            fault_sites=len(result['resources']['fault_sites']),
            retained=result['resources']['retained'],census=result['resources']['census'])
    except Exception as exc:
        report['errors'].append(type(exc).__name__+': '+str(exc))
    save(run/'report.json',report)
    print(json.dumps(report))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
