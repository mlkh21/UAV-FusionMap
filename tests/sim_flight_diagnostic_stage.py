"""Explicit SW-02C acquisition, independent reload, and unchanged legacy regression."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from sim_flight_probe_fixture import ROOT, BINARY_DIR
from sim_motion_matrix_run import source_snapshot
from ufm_simulation.flight_probe_contract import FILE_BYTES, RECORD_BYTES, GROUP_NS
from ufm_simulation.flight_probe_diagnostic import loads, validate_stream
from ufm_simulation.flight_probe_contract import layouts_from_texts


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def audit(directory, manifest):
    formats = layouts_from_texts(json.loads((directory/'native-msg-before.json').read_text()))
    rawdir = directory/'uorb-diagnostics'
    if sum(p.stat().st_size for p in rawdir.iterdir()) > FILE_BYTES:
        raise ValueError('diagnostic_all_files_budget')
    rows = []
    with (rawdir/'diagnostics.jsonl').open('rb') as stream:
        while True:
            raw = stream.readline(RECORD_BYTES+1)
            if not raw:
                break
            if len(rows) >= 21 or not raw.endswith(b'\n'):
                raise ValueError('diagnostic_reload_bound')
            rows.append(loads(raw, formats, BINARY_DIR))
    result = validate_stream(rows, manifest['run_id'], formats, BINARY_DIR)
    host = {r['step_index']:r for r in map(json.loads, (directory/'diagnostics/actuators.jsonl').read_text().splitlines())}
    for row in rows:
        q = row['query']
        source = host[q['checkpoint']]
        if row['last_hil_us'] != source['hil_sensor_time_us'] or row['fdm_time_s'] != source['fdm']['sim_time_after_s']:
            raise ValueError('diagnostic_reload_host_context')
        original = json.loads((rawdir/('%02d-raw.json' % q['query_index'])).read_text())
        if any(original[k] != row[k] for k in ('argv','stdout','stderr','returncode')):
            raise ValueError('diagnostic_reload_raw_context')
    initial = json.loads((directory/'diagnostics/initial.json').read_text())
    for group in rawdir.glob('group-*.json'):
        value = json.loads(group.read_text())
        subset = [r for r in rows if r['query']['checkpoint'] == value['checkpoint'] and r['query']['kind'] == value['kind']]
        if (len(subset) != value['queries'] or value['end_ns']-value['start_ns'] > GROUP_NS
                or value['end_ns'] > value['deadline_ns'] or value['deadline_ns'] > initial['initial_wall_ns']+5000000000
                or subset[0]['wall_start_ns'] < value['start_ns'] or subset[-1]['wall_end_ns'] > value['end_ns']):
            raise ValueError('diagnostic_reload_group_context')
    if len(list(rawdir.glob('group-*.json'))) != 3:
        raise ValueError('diagnostic_reload_groups')
    if result != manifest['uorb_diagnostics_verification']:
        raise ValueError('diagnostic_reload_summary')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    run = ROOT/'.runtime/runs'/('sim-flight-sw02c-stage-'+datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True)
    print(run, flush=True)
    baseline = source_snapshot()
    save(run/'source-before.json', baseline)
    with (run/'independent-expectations.json').open('xb') as stream:
        stream.write((ROOT/'tests/fixtures/sim_flight_diagnostic_cases.json').read_bytes())
    save(run/'git-before.json', dict(head=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT,text=True).strip(),
        status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True).splitlines()))
    with (run/'flight-targeted.log').open('x') as stream:
        targeted = subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_sim_flight*.py','-v'],
            cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
    if targeted.returncode:
        raise RuntimeError('targeted tests failed; see saved log')
    with (run/'diagnostic.log').open('x') as stream:
        child = subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws/sim_flight_diagnostic_run.py'),'--uorb-diagnostics'],
            cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=300)
    directory = Path((run/'diagnostic.log').read_text().splitlines()[0])
    if directory.parent != ROOT/'.runtime/runs':
        raise ValueError('missing isolated diagnostic directory')
    manifest = json.loads((directory/'manifest.json').read_text())
    acquired = child.returncode == 0 and manifest['diagnostic_collection_complete']
    audited = audit(directory, manifest) if acquired else None
    save(run/'acquisition-result.json', dict(directory=str(directory), returncode=child.returncode,
        diagnostic_collection_complete=acquired, errors=manifest['errors'], reload=audited))
    print('diagnostic: '+str(directory)+' complete='+str(acquired), flush=True)
    command = [sys.executable,'-B',str(ROOT/'tests/sim_flight_stage_run.py')]+(['--full'] if args.full else [])
    with (run/'compatibility.log').open('x') as stream:
        compatibility = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=660)
    previous = Path((run/'compatibility.log').read_text().splitlines()[0])/'report.json'
    compatible = compatibility.returncode == 0 and json.loads(previous.read_text())['passed']
    unchanged = source_snapshot() == baseline
    result = dict(passed=acquired and compatible and unchanged, python=sys.executable,
        diagnostic_directory=str(directory), diagnostic_collection_complete=acquired,
        payload_complete=bool(audited and audited['payload_complete']),
        acquisition=audited, compatibility_passed=compatible, compatibility_report=str(previous),
        source_files=len(baseline), source_unchanged=unchanged, full_requested=args.full,
        binding_status='unverified', control_gate_accepted=False, legacy_sw02b_runtime_accepted=False,
        scope='Only bounded diagnostic collection and software regression')
    save(run/'report.json', result)
    print(json.dumps({k:v for k,v in result.items() if k != 'acquisition'}), flush=True)
    return int(not result['passed'])


if __name__ == '__main__':sys.exit(main())
