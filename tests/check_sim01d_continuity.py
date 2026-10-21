"""SIM-01D长测验收：使用B的记录完整性检查，并强制跨越32位微秒边界。"""
import argparse
import json
from pathlib import Path
import sys

from sim01b_validation import CLOCK, SOURCE

# 与独立配置保持同一冻结门槛；通过运行时覆盖只影响本模块调用，不改变B/C验收。
BOUNDARY_NS = 2_147_483_647_000
SPAN_NS = 2_400_000_000_000
LIMIT_NS = 2_520_000_000_000


def validate_sim01d(run):
    import sim01b_validation as base
    old_span, old_limit = base.SPAN_NS, base.LIMIT_NS
    try:
        base.SPAN_NS = SPAN_NS
        base.LIMIT_NS = LIMIT_NS
        result = base.validate_live(run)
    finally:
        base.SPAN_NS, base.LIMIT_NS = old_span, old_limit
    errors = list(result.get('errors', []))
    rows = []
    try:
        with (Path(run) / 'records.jsonl').open() as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
    except (OSError, ValueError) as exc:
        errors.append('boundary records: ' + str(exc))
    clocks = [row['timestamp'] for row in rows if row.get('topic') == CLOCK and
              isinstance(row.get('timestamp'), int)]
    sources = [row['timestamp'] for row in rows if row.get('topic') == SOURCE and
               isinstance(row.get('timestamp'), int)]
    if not any(value < BOUNDARY_NS for value in clocks) or not any(value >= BOUNDARY_NS for value in clocks):
        errors.append('boundary: /clock未跨越2147483647000ns')
    if not any(value < BOUNDARY_NS for value in sources) or not any(value >= BOUNDARY_NS for value in sources):
        errors.append('boundary: source state未跨越2147483647000ns')
    result['errors'] = list(dict.fromkeys(errors))
    result['passed'] = not result['errors']
    result['boundary_ns'] = BOUNDARY_NS
    result['boundary_crossed'] = not result['errors']
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--output', type=Path, help='可选新结果文件；拒绝覆盖既有文件')
    args = parser.parse_args(argv)
    result = validate_sim01d(args.run_dir)
    if args.output is not None:
        try:
            with args.output.open('x') as stream:
                stream.write(json.dumps(result, indent=2) + '\n')
        except OSError as exc:
            parser.error('无法创建新结果文件：' + str(exc))
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
