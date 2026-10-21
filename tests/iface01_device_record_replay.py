"""Read-only IFACE-01 device-record replay audit (not a hardware gate)."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sensors'))
from ufm_sensors.device_time_record import validate_device_time_record


def audit_jsonl(path):
    """Check one decoded device stream; never infer cross-clock synchronization."""
    seen = set()
    identity = None
    bounds = {'device_timestamp_ns': [None, None],
              'receive_timestamp_ns': [None, None]}
    count = 0
    with Path(path).open(encoding='utf-8') as source:
        for line_number, line in enumerate(source, 1):
            try:
                record = json.loads(line)
                validate_device_time_record(record)
            except (ValueError, TypeError) as error:
                raise ValueError('line %d: %s' % (line_number, error)) from error
            current = tuple(record[key] for key in
                            ('record_kind', 'device_model', 'run_id', 'clock_id',
                             'receive_clock_id', 'frame_id'))
            if identity is None:
                identity = current
            elif current != identity:
                raise ValueError('line %d: device or clock identity changed' % line_number)
            if record['sample_id'] in seen:
                raise ValueError('line %d: duplicate sample_id' % line_number)
            seen.add(record['sample_id'])
            for key, pair in bounds.items():
                value = record[key]
                pair[0] = value if pair[0] is None else min(pair[0], value)
                pair[1] = value if pair[1] is None else max(pair[1], value)
            count += 1
    if count == 0:
        raise ValueError('empty device time stream')
    return dict(schema_version='iface01_replay_audit_v1', record_count=count,
                **dict(zip(('record_kind', 'device_model', 'run_id', 'clock_id',
                            'receive_clock_id', 'frame_id'), identity)),
                device_timestamp_bounds_ns=bounds['device_timestamp_ns'],
                receive_timestamp_bounds_ns=bounds['receive_timestamp_ns'],
                time_mapping_status='unmapped', hardware_validated=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='existing JSONL decoded device record')
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        parser.error('Radar-Diffusion Python required')
    try:
        result = audit_jsonl(args.input)
    except (OSError, UnicodeError, ValueError) as error:
        print(json.dumps(dict(passed=False, error=str(error))), file=sys.stderr)
        return 1
    print(json.dumps(dict(passed=True, **result), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
