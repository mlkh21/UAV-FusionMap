"""Freeze independent inputs/bytes first; later verify real genpy and unchanged v1."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from sim_flight_v2_fixture import ROOT, cases, expected, packed
from sim_motion_fixture import cases as legacy_cases


def protected_paths():
    paths = list((ROOT / 'ros_ws/src').glob('*/msg/*.msg'))
    paths += list((ROOT / 'ros_ws/src').glob('*/srv/*.srv'))
    paths += list((ROOT / 'ros_ws/src/uav_fusionmap_sim_scene_msgs/src/ufm_scene_contract').glob('*.py'))
    paths += [ROOT / p for p in ('configs/sim_scene_motion_fixture.json',
        'ros_ws/sim_motion_gate_run.py', 'ros_ws/sensor_scene_run.py', 'ros_ws/sim01_env.sh',
        'configs/sim01_environment.bash', 'ros_ws/src/uav_fusionmap_msgs/src/ufm_ros_contract/codec.py')]
    paths += list((ROOT / 'ros_ws/launch').glob('*.launch'))
    paths += list((ROOT / 'simulation').glob('*.cpp'))
    paths += list((ROOT / 'sensors').glob('*.cpp'))
    return sorted(set(paths))


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write('\n')


def freeze(directory):
    package = ROOT / 'ros_ws/src/uav_fusionmap_sim_scene_msgs/src/ufm_flight_contract'
    if package.exists():
        raise ValueError('freeze must precede production package')
    from ufm_scene_contract.codec import serialize as old_serialize
    directory.mkdir(parents=True, exist_ok=False)
    rows = [dict(row, wire_hex=packed(row['kind'], row['value']).hex()) for row in cases()]
    legacy = [dict(row, wire_hex=old_serialize(row['kind'], row['value']).hex()) for row in legacy_cases()]
    for row in legacy:
        if bytes.fromhex(row['wire_hex']) != packed(row['kind'], row['value']):
            raise ValueError('legacy independent bytes differ')
    sources = {str(p.relative_to(ROOT)): p.read_text() for p in protected_paths()}
    save(directory / 'freeze.json', dict(production_package_exists=False,
        python=sys.executable, expected=expected(), cases=rows, legacy=legacy, protected=sources,
        profile=(ROOT / 'configs/sim_flight_scene_fixture.json').read_text()))
    print(json.dumps(dict(directory=str(directory), cases=len(rows), legacy=len(legacy),
                         definitions=sum(p.endswith(('.msg', '.srv')) for p in sources))))


def verify(directory):
    import io
    from ufm_flight_contract.codec import deserialize, from_ros, serialize, to_ros
    from ufm_scene_contract.codec import deserialize as old_deserialize, serialize as old_serialize
    baseline = json.loads((directory / 'freeze.json').read_text())
    assert not baseline['production_package_exists']
    assert baseline['expected'] == expected()
    assert baseline['profile'] == (ROOT / 'configs/sim_flight_scene_fixture.json').read_text()
    for path, text in baseline['protected'].items():
        assert (ROOT / path).read_text() == text, path
    for row in baseline['cases']:
        kind, value, raw = row['kind'], row['value'], bytes.fromhex(row['wire_hex'])
        generated, stream = to_ros(kind, value), io.BytesIO()
        assert type(generated).__module__.startswith('uav_fusionmap_sim_scene_msgs.')
        generated.serialize(stream)
        assert stream.getvalue() == raw == serialize(kind, value)
        assert from_ros(kind, type(generated)().deserialize(raw)) == value
        assert deserialize(kind, raw) == value
        try:
            old_deserialize(kind, raw)
        except ValueError:
            pass
        else:
            raise AssertionError('v1 accepted flight v2')
    for row in baseline['legacy']:
        kind, raw = row['kind'], bytes.fromhex(row['wire_hex'])
        assert old_serialize(kind, row['value']) == raw
        assert old_deserialize(kind, raw) == row['value']
        try:
            deserialize(kind, raw)
        except ValueError:
            pass
        else:
            raise AssertionError('flight v2 accepted v1')
    report = dict(passed=True, scope='offline real genpy; no runtime endpoints or simulation',
        cases=len(baseline['cases']), legacy=len(baseline['legacy']),
        protected_files=len(baseline['protected']), python=sys.executable,
        binding_status='unverified', control_gate_accepted=False)
    target = directory / ('verification-' + datetime.now().strftime('%Y%m%dT%H%M%S%f') + '.json')
    save(target, report)
    print(json.dumps(dict(report, report=str(target)), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['freeze', 'verify'])
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    (freeze if args.mode == 'freeze' else verify)(args.directory)


if __name__ == '__main__':
    main()
