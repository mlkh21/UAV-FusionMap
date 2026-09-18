"""调用方式：Conda Python check_sim01b_recording.py LIVE_DIR。"""
import argparse
import json
from pathlib import Path
import sys

from sim01b_validation import validate_live


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    result = validate_live(args.run)
    (args.run / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
