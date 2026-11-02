"""Save preimplementation runtime inputs and protected sources without hashes."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    assert sys.executable == '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python'
    assert not (ROOT/'simulation/flight_scene').exists()
    directory = ROOT/'.runtime/runs/flight-sw03b-oracle-20261102'
    directory.mkdir(exist_ok=False)
    paths = [p for folder in ('simulation','sensors','ros_ws','configs','tests')
             for p in (ROOT/folder).rglob('*') if p.is_file() and
             p.suffix in ('.py','.h','.cpp','.json','.yaml','.msg','.srv','.launch','.bash','.sh')
             and '__pycache__' not in p.parts]
    baseline = dict(production_exists=False, python=sys.executable,
        expectations=json.loads((ROOT/'tests/fixtures/sim_flight_scene_runtime_expectations.json').read_text()),
        sources={str(p.relative_to(ROOT)):p.read_text() for p in sorted(paths)})
    with (directory/'freeze.json').open('x') as stream:
        json.dump(baseline,stream,indent=2,ensure_ascii=True)
    print(directory,flush=True)
    print('protected source texts:',len(paths))


if __name__ == '__main__':
    main()
