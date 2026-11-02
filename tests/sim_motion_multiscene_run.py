"""Freeze SW-04A independent expectations before production validation or genpy."""
import argparse
from datetime import datetime
import io
import json
from pathlib import Path
import subprocess
import sys

from sim_motion_fixture import ROOT
from sim_motion_multiscene_fixture import expected, expected_wire, layout, source_cases, wire_cases


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def freeze():
    run = ROOT / '.runtime/runs' / ('sim-motion-sw04a-' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True)
    literals = expected()
    save(run / 'independent-expectations.json', literals)
    save(run / 'suite.json', json.loads((ROOT / 'configs/sim_motion_multiscene_fixture.json').read_text()))
    save(run / 'base-profile.json', json.loads((ROOT / 'configs/sim_scene_motion_fixture.json').read_text()))
    formats = layout()
    save(run / 'wire-layout.json', formats)
    rows = wire_cases(literals)
    save(run / 'wire-inputs.json', rows)
    save(run / 'source-inputs.json', source_cases(literals))
    for index, row in enumerate(rows):
        with (run / ('expected-%03d.bin' % index)).open('xb') as stream:
            stream.write(expected_wire(row, formats))
    paths = []
    for package in ('uav_fusionmap_msgs', 'uav_fusionmap_sim_scene_msgs', 'uav_fusionmap_terrain_msgs'):
        for directory, suffix in (('msg', '*.msg'), ('srv', '*.srv')):
            paths.extend(sorted((ROOT / 'ros_ws/src' / package / directory).glob(suffix)))
    save(run / 'old-definitions.json', {str(p.relative_to(ROOT)): p.read_text() for p in paths})
    entries = ['configs/sim_scene_motion_fixture.json', 'configs/sensor_scene.yaml',
        'ros_ws/sim_motion_gate_run.py', 'ros_ws/sim_motion_delivery.py', 'ros_ws/sim_motion_delivery_run.py',
        'simulation/ufm_simulation/scene_motion.py', 'simulation/ufm_simulation/scene_motion_world.py']
    save(run / 'old-entrypoints.json', {name: (ROOT / name).read_text() for name in entries})
    save(run / 'git-state.json', dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).splitlines()))
    return run


def verify(run, full=False):
    if (any(run.glob('actual-*.bin')) or any(run.glob('public-empty-*.bin')) or
            any((run/name).exists() for name in ('verification-started.json','report.json','targeted.log','full.log'))):
        raise ValueError('verification evidence already exists; create a new run')
    save(run/'verification-started.json',dict(python=sys.executable,phase='verify_after_freeze'))
    from ufm_scene_contract.codec import deserialize, from_ros, to_ros
    from ufm_simulation.motion_suite import case_spec, load_suite, validate_geometry
    from sim_motion_multiscene_checks import verify_empty_semantics, verify_sources
    from sim_motion_multiscene_oracle import verify_literals
    literals = json.loads((run/'independent-expectations.json').read_text())
    suite = load_suite(run/'suite.json',base_profile_path=run/'base-profile.json')
    if suite != json.loads((ROOT/'configs/sim_motion_multiscene_fixture.json').read_text()):
        raise ValueError('live suite differs from frozen input')
    verify_literals(literals)
    for row in literals['cases']:
        spec = case_spec(suite,row['case_id'])
        if (spec['ic_degrees'] != row['ic_degrees'] or spec['geometry_id'] != row['geometry_id'] or
                spec['geometry'] != literals['geometry'][row['geometry_id']]):
            raise ValueError('suite differs from independent geometry/IC')
        validate_geometry(row['geometry_id'],spec['geometry'])
        if row['case_id'] != 'S01' and spec['map_settings'] != literals['wide_map']:
            raise ValueError('suite differs from independent map')
    rows = json.loads((run/'wire-inputs.json').read_text())
    source_rows = json.loads((run/'source-inputs.json').read_text())
    if rows != wire_cases(literals) or source_rows != source_cases(literals):
        raise ValueError('frozen inputs missing, reordered or differ from independent probes')
    sources = verify_sources(source_rows,literals,
        json.loads((run/'base-profile.json').read_text()))
    save(run/'source-validation.json',sources)
    wire = []
    generated_types = {}
    for index,row in enumerate(rows):
        message = to_ros(row['kind'],row['value'])
        generated_types[row['kind']] = dict(python_module=type(message).__module__,
            file=sys.modules[type(message).__module__].__file__,ros_type=message._type)
        stream = io.BytesIO(); message.serialize(stream)
        raw = stream.getvalue()
        if (raw != (run/('expected-%03d.bin'%index)).read_bytes() or
                deserialize(row['kind'],raw) != row['value'] or
                from_ros(row['kind'],type(message)().deserialize(raw)) != row['value']):
            raise ValueError('saved wire differs: '+row['id'])
        with (run/('actual-%03d.bin'%index)).open('xb') as output:output.write(raw)
        wire.append(dict(id=row['id'],kind=row['kind'],bytes=len(raw)))
    public = verify_empty_semantics(literals,run=run)
    save(run/'public-empty-validation.json',public)
    results = []
    for name,pattern in [('targeted','test_sim_motion*.py')] + ([('full','test_*.py')] if full else []):
        result = subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p',pattern,'-v'],
            cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180.)
        with (run/(name+'.log')).open('x') as output:output.write(result.stdout)
        results.append(dict(name=name,returncode=result.returncode))
        print(name+':\n'+'\n'.join(result.stdout.strip().splitlines()[-5:]),flush=True)
    unchanged = {}
    for filename in ('old-definitions.json','old-entrypoints.json'):
        snapshot = json.loads((run/filename).read_text())
        if any((ROOT/name).read_text() != value for name,value in snapshot.items()):
            raise ValueError('existing definition or entrypoint changed')
        unchanged[filename] = len(snapshot)
    report = dict(python=sys.executable,core_cases=9,planned_compatibility_cases=3,
        wire=wire,generated_types=generated_types,public_wire=public['wire'],synthetic_source_probes=len(sources),
        old_files_unchanged=unchanged,results=results,
        new_fdm_trajectory_executed=False,ros_or_gazebo_started=False,
        passed=all(r['returncode']==0 for r in results))
    save(run/'report.json',report)
    return report['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-only', action='store_true')
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if args.freeze_only and (args.verify or args.full):
        parser.error('freeze and verify are separate phases')
    run = args.verify.resolve() if args.verify else freeze()
    print(run, flush=True)
    return 0 if args.freeze_only else int(not verify(run, args.full))


if __name__ == '__main__':
    sys.exit(main())
