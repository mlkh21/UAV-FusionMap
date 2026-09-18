"""调用方式：Conda Python check_sim01b_replay.py LIVE_DIR REPLAY_DIR B1|B2。"""
import argparse
import json
from pathlib import Path
import sys

from sim01b_validation import validate_replay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('live', type=Path)
    parser.add_argument('replay', type=Path)
    parser.add_argument('mode', choices=('B1', 'B2'))
    args = parser.parse_args()
    result = validate_replay(args.live, args.replay, args.mode)
    (args.replay / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
