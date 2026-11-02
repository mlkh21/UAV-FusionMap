"""Freeze M4 contracts, explicit trajectories and independent expectations; no Scene execution."""
import argparse
import copy
import datetime
import io
import json
from pathlib import Path
import sys

from m4_fixture import CONFIG, bound_spec, load_spec, observation, scenarios
from m4_oracle import expected_step
from ufm_mapping.m4_contract import validate_fixture_observation, validate_spec
from ufm_ros_contract.perf01a_codec import (to_ros_occupancy, from_ros_occupancy,
                                         to_ros_snapshot, from_ros_snapshot)
from ufm_ros_contract.query_codec import to_ros_query_result, from_ros_query_result


def roundtrip(value, encode, decode):
    message, buffer = encode(value), io.BytesIO()
    message.serialize(buffer)
    return decode(type(message)().deserialize(buffer.getvalue()))


def _wire_expected(value):
    result = copy.deepcopy(value)
    if result.get('uncertainty', 'absent') is None:
        result['uncertainty'] = dict(status='unavailable', kind='', value=None, unit='', source='')
    return result


def _compare_wire(actual, expected):
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_compare_wire(actual[k],expected[k]) for k in actual)
    if isinstance(actual, (list,tuple)) and isinstance(expected, (list,tuple)):
        return len(actual) == len(expected) and all(_compare_wire(a,b) for a,b in zip(actual,expected))
    # The caller resolves nominal/confidence wire precision; all fields then compare exactly.
    return type(actual) is type(expected) and actual == expected


def check_wire_quality(actual, expected):
    """Compare each public numeric slot at its declared wire precision; never rewrite source values."""
    import struct
    expected = copy.deepcopy(expected)
    for key in ('probability','confidence'):
        if key in expected and expected[key] is not None:
            expected[key] = struct.unpack('!f',struct.pack('!f',expected[key]))[0]
    if 'cells' in expected:
        for cell in expected['cells']:
            for key in ('probability','confidence'):
                if cell[key] is not None:
                    cell[key] = struct.unpack('!f',struct.pack('!f',cell[key]))[0]
    if not _compare_wire(actual, expected):
        raise ValueError('M4 expected public fixture differs after actual serialization')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=CONFIG)
    parser.add_argument('--output-root',type=Path,default=CONFIG.parent.parent/'.runtime/runs')
    args=parser.parse_args(argv)
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    # Use the client/project date and explicit timezone, independent of the host timezone.
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    identity='m4-fixture-'+now.strftime('%Y%m%dT%H%M%S%f')
    run=args.output_root.resolve()/identity
    run.mkdir(parents=True,exist_ok=False)
    report=dict(run_id=identity,passed=False,errors=[],python=sys.executable,
        scene_map_executed=False,map_accumulation_executed=False,ros_master_started=False,
        scope='M4-SW-01 contract, explicit input/ownership tables and independent expectations only')
    try:
        spec=load_spec(args.config)
        (run/'config.json').write_text(json.dumps(spec,indent=2))
        cases=scenarios(spec)
        frozen=[]
        for case in cases:
            case['spec']=bound_spec(case['spec'],identity+':'+case['name'])
            validate_spec(case['spec'])
            steps=[]
            for declaration in case['steps']:
                row=observation(case['spec'],declaration)
                expected=expected_step(case['spec'],case['versions'],declaration)
                steps.append(dict(declaration=declaration,observation=row,expected=expected))
            frozen.append(dict(name=case['name'],spec=case['spec'],versions=case['versions'],steps=steps))
        # Freeze before any contract/serialization comparison; no candidate is imported or run.
        (run/'fixtures.json').write_text(json.dumps(frozen,indent=2))
        accepted,refused,query_count=0,0,0
        for case in frozen:
            for item in case['steps']:
                row=item['observation']
                for value in (row,roundtrip(row,to_ros_occupancy,from_ros_occupancy)):
                    try:
                        validate_fixture_observation(value,case['spec'])
                        accepts=True
                    except (ValueError,KeyError,TypeError):
                        accepts=False
                    if accepts != item['declaration']['contract_accepts']:
                        raise ValueError('M4 contract outcome differs: '+case['name'])
                if roundtrip(row,to_ros_occupancy,from_ros_occupancy) != row:
                    raise ValueError('M4 input serialization changed declared observation')
                accepted+=int(accepts)
                refused+=int(not accepts)
                expected=item['expected']
                check_wire_quality(roundtrip(expected['snapshot'],to_ros_snapshot,from_ros_snapshot),
                                   expected['snapshot'])
                for query in expected['queries']:
                    result=_wire_expected(query['result'])
                    check_wire_quality(roundtrip(result,to_ros_query_result,from_ros_query_result),result)
                    query_count+=1
        if any(name.endswith('probability_map') for name in sys.modules):
            raise RuntimeError('SW-01 unexpectedly imported a map accumulator')
        report.update(passed=True,scenario_count=len(frozen),
            observation_count=accepted+refused,contract_accepted=accepted,contract_refused=refused,
            query_count=query_count,expected_states=sorted({q['result']['status'] for c in frozen
                for s in c['steps'] for q in s['expected']['queries']}),
            note='stateful outcome/ownership tables are frozen expectations, not candidate results')
    except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:
        report['errors'].append(type(exc).__name__+':'+str(exc))
    (run/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(dict(run=str(run),passed=report['passed'],errors=report['errors'])))
    return int(not report['passed'])


if __name__=='__main__':
    sys.exit(main())
