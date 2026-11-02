"""S09 actual graph faults, fresh run and separate native Gazebo/RViz delivery."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'application'))
from p5_contract import load_pair, load, expand
from p5_delivery_checks import verify_delivery, native_separation
from sim01b_runtime import (Processes, configure_environment, install_interrupt_handler,
    probe_ports, python_process_audit, start_master, write_json)


def process_identity(pid):
    stat = (Path('/proc') / str(pid) / 'stat').read_text()
    fields = stat[stat.rfind(')') + 2:].split()
    return dict(pid=pid, start_ticks=int(fields[19]), state=fields[0])


def sentinel_live(saved):
    try:
        current = process_identity(saved['pid'])
        return current['start_ticks'] == saved['start_ticks'] and current['state'] != 'Z'
    except (OSError, ValueError):
        return False


def command_run(command, log, timeout):
    """Signal the child's supervisor so its finally block cleans its own process groups."""
    with log.open('x') as stream:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        try:
            code = child.wait(timeout=timeout)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGINT)
                child.wait(timeout=30.)
    if code:
        raise RuntimeError('subcommand failed; see ' + str(log))
    rows = []
    for line in log.read_text().splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict) and 'run' in value:
                rows.append(value)
        except ValueError:
            pass
    if not rows:
        raise ValueError('subcommand did not identify evidence directory')
    directory = Path(rows[-1]['run']).resolve()
    try:
        directory.relative_to(ROOT / '.runtime/runs')
    except ValueError as exc:
        raise ValueError('subcommand evidence outside isolated runtime') from exc
    return directory


def native_views(directory, port, display, xauthority):
    scene = command_run([sys.executable, '-B', str(ROOT / 'ros_ws/sensor_scene_run.py'), '--check',
        '--port', str(port + 2), '--gazebo-port', str(port + 3), '--display', display,
        '--xauthority', xauthority], directory / 'native-scene.log', 110.)
    terrain = command_run([sys.executable, '-B', str(ROOT / 'ros_ws/terrain_delivery_run.py'),
        '--with-rviz', '--port', str(port + 4), '--display', display, '--xauthority', xauthority],
        directory / 'native-terrain.log', 90.)
    sm, tm = load(scene / 'manifest.json'), load(terrain / 'manifest.json')
    # Read exactly the configs used by the owned native windows and snapshot them.
    scene_config = yaml.safe_load((scene / 'sensor_scene.rviz').read_text())
    terrain_config = yaml.safe_load((ROOT / 'configs/terrain.rviz').read_text())
    shutil.copy2(ROOT / 'configs/terrain.rviz', directory / 'terrain.rviz')
    values = native_separation(sm, tm, scene_config, terrain_config)
    graph = sm['graph']
    if any('/terrain' in topic for group in graph[:2] for topic, nodes in group):
        values['view.unregistered_overlay'] = True
    scene_pixels = load(scene / 'figures/pixel-validation.json')
    terrain_pixels = load(terrain / 'pixel-validation.json')
    if not (scene_pixels['passed'] and terrain_pixels['passed'] and
            load(scene / 'cleanup-audit.json')['passed'] and load(terrain / 'cleanup-audit.json')['passed']):
        values['view.native'] = False
    receipt = dict(scene=str(scene), terrain=str(terrain), values=values,
                   scene_pixels=scene_pixels, terrain_pixels=terrain_pixels,
                   terrain_registered_to_scene=False)
    write_json(directory / 'native-views.json', receipt)
    return values


