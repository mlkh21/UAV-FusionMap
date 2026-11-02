"""Independent JSBSim pilot-acceleration scenarios; never feeds online IMU data."""
import argparse
import datetime
import json
import math
from pathlib import Path
import subprocess
import sys


CASES = (('ground', 0, 'ground'), ('freefall', 0, 'freefall'),
         ('roll-positive', 20, 'ground'), ('roll-negative', -20, 'ground'))
MARKER = 'IMU_PROBE_RESULT '


def check_scenarios(cases):
    """Verify only observable JSBSim scenario contrasts, not IMU calibration."""
    errors = []
    if set(cases) != {name for name, _, _ in CASES}:
        return ['missing JSBSim scenario']
    for name, roll, scenario in CASES:
        row = cases[name]
        try:
            values = (row['pilot_last_mps2'] + row['pilot_mean_mps2'] +
                      row['pilot_0p2s_mps2'] + row['body_forces_mean_mps2'])
            if (row['scenario'] != scenario or row['roll_initial_deg'] != roll or
                    row['steps'] != 750 or row['dt_s'] != .004 or
                    len(values) != 12 or not all(math.isfinite(v) for v in values) or
                    not math.isfinite(row['roll_0p2s_deg']) or
                    row['eyepoint_struct_in'] != [20., 0., 5.] or
                    not 9. < row['gravity_mps2'] < 11.):
                errors.append('invalid scenario configuration or sample: ' + name)
        except (KeyError, TypeError, ValueError):
            errors.append('missing scenario fields: ' + name)
    if errors:
        return errors
    if not -11. < cases['ground']['pilot_last_mps2'][2] < -8.:
        errors.append('grounded pilot force does not oppose gravity')
    if not -2. < cases['freefall']['pilot_0p2s_mps2'][2] < 2.:
        errors.append('early freefall pilot force is gravity-like')
    if not (cases['roll-positive']['roll_0p2s_deg'] > 10. and
            cases['roll-negative']['roll_0p2s_deg'] < -10. and
            cases['roll-positive']['pilot_0p2s_mps2'][1] < -1. and
            cases['roll-negative']['pilot_0p2s_mps2'][1] > 1.):
        errors.append('roll contrast not observed at actual sample attitude')
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live-result', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.runtime'
    bridge = runtime / 'src/px4-v1.13.3/Tools/jsbsim_bridge'
    installed = runtime / 'deps/jsbsim-1.1.13/usr'
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        parser.error('Radar-Diffusion Python required')
    run = runtime / 'runs' / ('imu-physics-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    run.mkdir(parents=True, exist_ok=False)
    report = dict(passed=False, run=str(run), bridge_root=str(bridge),
                  live_result=str(args.live_result.resolve()), cases={}, errors=[],
                  scope='independent JSBSim scenarios; not same-run bridge/PX4 truth')
    try:
        live = json.loads(args.live_result.read_text())
        if not live.get('passed') or not live.get('imu_live') or not live.get('imu_audit', {}).get('passed'):
            raise ValueError('reference live IMU result did not pass')
        archive = dict(imu_samples=live['imu_audit']['raw_source_matches'],
                       acceleration_axes=live['imu_audit']['acceleration_axes'])
        report['archived_live'] = archive
        executable = run / 'imu_physics_probe'
        command = ['g++', '-std=c++17', '-O2', '-I' + str(installed / 'include/JSBSim'),
                   str(root / 'simulation/imu_physics_probe.cpp'), str(installed / 'lib/libJSBSim.a'),
                   '-lpthread', '-ldl', '-o', str(executable)]
        built = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
        (run / 'build.log').write_text(built.stdout + built.stderr)
        report['build_command'] = command
        if built.returncode:
            raise RuntimeError('probe compilation failed (see build.log)')
        for name, roll, scenario in CASES:
            proc = subprocess.run([str(executable), str(bridge), str(roll), '750', scenario],
                                  capture_output=True, text=True, timeout=30, check=False)
            (run / (name + '.log')).write_text(proc.stdout + proc.stderr)
            rows = [json.loads(line[len(MARKER):]) for line in proc.stdout.splitlines()
                    if line.startswith(MARKER)]
            if proc.returncode or len(rows) != 1:
                raise RuntimeError('JSBSim probe failed: ' + name + ' (see run log)')
            report['cases'][name] = rows[0]
        report['errors'] = check_scenarios(report['cases'])
        report['passed'] = not report['errors']
        if report['passed']:
            # This comparison is descriptive only: PX4 bias/noise and FDM controls differ.
            report['cross_run_ground_last_minus_live_mean_mps2'] = [
                report['cases']['ground']['pilot_last_mps2'][axis] - archive['acceleration_axes'][axis]['mean']
                for axis in range(3)]
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        report['errors'].append(str(exc))
    (run / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(run=str(run), passed=report['passed'], errors=report['errors'])))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
