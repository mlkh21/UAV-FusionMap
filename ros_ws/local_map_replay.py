"""Read existing ROS fixture receipts and verify deterministic public-map replay."""
import argparse
import datetime
import json
from pathlib import Path
import sys

from runtime_config import load_m2_config, load_m3_config, load_m4_config, load_map_config
from ufm_mapping.replay import equivalent, replay_observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--rolling', action='store_true')
    parser.add_argument('--free-threshold', type=float)
    parser.add_argument('--occupied-threshold', type=float)
    parser.add_argument('--map-backend', choices=('latest', 'm2_fixture', 'm3_fixture', 'm4_fixture'), default='latest')
    parser.add_argument('--m2-fixture-config', type=Path)
    parser.add_argument('--m3-fixture-config', type=Path)
    parser.add_argument('--m4-fixture-config', type=Path)
    parser.add_argument('--clock-id')
    parser.add_argument('--map-config', type=Path)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    root = Path(__file__).resolve().parents[1]
    run = root / '.runtime/runs' / ('local-map-replay-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, errors=[], source=str(args.input.resolve()),
                  configured_run_id=args.run_id, python=sys.executable,
                  scope='occupancy receipt replay, not real-device or performance acceptance')
    try:
        source = json.loads(args.input.read_text())
        keys = [key for key in ('observations', 'occupancies', 'published') if key in source]
        if not keys:
            raise ValueError('receipt has no occupancy records')
        observations = source[keys[0]]
        if not observations or any('voxels' not in row for row in observations):
            raise ValueError('receipt must contain nonempty OccupancyObservation records')
        spec = None
        configs = dict(m2_fixture=args.m2_fixture_config, m3_fixture=args.m3_fixture_config,
                       m4_fixture=args.m4_fixture_config)
        if args.map_backend in configs:
            if any(path is not None for name, path in configs.items() if name != args.map_backend):
                raise ValueError('fixture configurations cannot be mixed')
            if args.free_threshold is not None or args.occupied_threshold is not None:
                raise ValueError('thresholds must come from fixture configuration')
            loader = dict(m2_fixture=load_m2_config, m3_fixture=load_m3_config,
                          m4_fixture=load_m4_config)[args.map_backend]
            spec = loader(configs[args.map_backend])
            settings = dict(rolling_enabled=args.rolling)
        else:
            if args.m2_fixture_config is not None:
                raise ValueError('M2 configuration requires explicit m2_fixture backend')
            if args.m3_fixture_config is not None:
                raise ValueError('M3 configuration requires explicit m3_fixture backend')
            if args.m4_fixture_config is not None:
                raise ValueError('M4 configuration requires explicit m4_fixture backend')
            settings = load_map_config(args.map_config)
            settings.update(rolling_enabled=args.rolling, free_threshold=args.free_threshold,
                            occupied_threshold=args.occupied_threshold)
        report['map_settings'] = settings
        report.update(map_backend=args.map_backend, clock_id=args.clock_id)
        report[args.map_backend + '_config'] = spec
        rebuilt = replay_observations(observations, args.run_id, settings, source.get('queries', []),
            backend=args.map_backend, clock_id=args.clock_id, fixture_spec=spec)
        if 'snapshots' not in source or not equivalent(rebuilt['snapshots'], source['snapshots']):
            report['errors'].append('replayed snapshots differ from recorded snapshots')
        if not equivalent(rebuilt['queries'], source.get('queries', [])):
            report['errors'].append('replayed queries differ from recorded queries')
        if 'outcomes' in source and [row['outcome'] for row in rebuilt['steps']] != source['outcomes']:
            report['errors'].append('replayed refusal/fusion outcomes differ from recorded outcomes')
        report.update(observation_count=len(observations), snapshot_count=len(rebuilt['snapshots']),
                      query_count=len(rebuilt['queries']),
                      rejected_count=sum(row['outcome'] == 'rejected' for row in rebuilt['steps']))
        with (run / 'replay.json').open('x') as handle:
            json.dump(rebuilt, handle, indent=2)
        report['passed'] = not report['errors']
    except (ValueError, KeyError, TypeError, OSError) as exc:
        report['errors'].append(type(exc).__name__ + ':' + str(exc))
    with (run / 'report.json').open('x') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