def run_case(args):
    from p5_delivery_case import DeliveryCase
    directory = args.directory
    inputs = load(directory.parent / 'inputs.json')
    expected = load(directory.parent / 'independent-expectations.json')
    case = next(c for c in inputs['cases'] if c['id'] == args.case_worker)
    answers = next(c for c in expected['cases'] if c['id'] == case['id'])
    identity = directory.parent.name + '-' + case['id'].lower().replace('.', '-')
    for name in ('ros-home', 'ros-logs'):
        (directory / name).mkdir()
    env = configure_environment(directory, args.port)
    manifest = dict(run_id=identity, case_id=case['id'], python=sys.executable,
                    commands=[], errors=[], passed=False)
    processes = Processes(directory, env, manifest)
    observer, previous_instance = None, None
    origin = time.monotonic_ns()
    receipts = []
    events = expand(case, inputs['sequences'])
    def record(name, values):
        event = next(e for e in events if e[0] == name)
        receipts.append(dict(event_id=name, operation=event[1], planned_wall_ns=event[3],
                             completion_elapsed_ns=time.monotonic_ns() - origin, values=values))
    try:
        if any(not row['free'] for row in probe_ports('P5-C', args.port)):
            raise RuntimeError('existing master preserved; choose a free port')
        start_master(processes, args.port, time.monotonic() + 15.)
        import rospy
        rospy.init_node('p5_source', disable_signals=True)
        observer = DeliveryCase(inputs, case, directory, identity, processes)
        if case['id'] == 'S09.recover_view':
            record('new_run', observer.recover(identity, events[0][4]['previous_run']))
            previous_instance = load(directory / 'previous-run.json')['group']['provider_instance_id']
            record('view', native_views(directory, args.port, args.display, args.xauthority))
        else:
            fault = events[0][4]['fault']
            observer.start_generation(identity, missing=fault == 'missing_subscriber',
                                      bad_identity=fault == 'bad_identity')
            if fault == 'clock_conflict':
                processes.spawn('foreign-clock', [sys.executable, '-B',
                    str(ROOT / 'tests/p5_ros_nodes.py'), 'foreign_clock'])
                observer.wait(lambda: rospy.get_param('/p5_foreign_clock/ready', False), 'rogue clock ready')
            errors = observer.audit('preflight')
            required = {'clock_conflict': 'clock_source_conflict',
                        'missing_subscriber': 'mapping_connection_missing',
                        'bad_identity': 'run_identity:/p5_map'}[fault]
            if required not in errors:
                raise ValueError('injected fault not observed: ' + fault)
            record('preflight', {'graph.accepted': not errors})
            if observer.count('/uav/map/snapshot'):
                raise ValueError('preflight rejection collected map evidence')
        manifest['python_process_audit'] = python_process_audit()
        if not manifest['python_process_audit']['passed']:
            raise ValueError('Python process environment differs')
        if observer.errors:
            raise ValueError('public receipt errors: ' + repr(observer.errors))
        manifest.update(public_counts={k: len(v) for k, v in observer.messages.items()},
                        public_bytes=observer.bytes)
    except Exception as exc:
        manifest['errors'].append(type(exc).__name__ + ': ' + str(exc))
    finally:
        if observer is not None:
            observer.close()
        cleanup = processes.cleanup()
        cleanup['ports'] = probe_ports('P5-C', args.port)
        cleanup['sentinel'] = load(directory.parent / 'sentinel.json')
        cleanup['sentinel_preserved'] = sentinel_live(cleanup['sentinel'])
        cleanup['passed'] = (cleanup['passed'] and cleanup['sentinel_preserved'] and
                             all(row['free'] for row in cleanup['ports']))
        write_json(directory / 'cleanup-audit.json', cleanup)
        record('cleanup', {'cleanup.owned_only': cleanup['passed']})
        write_json(directory / 'event-receipts.json', receipts)
        try:
            validation = verify_delivery(answers, receipts, previous_instance)
            write_json(directory / 'validation.json', validation)
            manifest['checked_values'] = validation['checked_values']
            manifest['passed'] = validation['passed'] and cleanup['passed'] and not manifest['errors']
        except ValueError as exc:
            manifest['errors'].append(str(exc))
        write_json(directory / 'manifest.json', manifest)
        print(json.dumps(dict(run=str(directory), passed=manifest['passed'], errors=manifest['errors'])), flush=True)
    return int(not manifest['passed'])


