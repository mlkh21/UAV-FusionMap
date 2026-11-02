"""Freeze/replay independent M4 time schedules, rollback checks and logical resource census."""
import argparse
import datetime
import json
from pathlib import Path
import sys

from m4_resource_audit import assert_retained
from m4_scene_run import run_cases
from m4_time_validation import atomic_probes, census_probes, domain_probes
from ufm_mapping.scene_map import SceneMap


def resources(case):
    spec=case['spec']
    registration=spec['registration']
    scene=SceneMap(spec,registration['run_id'],registration['clock_id'])
    maximum_voxels=max(len(item['observation']['voxels']) for item in case['steps'])
    maximum={}
    for item in case['steps']:
        try:scene.update(item['observation'])
        except (ValueError,KeyError,TypeError):pass
        counts=assert_retained(scene,maximum_voxels)
        for key,value in counts.items():maximum[key]=max(maximum.get(key,0),value)
    return dict(name=case['name'],retained_maxima=maximum,
        n=spec['local_map']['arithmetic']['max_active_cells'],
        h=spec['local_map']['arithmetic']['identity_history_limit'],
        k=spec['max_sealed_submaps'],max_input_voxels=maximum_voxels)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path)
    parser.add_argument('--output-root',type=Path,default=Path(__file__).resolve().parents[1]/'.runtime/runs')
    args=parser.parse_args(argv)
    if sys.executable!='/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    run=args.output_root/('m4-time-'+now.strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True,exist_ok=False)
    report=dict(passed=False,errors=[],python=sys.executable,ros_master_started=False,
        scope='offline fixed synthetic registration; logical item census, not RSS or PERF-01',
        source=None if args.input is None else str(args.input.resolve()))
    try:
        if args.input:
            frozen=json.loads(args.input.read_text())
        else:
            from m4_fixture import load_spec
            from m4_time_scenarios import frozen_cases,periodic_fixture
            spec=load_spec()
            frozen=dict(spec=spec,cases=frozen_cases(spec)+[periodic_fixture(spec)])
        if not isinstance(frozen,dict) or not isinstance(frozen.get('cases'),list) or not frozen['cases']:
            raise ValueError('saved time fixture must contain nonempty cases')
        # Save before candidate execution. Replay never calls the scenario/oracle generators.
        (run/'fixtures.json').write_text(json.dumps(frozen,indent=2))
        results=run_cases(frozen['cases'])
        retained=[resources(case) for case in frozen['cases']]
        atomic=atomic_probes(frozen['spec'])
        domain=domain_probes(frozen['spec'])
        census=census_probes(frozen['spec'])
        if args.input and 'm4_oracle' in sys.modules:
            raise RuntimeError('saved time replay unexpectedly imported the oracle')
        (run/'results.json').write_text(json.dumps(results,indent=2))
        (run/'resource-audit.json').write_text(json.dumps(dict(retained=retained,census=census),indent=2))
        (run/'probes.json').write_text(json.dumps(dict(atomic=atomic,domain=domain),indent=2))
        report.update(passed=True,scenario_count=len(results),
            observation_count=sum(len(c['steps']) for c in results),
            query_count=sum(len(s['queries']) for c in results for s in c['steps']),
            atomic_probe_count=len(atomic),domain_probe_count=1,
            saved_expectations_recomputed=False,
            statuses=sorted({q['result']['status'] for c in results for s in c['steps'] for q in s['queries']}))
    except (ValueError,KeyError,TypeError,OSError,RuntimeError,AssertionError) as exc:
        report['errors'].append(type(exc).__name__+':'+str(exc))
    (run/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(run=str(run),passed=report['passed'],errors=report['errors'])))
    return int(not report['passed'])


if __name__=='__main__':
    sys.exit(main())
