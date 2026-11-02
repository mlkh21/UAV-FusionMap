"""Freeze P5 inputs/oracles, then exercise real generated ROS serialization offline."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from p5_contract import ROOT, load, load_pair, budget, expand
from p5_oracle import verify_seeds
from p5_payloads import materialize, wire_vectors, roundtrip, canonical, check_projections


def save(path, value):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n')


def verify(directory):
    inputs, expected = load_pair()
    verify_seeds(inputs,expected)
    # Both independent source files and every materialized input precede codec execution.
    save(directory/'inputs.json',inputs)
    save(directory/'expectations.json',expected)
    rows, vectors = materialize(inputs), wire_vectors(inputs)
    payload_dir = directory/'payloads'
    payload_dir.mkdir()
    for row in rows:
        save(payload_dir/(row['id']+'.json'),row)
    save(directory/'wire-inputs.json',vectors)
    del rows, vectors
    report = dict(python=sys.executable,passed=False,ros_master_started=False,
        perception_executed=False,map_accumulation_executed=False,provider_executed=False,
        combination_scenarios_executed=False,errors=[],cases=len(inputs['cases']),wire=[],
        budgets={c['id']:budget(expand(c,inputs['sequences']),c['recording']) for c in inputs['cases']})
    wire_count = samples = observations = 0
    try:
        for row in load(directory/'wire-inputs.json'):
            decoded,raw = roundtrip(row['kind'],row['value'])
            if decoded != canonical(row['value']):
                raise ValueError('P5 wire logical mismatch: '+row['id'])
            check_projections(decoded,expected['wire_projections'][row['id']])
            (directory/(row['id']+'.bin')).write_bytes(raw)
            report['wire'].append(dict(id=row['id'],kind=row['kind'],bytes=len(raw)))
            wire_count += 1
        from ufm_mapping.terrain_dataset import validate_dataset
        from ufm_mapping.m4_contract import validate_fixture_observation
        from ufm_sensors.perf01a_fixture import validate_bundle
        for path in sorted(payload_dir.iterdir()):
            row = load(path)
            validate_dataset(row['terrain_dataset'])
            decoded_rows = []
            for item in row['samples']:
                samples += 1
                decoded = dict(event_id=item['event_id'],reason=item['reason'])
                for key,kind in [('source_state','AircraftState'),('state','AircraftState'),
                                 ('radar','RadarFrame'),('infrared','InfraredFrame'),('bundle','SensorBundle')]:
                    value = item[key]
                    if value is None:
                        decoded[key] = None
                        continue
                    actual,raw = roundtrip(kind,value)
                    if actual != canonical(value):
                        raise ValueError('P5 saved sample wire mismatch: '+row['id']+'/'+item['event_id']+'/'+key)
                    if key == 'bundle':
                        validate_bundle(actual)
                    decoded[key] = actual
                    wire_count += 1
                decoded_rows.append(decoded)
            for item in row['observations']:
                value = item['value']
                validate_fixture_observation(value,row['map_spec'])
                actual,raw = roundtrip('OccupancyObservation',value)
                if actual != canonical(value):
                    raise ValueError('P5 inverse wire mismatch')
                validate_fixture_observation(actual,row['map_spec'])
                wire_count += 1
                observations += 1
            save(directory/(row['id']+'-decoded.json'),decoded_rows)
        forbidden = ('ufm_mapping.terrain_provider','ufm_mapping.scene_map','ufm_mapping.probability_map',
                     'ufm_mapping.interval_probability_map','ufm_perception.engine','ufm_perception.placeholder')
        if any(name in sys.modules for name in forbidden):
            raise RuntimeError('P5 SW-01 imported a runtime candidate')
        report.update(passed=True,sample_count=samples,observation_count=observations,
                      serialized_messages=wire_count,scenario_groups=9)
    except (ValueError,TypeError,KeyError,OSError,RuntimeError) as exc:
        report['errors'].append(type(exc).__name__+': '+str(exc))
    save(directory/'report.json',report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    directory = ROOT/'.runtime/runs'/('p5-sw01-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    directory.mkdir(parents=True,exist_ok=False)
    print(directory,flush=True)
    report = verify(directory)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if not report['passed']:
        return 1
    patterns = [('targeted','test_p5_*.py')]
    if args.full:
        patterns.append(('full','test_*.py'))
    passed = True
    for name,pattern in patterns:
        process = subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p',pattern,'-v'],
            cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
        with (directory/(name+'.log')).open('x') as stream:
            stream.write(process.stdout)
        save(directory/(name+'-result.json'),dict(returncode=process.returncode))
        passed = passed and process.returncode == 0
        print(name+': '+'\n'.join(process.stdout.strip().splitlines()[-5:]),flush=True)
    return int(not passed)


if __name__ == '__main__':
    sys.exit(main())
