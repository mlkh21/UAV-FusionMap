"""Independent execution replay of P5 public receipts; never reads scenario expectations."""
import argparse
import json
from pathlib import Path
import sys

from p5_contract import load
from p5_payloads import canonical


def map_replay(directory):
    from ufm_mapping.replay import replay_observations
    spec = load(directory/'replay-config.json')
    observations = load(directory/'map-observations.json')
    snapshots = load(directory/'map-snapshots.json')
    queries = load(directory/'map-queries.json')
    actual = replay_observations(observations,spec['run_id'],spec['settings'],queries,
        backend=spec['backend'],clock_id='sim:'+spec['run_id'],fixture_spec=spec['fixture_spec'])
    passed = (canonical(actual['snapshots']) == canonical(snapshots) and
              canonical(actual['queries']) == canonical(queries))
    return dict(passed=passed,executed=True,observations=len(observations),
                snapshots=len(snapshots),queries=len(queries),actual=actual)


def terrain_replay(directory):
    from ufm_mapping.terrain_recording_contract import load_recording
    from ufm_mapping.terrain_recording import replay_recording
    result = dict(executed=False,matches=False,error='')
    try:
        load_recording(directory)
        result['executed'] = True
        actual = replay_recording(directory)
        result.update(matches=actual['passed'],actual=actual)
    except ValueError as exc:
        result['error'] = str(exc)
    return result


if __name__ == '__main__':
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    parser = argparse.ArgumentParser()
    parser.add_argument('kind',choices=['map','terrain'])
    parser.add_argument('directory',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    result = (map_replay if args.kind == 'map' else terrain_replay)(args.directory)
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
    raise SystemExit(int(args.kind == 'map' and not result['passed']))
