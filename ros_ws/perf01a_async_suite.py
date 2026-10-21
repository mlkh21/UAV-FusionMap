"""串行运行预登记异步场景，所有结果进入新的独立suite目录。"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration-s', type=float, default=3.)
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--port', type=int, default=11431)
    parser.add_argument('--full-ir', action='store_true')
    args = parser.parse_args()
    if not 2 <= args.duration_s <= 60 or not 1 <= args.repeat <= 3:
        parser.error('duration in [2,60], repeat in [1,3] required')
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    directory = root / '.runtime/runs' / ('perf01a-async-suite-' +
        datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    directory.mkdir(parents=True, exist_ok=False)
    scenarios = ('normal', 'phase_offset', 'jitter', 'out_of_order', 'missing', 'overflow', 'recovery')
    commands = [[sys.executable, str(root / 'ros_ws/perf01a_async_run.py'),
                 '--duration-s', str(args.duration_s), '--scenario', scenario,
                 '--port', str(args.port + iteration * len(scenarios) + offset)] +
                (['--full-ir'] if args.full_ir else [])
                for iteration in range(args.repeat) for offset, scenario in enumerate(scenarios)]
    with (directory / 'registered.json').open('x') as handle:
        json.dump(dict(commands=commands, python=sys.executable), handle, indent=2)
    results = []
    for index, command in enumerate(commands):
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        with (directory / ('run-%02d.log' % index)).open('x') as handle:
            handle.write(completed.stdout)
        result = dict(command=command, returncode=completed.returncode)
        for line in reversed(completed.stdout.splitlines()):
            try:
                value = json.loads(line)
                if isinstance(value, dict) and 'run' in value:
                    result.update(value)
                    break
            except ValueError:
                continue
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    passed = all(r['returncode'] == 0 and r.get('passed') for r in results)
    with (directory / 'suite-report.json').open('x') as handle:
        json.dump(dict(passed=passed, results=results), handle, ensure_ascii=False, indent=2)
    print(json.dumps(dict(suite=str(directory), passed=passed)), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
