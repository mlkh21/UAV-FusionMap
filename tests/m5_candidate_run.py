"""Verify the private M5 candidate against existing SW-01 receipts, without rebuilding inputs."""
import argparse
import copy
import datetime
from fractions import Fraction
import json
import math
from pathlib import Path
import sys

from ufm_mapping.m5_contract import load_fixture
from ufm_mapping.terrain_fixture import TerrainFixture
from ufm_mapping.terrain_replay import replay_terrain


def save(path,value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def read(path):
    return json.loads(path.read_text())


def execute(saved):
    spec = load_fixture(saved/'config.json')
    expected,events,inputs,requests = [read(saved/name) for name in
        ('expectations.json','future-events.json','inputs.json','requests.json')]
    report,checks = {},[]
    if len(expected['samples']) != 4 or len(events) != 7 or len(inputs) != 45 or len(requests) != 5:
        raise ValueError('M5 saved SW-01 acceptance set is incomplete')

    def check(name,condition):
        if not condition:raise ValueError('M5 saved expectation mismatch: ' + name)
        checks.append(name)

    registration = spec['registration']
    layer = TerrainFixture(spec,registration['run_id'],registration['clock_id'])
    start = spec['eligibility']['valid_interval_ns'][0]
    layer.observe_clock(start)
    layer.install(spec,start)
    samples = []
    for sample in expected['samples']:
        request = dict(requests[1],point_xy=sample['map_xy'])
        result = layer.query(request)
        check('sample source index '+str(sample['source_xy']),result['source_index']==[sample['row'],sample['column']])
        check('sample source XY '+str(sample['source_xy']),result['source_xy']==sample['source_xy'])
        check('sample height '+str(sample['source_xy']),result['height']==sample['map_height'])
        if sample['map_height'] is None:
            check('no-data preserved',result['status']=='unknown' and result['reason']=='no_data' and
                  result['height_quality']['status']=='unavailable')
        else:
            check('sample status valid '+str(sample['source_xy']),result['status']=='valid')
            bounds = result['height_quality']['value']
            check('outward interval '+str(sample['source_xy']),
                all(math.isclose(a,b,rel_tol=0.,abs_tol=1e-12) for a,b in zip(bounds,sample['map_height_interval'])) and
                Fraction.from_float(bounds[0]) <= Fraction(str(sample['map_height_interval'][0])) and
                Fraction.from_float(bounds[1]) >= Fraction(str(sample['map_height_interval'][1])))
        samples.append(result)
    query_results = []
    for request,status in zip(requests,expected['groups'][7]['expected_status']):
        result = layer.query(request)
        check('time boundary '+str(request['query_timestamp']),result['status']==status)
        if status == 'unavailable':check('no unavailable payload '+str(request['query_timestamp']),result['height'] is None)
        else:
            check('source time unchanged '+str(request['query_timestamp']),result['source_time']==spec['source_time'])
            check('install time unchanged '+str(request['query_timestamp']),result['installed_timestamp']==start)
        query_results.append(result)
    # Run the saved version/expiry/reset sequence twice; do not call fixture builders or an oracle.
    replay = replay_terrain(spec,events)
    check('deterministic private replay',replay==replay_terrain(spec,copy.deepcopy(events)))
    for event,row in zip(events,replay['receipts']):
        operation = event['operation']
        outcome = ('installed' if operation=='install' else 'idempotent' if operation=='install_identical'
                   else 'unavailable' if operation=='clock_reset' else event['expected'])
        check('saved event '+str(event['sequence']),row['outcome']==outcome)
        if 'expected_revision' in event:
            check('saved revision '+str(event['sequence']),row['terrain_revision']==event['expected_revision'])
    input_results = []
    for case in inputs:
        # Fresh candidate per input: static admission is independent from historical version conflicts.
        candidate = None
        reason = ''
        try:
            candidate = TerrainFixture(spec,registration['run_id'],registration['clock_id'])
            # Missing registration quality is a supported binding of its own fixture instance.
            if case['accepts']:candidate = TerrainFixture(case['spec'],registration['run_id'],registration['clock_id'])
            candidate.observe_clock(start)
            candidate.install(case['spec'],start)
            accepted = True
        except ValueError as exc:
            accepted,reason = False,str(exc)
        check('candidate admission '+case['name'],accepted==case['accepts'])
        if accepted:
            query = candidate.query(requests[1])
            if case['name']=='T3_zero_height':check('zero input maps to offset',query['height']==3. and query['status']=='valid')
            if case['name'].startswith('T15_missing_'):
                check('missing quality '+case['name'],query['height']==13. and
                      query['height_quality']['status']=='unavailable' and query['height_quality']['value'] is None)
        else:
            check('refused candidate stays empty '+case['name'],candidate.snapshot()['terrain_revision']==0)
        input_results.append(dict(name=case['name'],accepted=accepted,reason=reason))
    report.update(passed=True,checks=checks,check_count=len(checks),samples=samples,query_results=query_results,
                  replay=replay,input_results=input_results)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-run',required=True,type=Path)
    parser.add_argument('--output-root',type=Path,default=Path(__file__).resolve().parents[1]/'.runtime/runs')
    args = parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%dT%H%M%S%f')
    run = args.output_root.resolve()/('m5-candidate-'+stamp)
    run.mkdir(parents=True,exist_ok=False)
    report = dict(run=str(run),fixture_run=str(args.fixture_run.resolve()),python=sys.executable,
                  passed=False,errors=[],terrain_layer_executed=True,occupancy_updated=False,
                  ros_master_started=False,real_dem_loaded=False)
    try:
        source_report = read(args.fixture_run/'report.json')
        if not source_report['passed'] or source_report['terrain_layer_executed']:
            raise ValueError('M5 requires a passed SW-01 input/expectation run')
        result = execute(args.fixture_run)
        save(run/'candidate-results.json',result)
        report.update(passed=result['passed'],check_count=result['check_count'],
                      samples=len(result['samples']),boundary_queries=len(result['query_results']),
                      replay_events=len(result['replay']['receipts']),input_cases=len(result['input_results']))
    except Exception as exc:
        report['errors'].append(type(exc).__name__+': '+str(exc))
    save(run/'report.json',report)
    print(json.dumps(report))
    return int(not report['passed'])


if __name__=='__main__':
    sys.exit(main())
