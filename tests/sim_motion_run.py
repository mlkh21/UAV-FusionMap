"""Freeze independent inputs/bytes first, then verify actual generated messages offline."""
import argparse
from datetime import datetime
import io
import json
from pathlib import Path
import subprocess
import sys

from sim_motion_fixture import ROOT, cases, expected, independent_bytes, source_sample, verify_analytic, wire_object


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def freeze():
    run = ROOT / '.runtime/runs' / ('sim-motion-sw01-' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True)
    literals = expected()
    save(run / 'independent-expectations.json', literals)
    save(run / 'profile.json', json.loads((ROOT / 'configs/sim_scene_motion_fixture.json').read_text()))
    save(run / 'wire-inputs.json', cases())
    save(run / 'source-inputs.json', [source_sample(i) for i in (0, 1, 25, 250)])
    verify_analytic(literals)
    for index, row in enumerate(json.loads((run / 'wire-inputs.json').read_text())):
        (run / ('expected-%02d.bin' % index)).write_bytes(independent_bytes(
            row['kind'], wire_object(row['kind'], row['value'], literals['layout']), literals['layout']))
    paths = sorted((ROOT / 'ros_ws/src/uav_fusionmap_msgs').glob('msg/*.msg'))
    paths += sorted((ROOT / 'ros_ws/src/uav_fusionmap_msgs').glob('srv/*.srv'))
    save(run / 'old-public-definitions.json', {str(p.relative_to(ROOT)): p.read_text() for p in paths})
    save(run / 'git-state.json', dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).splitlines()))
    return run


def verify(run, full):
    if any(run.glob('actual-*.bin')) or any((run / name).exists() for name in ('targeted.log', 'full.log', 'report.json')):
        raise ValueError('verification evidence already exists; create a new run')
    from ufm_scene_contract.codec import deserialize, from_ros, to_ros
    from ufm_scene_contract.profile import load_json, validate_profile, validate_source_sample
    profile = load_json(run / 'profile.json')
    validate_profile(profile)
    for row in load_json(run / 'source-inputs.json'):
        validate_source_sample(row, profile)
    rows = load_json(run / 'wire-inputs.json')
    wire = []
    for index, row in enumerate(rows):
        cls_message = to_ros(row['kind'], row['value'])
        stream = io.BytesIO()
        cls_message.serialize(stream)
        raw = stream.getvalue()
        if (raw != (run / ('expected-%02d.bin' % index)).read_bytes() or
                deserialize(row['kind'], raw) != row['value'] or
                from_ros(row['kind'], type(cls_message)().deserialize(raw)) != row['value']):
            raise ValueError('saved wire differs: ' + row['id'])
        with (run / ('actual-%02d.bin' % index)).open('xb') as stream:
            stream.write(raw)
        wire.append(dict(id=row['id'], kind=row['kind'], bytes=len(raw)))
    old = load_json(run / 'old-public-definitions.json')
    if any((ROOT / path).read_text() != value for path, value in old.items()):
        raise ValueError('old public definitions changed')
    report = dict(python=sys.executable, wire=wire, old_definitions_unchanged=len(old),
        coordinate_converter_executed=False, simulator_or_ros_started=False, results=[])
    for name, pattern in [('targeted', 'test_sim_motion*.py')] + ([('full', 'test_*.py')] if full else []):
        result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v'],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180.)
        with (run / (name + '.log')).open('x') as stream:
            stream.write(result.stdout)
        report['results'].append(dict(name=name, returncode=result.returncode))
        print(name + ':\n' + '\n'.join(result.stdout.strip().splitlines()[-5:]), flush=True)
    report['passed'] = all(r['returncode'] == 0 for r in report['results'])
    save(run / 'report.json', report)
    return report['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-only', action='store_true')
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if args.freeze_only and args.verify:
        parser.error('freeze and verify are distinct phases')
    run = args.verify.resolve() if args.verify else freeze()
    print(run, flush=True)
    return 0 if args.freeze_only else int(not verify(run, args.full))


if __name__ == '__main__':
    sys.exit(main())
