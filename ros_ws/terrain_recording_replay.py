"""Strict offline public terrain replay; never advertises live service or topics."""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    from ufm_mapping.terrain_recording import replay_recording
    result = replay_recording(args.input)
    payload = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        with args.output.open('x') as handle: handle.write(payload)
    else:
        print(payload)


if __name__ == '__main__':
    main()
