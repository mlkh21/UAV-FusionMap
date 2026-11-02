"""Save independent public examples before exercising generated terrain wire codecs."""
import argparse
from datetime import datetime
import io
import json
from pathlib import Path
import subprocess
import sys

from m5_iface_fixture import LAYOUT, ROOT, expected, independent_bytes, request, result, status, unavailable, wire_object


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true', help='also run the complete lightweight unittest suite')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('wrong Python interpreter')
    directory = ROOT / '.runtime/runs' / ('m5-iface-sw01-' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    directory.mkdir(parents=True, exist_ok=False)
    cases = [('TerrainQueryRequest', request()), ('TerrainContext', expected()['context']),
             ('TerrainStatus', status()), ('TerrainQueryResult', unavailable())]
    cases += [('TerrainQueryResult', result(i)) for i in range(4)]
    saved = dict(expectations=expected(), independent_layout=LAYOUT, cases=cases)
    (directory / 'inputs-and-expectations.json').write_text(json.dumps(saved, indent=2, allow_nan=False) + '\n')
    for i, (name, row) in enumerate(cases):
        (directory / ('expected-%02d.bin' % i)).write_bytes(independent_bytes(name, wire_object(name, row)))

    from ufm_terrain_contract.codec import deserialize, to_ros
    from test_m5_iface_recording import saved_recording, write_recording
    from ufm_mapping.terrain_recording_contract import load_recording
    wire = []
    for i, (name, row) in enumerate(cases):
        message, stream = to_ros(name, row), io.BytesIO()
        message.serialize(stream)
        payload = stream.getvalue()
        if payload != (directory / ('expected-%02d.bin' % i)).read_bytes() or deserialize(name, payload) != row:
            raise AssertionError('independent wire expectation mismatch')
        (directory / ('actual-%02d.bin' % i)).write_bytes(payload)
        wire.append(dict(name=name, bytes=len(payload)))
    recording = directory / 'recording'
    recording.mkdir()
    values = saved_recording()
    write_recording(recording, values)
    if load_recording(recording) != values:
        raise AssertionError('recording schema roundtrip mismatch')
    report = dict(python=sys.executable, wire=wire, recording_schema_roundtrip=True,
                  provider_or_ros_service_started=False, runtime_replay_tested=False)
    runs = [('targeted', 'test_m5_iface*.py')]
    if args.full:
        runs.append(('full', 'test_*.py'))
    for label, pattern in runs:
        process = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v'],
                                 cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (directory / (label + '.log')).write_text(process.stdout)
        report[label + '_returncode'] = process.returncode
        print(label + ': ' + '\n'.join(process.stdout.strip().splitlines()[-4:]), flush=True)
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(directory, flush=True)
    return int(any(report.get(label + '_returncode') for label, _ in runs))


if __name__ == '__main__':
    sys.exit(main())