def matrix_report(ab, directory, inputs, expected):
    from p5_checkpoints import verify_receipts
    report = load(ab / 'report.json')
    if not report['passed'] or not report['full_ab_matrix']:
        raise ValueError('A/B baseline is not a complete passing run')
    sources = list((ab / 'sources').iterdir())
    if len(sources) != 9:
        raise ValueError('A/B source snapshot incomplete')
    for source in sources:
        relative = ('ros_ws/' if source.name == 'p5_combination_run.py' else 'tests/') + source.name
        if source.read_bytes() != (ROOT / relative).read_bytes():
            raise ValueError('A/B assembly source changed: ' + relative)
    results = []
    for case in inputs['cases']:
        origin = directory if case['profile'] == 'C' else ab
        child = origin / case['id']
        answer = next(c for c in expected['cases'] if c['id'] == case['id'])
        rows = load(child / 'event-receipts.json')
        if [r['event_id'] for r in rows] != [e[0] for e in expand(case, inputs['sequences'])]:
            raise ValueError('actual event coverage differs: ' + case['id'])
        if origin == ab:
            if load(child / 'inputs.json') != inputs or load(child / 'independent-expectations.json') != expected:
                raise ValueError('A/B frozen contract differs')
            validation = verify_receipts(answer, rows)
            if not load(child / 'map-replay.json')['passed']:
                raise ValueError('A/B public map replay failed')
        else:
            previous = (load(child / 'previous-run.json')['group']['provider_instance_id']
                        if case['id'] == 'S09.recover_view' else None)
            validation = verify_delivery(answer, rows, previous)
        manifest, cleanup = load(child / 'manifest.json'), load(child / 'cleanup-audit.json')
        passed = validation['passed'] and manifest['passed'] and cleanup['passed']
        results.append(dict(case_id=case['id'], passed=passed, evidence=str(child),
            events=len(rows), checkpoints=len(validation['checks']), checked_values=validation['checked_values']))
    return dict(passed=all(r['passed'] for r in results), cases=len(results),
        events=sum(r['events'] for r in results), checkpoints=sum(r['checkpoints'] for r in results),
        checked_values=sum(r['checked_values'] for r in results), results=results,
        ab_evidence_rechecked=str(ab), ab_rerun=False, source_snapshots_equal=True,
        declaration_only_lifecycle_tables=6, formal_phase5_closed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=11731)
    parser.add_argument('--ab-run', type=Path)
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--case-worker')
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--display', default=':0')
    parser.add_argument('--xauthority', default='/run/user/%d/gdm/Xauthority' % os.getuid())
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    if not 1024 <= args.port <= 65531:
        parser.error('invalid isolated port range')
    install_interrupt_handler()
    if args.case_worker:
        return run_case(args)
    inputs, expected = load_pair()
    available = [c['id'] for c in inputs['cases'] if c['profile'] == 'C']
    selected = args.cases or available
    if not selected or len(selected) != len(set(selected)) or any(c not in available for c in selected):
        parser.error('select unique frozen S09 case IDs')
    if selected == available and args.ab_run is None:
        parser.error('full delivery requires an explicit passing A/B evidence directory')
    directory = ROOT / '.runtime/runs' / ('p5-delivery-' + datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    directory.mkdir(parents=True)
    write_json(directory / 'inputs.json', inputs)
    write_json(directory / 'independent-expectations.json', expected)
    sources = directory / 'sources'
    sources.mkdir()
    for relative in ('ros_ws/p5_delivery_run.py', 'tests/p5_delivery_case.py', 'tests/p5_delivery_checks.py',
                     'ros_ws/sensor_scene_run.py', 'ros_ws/terrain_delivery_run.py',
                     'tests/check_sensor_scene_ros.py', 'tests/check_sensor_scene_figures.py',
                     'tests/check_terrain_delivery_ros.py', 'tests/terrain_rviz_capture.py'):
        shutil.copy2(ROOT / relative, sources / Path(relative).name)
    write_json(directory / 'git-state.json', dict(branch=subprocess.check_output(
        ['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        status=subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True).splitlines()))
    print(directory, flush=True)
    sentinel = subprocess.Popen([sys.executable, '-B', '-c',
        'import signal,time,sys; signal.signal(signal.SIGINT,lambda *_:sys.exit(0)); time.sleep(600)'],
        start_new_session=True)
    write_json(directory / 'sentinel.json', process_identity(sentinel.pid))
    results, errors = [], []
    try:
        for case_id in selected:
            child = directory / case_id
            child.mkdir()
            command = [sys.executable, '-B', str(Path(__file__).resolve()), '--case-worker', case_id,
                '--directory', str(child), '--port', str(args.port), '--display', args.display,
                '--xauthority', args.xauthority]
            try:
                command_run(command, child / 'supervisor.log', 260. if case_id.endswith('recover_view') else 45.)
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                errors.append(case_id + ': ' + str(exc))
            manifest = load(child / 'manifest.json')
            results.append(dict(case_id=case_id, passed=manifest['passed'], errors=manifest['errors']))
            print(json.dumps(results[-1]), flush=True)
        if selected == available and all(r['passed'] for r in results):
            write_json(directory / 'full-matrix.json', matrix_report(args.ab_run.resolve(), directory, inputs, expected))
    except Exception as exc:
        errors.append(type(exc).__name__ + ': ' + str(exc))
    finally:
        preserved = sentinel_live(load(directory / 'sentinel.json'))
        if sentinel.poll() is None:
            os.killpg(sentinel.pid, signal.SIGINT)
        sentinel.wait(timeout=5.)
        report = dict(passed=not errors and len(results) == len(selected) and all(r['passed'] for r in results)
            and preserved and sentinel.returncode == 0, results=results, errors=errors,
            sentinel_preserved=preserved, sentinel_final_exit=sentinel.returncode,
            full_matrix=(directory / 'full-matrix.json').exists())
        if report['full_matrix']:
            report['passed'] = report['passed'] and load(directory / 'full-matrix.json')['passed']
        write_json(directory / 'report.json', report)
        print(json.dumps(dict(run=str(directory), passed=report['passed'], errors=errors)), flush=True)
    return int(not report['passed'])


if __name__ == '__main__':
    sys.exit(main())
