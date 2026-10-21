"""Offline known-scene acceptance: records, geometry and coverage statistics."""
import argparse
import copy
import datetime
import json
import math
from pathlib import Path
import shutil
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
for directory in ('simulation', 'sensors'):
    sys.path.insert(0, str(ROOT / directory))

from ufm_simulation.perf01a_fixture import make_scan_motion_state
from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.training_stream import TrainingScanBuffer
from ufm_sensors.training_supervision import validate_training_sample


def build_case(case, plan, root=ROOT, run_id=None):
    config = yaml.safe_load((root / plan['base_config']).read_text())
    config['scene']['scene_id'] = 'sens_train_matrix:' + case['case_id']
    obstacles = config['scene']['obstacles_odom']
    geometry = case['geometry']
    if geometry == 'single':
        del obstacles[1:]
    elif geometry == 'empty':
        obstacles.clear()
    elif geometry == 'near':
        obstacles[0]['center_m'][1] = 4.
        obstacles[1]['center_m'][:2] = [-.6, 4.]
    elif geometry == 'occluded':
        obstacles.append(dict(obstacle_id='hidden_box', center_m=[0., 7.5, .2],
                              size_m=[.5, .5, .5], ir_pixel=[2, 1]))
    elif geometry == 'voxel_coverage':
        obstacles.clear()
        slope = case['ray_slope']
        norm = math.sqrt(1. + slope * slope)
        reference = plan['anchor_timestamp_ns']
        mount = config['calibration']['T_body_training_lidar']
        lidar_origin, body_rotation = _pose(case, plan, reference, mount)
        center_range = case['obstacle_center_range_m']
        center_local = [center_range / norm, center_range * slope / norm, 0.]
        center = _world_point(center_local, lidar_origin, body_rotation)
        camera_mount = config['calibration']['T_body_thermal_optical']
        camera_origin, _ = _pose(case, plan, reference, camera_mount)
        camera_local = _local_point(center, camera_origin, body_rotation)
        optical = [-camera_local[1], -camera_local[2], camera_local[0]]
        pixels = config['infrared']
        ir_pixel = [round(pixels['fx'] * optical[0] / optical[2] + pixels['cx']),
                    round(pixels['fy'] * optical[1] / optical[2] + pixels['cy'])]
        obstacles.append(dict(obstacle_id='voxel_coverage_box', center_m=center,
                              size_m=list(case['obstacle_size_m']), ir_pixel=ir_pixel))
    elif geometry != 'two':
        raise ValueError('unknown scene geometry: ' + geometry)
    if 'forward_center_z_m' in case:
        obstacles[0]['center_m'][2] = case['forward_center_z_m']
    config['lidar']['ray_time_offsets_ns'] = list(plan['ray_time_offsets_ns'])
    config['lidar']['rays_lidar'] = copy.deepcopy(case.get('lidar_rays_lidar', plan['rays_lidar']))
    config['lidar']['max_range_m'] = case.get('lidar_range_m', config['lidar']['max_range_m'])
    config['lidar']['fov_vertical_deg'] = case.get('lidar_vertical_fov_deg',
                                                 config['lidar']['fov_vertical_deg'])
    references = plan['reference_timestamps_ns']
    half = config['lidar']['scan_duration_ns'] // 2
    stamps = sorted({stamp + offset for stamp in references for offset in (-half, 0, half)})
    run_id = run_id or 'sens-train-matrix:' + case['case_id']
    states = [make_scan_motion_state(run_id, sequence, stamp, plan['anchor_timestamp_ns'],
                                     case['speed_mps'], case['yaw_rate_deg_s'])
              for sequence, stamp in enumerate(stamps)]
    buffer = TrainingScanBuffer(run_id, config, references)
    rows = []
    for state in states:
        rows.extend(buffer.advance_clock(state['header']['timestamp']))
        rows.extend(buffer.push_state(adapt_state(state, {
            'odom_origin_policy': 'px4_estimator_local_origin',
            'body_origin_policy': 'source_body_virtual_flu',
        })))
    buffer.finish()
    return config, states, rows


def _pose(case, plan, timestamp, mount):
    elapsed = (timestamp - plan['anchor_timestamp_ns']) / 1e9
    yaw = math.radians(case['yaw_rate_deg_s']) * elapsed
    sine, cosine = math.sin(yaw), math.cos(yaw)
    rotation = [[sine, -cosine, 0.], [cosine, sine, 0.], [0., 0., 1.]]
    origin = [sine * mount[3] - cosine * mount[7],
              case['speed_mps'] * elapsed + cosine * mount[3] + sine * mount[7], mount[11]]
    return origin, rotation


def _world_point(local, origin, rotation):
    return [origin[axis] + sum(rotation[axis][j] * local[j] for j in range(3))
            for axis in range(3)]


def _local_point(world, origin, rotation):
    return [sum(rotation[axis][j] * (world[axis] - origin[axis]) for axis in range(3))
            for j in range(3)]


def _entry_face_hit(origin, direction, obstacles, max_range):
    # Independent face-plane intersection oracle, not the producer's slab interval code.
    candidates = []
    for obstacle in obstacles:
        low = [c - size / 2 for c, size in zip(obstacle['center_m'], obstacle['size_m'])]
        high = [c + size / 2 for c, size in zip(obstacle['center_m'], obstacle['size_m'])]
        for axis in range(3):
            if abs(direction[axis]) < 1e-12:
                continue
            face = low[axis] if direction[axis] > 0 else high[axis]
            distance = (face - origin[axis]) / direction[axis]
            hit = [origin[j] + distance * direction[j] for j in range(3)]
            if (0 < distance < max_range and all(low[j] + 1e-9 < hit[j] < high[j] - 1e-9
                                                 for j in range(3) if j != axis)):
                candidates.append((distance, hit))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def _source_ids(states, timestamp):
    for state in states:
        if state['header']['timestamp'] == timestamp:
            return ['sensors.state:' + state['header']['sample_id']]
    for first, second in zip(states, states[1:]):
        if first['header']['timestamp'] < timestamp < second['header']['timestamp']:
            return ['sensors.state:' + item['header']['sample_id'] for item in (first, second)]
    raise ValueError('oracle state history does not cover acquisition')


def _summary(values):
    if not values:
        return dict(count=0, mean=None, p95=None, max=None)
    ordered = sorted(values)
    return dict(count=len(values), mean=sum(values) / len(values),
                p95=ordered[math.ceil(.95 * len(values)) - 1], max=ordered[-1])


def _expected_free_cells(origin, hit, grid, tolerance):
    """Sample independently intersected pre-echo cells, away from moving grid faces."""
    delta = [hit[i] - origin[i] for i in range(3)]
    length = math.dist(origin, hit)
    spacing = min(grid['grid_resolution_m']) / 4
    result = set()
    for step in range(1, math.ceil(length / spacing)):
        distance = step * spacing
        if distance >= length:
            break
        point = [origin[i] + distance * delta[i] / length for i in range(3)]
        index = []
        for axis in range(3):
            scaled = (point[axis] - grid['grid_origin_m'][axis]) / grid['grid_resolution_m'][axis]
            nearest = round(scaled)
            if abs(scaled - nearest) * grid['grid_resolution_m'][axis] <= tolerance:
                if abs(delta[axis]) > tolerance:
                    break  # A moving ray too close to a grid face has an ambiguous cell.
                scaled = nearest  # A ray lying on a fixed face belongs to its upper cell.
            index.append(math.floor(scaled))
        if len(index) == 3 and all(0 <= index[axis] < grid['grid_shape'][axis]
                                   for axis in range(3)):
            result.add((index[0] * grid['grid_shape'][1] + index[1]) * grid['grid_shape'][2] + index[2])
    return result


def _segment_intersects_cell(start, end, cell, tolerance):
    """Clip a reference-frame echo segment to a voxel, with numerical slack."""
    entry, exit = 0., 1.
    for axis, (low, high) in enumerate(cell):
        delta = end[axis] - start[axis]
        if abs(delta) < 1e-12:
            if start[axis] < low - tolerance or start[axis] > high + tolerance:
                return False
            continue
        a = (low - tolerance - start[axis]) / delta
        b = (high + tolerance - start[axis]) / delta
        entry, exit = max(entry, min(a, b)), min(exit, max(a, b))
        if entry > exit:
            return False
    return entry <= exit


def _positive_length_voxel_cells(start, end, grid):
    """Enumerate voxels with positive-length segment overlap, independently of sampling."""
    if start == end:
        return set()
    shape = grid['grid_shape']
    origin = grid['grid_origin_m']
    resolution = grid['grid_resolution_m']
    delta = [end[axis] - start[axis] for axis in range(3)]
    cells = set()
    for x in range(shape[0]):
        for y in range(shape[1]):
            for z in range(shape[2]):
                index = (x, y, z)
                entry, exit = 0., 1.
                for axis in range(3):
                    if abs(delta[axis]) <= 1e-12:
                        # A segment lying on a grid face follows floor's upper-side convention.
                        if math.floor((start[axis] - origin[axis]) / resolution[axis]) != index[axis]:
                            break
                        continue
                    low = origin[axis] + index[axis] * resolution[axis]
                    high = low + resolution[axis]
                    first = (low - start[axis]) / delta[axis]
                    second = (high - start[axis]) / delta[axis]
                    entry = max(entry, min(first, second))
                    exit = min(exit, max(first, second))
                    if exit - entry <= 1e-12:
                        break
                else:
                    if exit > 0. and entry < 1. and exit - entry > 1e-12:
                        cells.add((x * shape[1] + y) * shape[2] + z)
    return cells


def _input_oracle(row, case, plan, config):
    reference = row['radar']['header']['timestamp']
    calibration = config['calibration']
    radar_origin, body_rotation = _pose(case, plan, reference, calibration['T_body_radar'])
    camera_mount = calibration['T_body_thermal_optical']
    if [camera_mount[i] for i in (0, 1, 2, 4, 5, 6, 8, 9, 10)] != [0, 0, 1, -1, 0, 0, 0, -1, 0]:
        raise ValueError('unsupported analytic optical mount')
    camera_origin, _ = _pose(case, plan, reference, camera_mount)
    expected_radar = []
    pixels = config['infrared']
    image = [pixels['background_fixture_intensity']] * (pixels['width'] * pixels['height'])
    for obstacle in config['scene']['obstacles_odom']:
        local = _local_point(obstacle['center_m'], radar_origin, body_rotation)
        radar = config['radar']
        if (local[0] > 0 and math.dist(local, [0., 0., 0.]) <= radar['max_range_m']
                and abs(math.degrees(math.atan2(local[1], local[0]))) <= radar['fov_horizontal_deg'] / 2
                and abs(math.degrees(math.atan2(local[2], local[0]))) <= radar['fov_vertical_deg'] / 2):
            expected_radar.append((obstacle['obstacle_id'], local))
        body = _local_point(obstacle['center_m'], camera_origin, body_rotation)
        optical = [-body[1], -body[2], body[0]]
        if optical[2] <= 0:
            raise ValueError('scene oracle obstacle behind camera')
        u = round(pixels['fx'] * optical[0] / optical[2] + pixels['cx'])
        v = round(pixels['fy'] * optical[1] / optical[2] + pixels['cy'])
        if ([u, v] != obstacle['ir_pixel'] or not 0 <= u < pixels['width'] or not 0 <= v < pixels['height']):
            raise ValueError('scene oracle IR correspondence mismatch')
        image[v * pixels['width'] + u] = pixels['hotspot_fixture_intensity']
    if len(row['radar']['points']) != len(expected_radar):
        raise ValueError('scene radar count mismatch')
    for point, (obstacle_id, local) in zip(row['radar']['points'], expected_radar):
        error = math.dist([point[axis] for axis in ('x', 'y', 'z')], local)
        if (point['obstacle_id'] != obstacle_id or point['doppler_available'] or point['power_available']
                or not math.isfinite(error) or error > plan['numerical_tolerance_m']):
            raise ValueError('scene radar geometry or provenance mismatch')
    infrared = row['infrared']
    if (infrared['image'] != image or infrared['width'] != pixels['width']
            or infrared['height'] != pixels['height'] or infrared['encoding'] != '32FC1'
            or infrared['value_unit'] != 'fixture_intensity'
            or infrared['camera_info']['calibration_id'] != calibration['calibration_id']):
        raise ValueError('scene IR pixel or calibration mismatch')


def audit_case(case, plan, config, states, rows, run_id=None):
    references = plan['reference_timestamps_ns']
    run_id = run_id or 'sens-train-matrix:' + case['case_id']
    if len(rows) != len(references):
        raise ValueError('scene record count mismatch')
    for sequence, source in enumerate(states):
        header = source['header']
        expected = make_scan_motion_state(run_id, sequence, header['timestamp'],
                                          plan['anchor_timestamp_ns'], case['speed_mps'], case['yaw_rate_deg_s'])
        if source != expected or (sequence and header['timestamp'] <= states[sequence - 1]['header']['timestamp']):
            raise ValueError('scene source identity, pose or order mismatch')
    labels = dict(free=0, occupied=0, unknown=0)
    raw_errors, compensated_errors = [], []
    echo_count = interpolated = ray_slots = occlusion_checks = 0
    mount = config['calibration']['T_body_training_lidar']
    if [mount[i] for i in (0, 1, 2, 4, 5, 6, 8, 9, 10)] != [1, 0, 0, 0, 1, 0, 0, 0, 1]:
        raise ValueError('this analytic matrix requires the declared translation-only mount')
    for row, reference in zip(rows, references):
        validate_training_sample(row, config)
        _input_oracle(row, case, plan, config)
        lidar, grid = row['lidar'], row['supervision']
        if (row['run_id'] != run_id or row['clock_id'] != 'sim:' + run_id
                or row['state_sample_id'] != _source_ids(states, reference)[0]
                or any(row[kind]['header']['timestamp'] != reference for kind in ('radar', 'infrared', 'lidar'))
                or lidar['reference_pose_sample_ids'] != _source_ids(states, reference)):
            raise ValueError('scene midpoint or state identity mismatch')
        origin_mid, rotation_mid = _pose(case, plan, reference, mount)
        expected = {}
        for ray_index, (ray, offset) in enumerate(zip(config['lidar']['rays_lidar'], lidar['ray_time_offsets_ns'])):
            acquisition = lidar['scan_start'] + offset
            origin, rotation = _pose(case, plan, acquisition, mount)
            direction = [sum(rotation[axis][j] * ray[j] for j in range(3)) for axis in range(3)]
            hit = _entry_face_hit(origin, direction, config['scene']['obstacles_odom'],
                                  config['lidar']['max_range_m'])
            if hit is not None:
                expected[ray_index] = (acquisition, origin, rotation, hit)
        if [point['ray_index'] for point in lidar['points']] != list(expected):
            raise ValueError('scene first-echo/no-echo oracle mismatch')
        occupied = set()
        free_candidates = set()
        echo_segments = []
        for point in lidar['points']:
            acquisition, origin, rotation, hit = expected[point['ray_index']]
            if point['pose_sample_ids'] != _source_ids(states, acquisition):
                raise ValueError('scene per-point pose identity mismatch')
            raw_errors.append(math.dist(_world_point(point['raw_xyz'], origin, rotation), hit))
            local = [point[axis] for axis in ('x', 'y', 'z')]
            compensated_errors.append(math.dist(_world_point(local, origin_mid, rotation_mid), hit))
            interpolated += len(point['pose_sample_ids']) == 2
            expected_local = _local_point(hit, origin_mid, rotation_mid)
            reference_origin = _local_point(origin, origin_mid, rotation_mid)
            free_candidates.update(_expected_free_cells(
                reference_origin, expected_local, grid, plan['numerical_tolerance_m']))
            echo_segments.append((reference_origin, expected_local))
            index = [math.floor((value - grid['grid_origin_m'][axis]) / grid['grid_resolution_m'][axis])
                     for axis, value in enumerate(expected_local)]
            if all(0 <= index[axis] < grid['grid_shape'][axis] for axis in range(3)):
                occupied.add((index[0] * grid['grid_shape'][1] + index[1]) * grid['grid_shape'][2] + index[2])
        if plan.get('voxel_coverage_oracle') == 'positive_length':
            expected_coverage = set()
            expected_free = set()
            for start, end in echo_segments:
                traversed = _positive_length_voxel_cells(start, end, grid)
                expected_coverage.update(traversed)
                expected_free.update(traversed)
            expected_free.difference_update(occupied)
            expected_coverage.update(occupied)
            actual_coverage = {index for index, value in enumerate(grid['observed_mask']) if value}
            actual_free = {index for index, value in enumerate(grid['target']) if value == 'free'}
            if (actual_coverage != expected_coverage or actual_free != expected_free):
                raise ValueError('scene complete positive-length voxel coverage oracle mismatch')
        if {i for i, value in enumerate(grid['target']) if value == 'occupied'} != occupied:
            raise ValueError('scene occupied endpoint oracle mismatch')
        if any(grid['target'][flat] != 'free' or grid['observed_mask'][flat] is not True
               for flat in free_candidates - occupied):
            raise ValueError('scene pre-echo free coverage oracle mismatch')
        for flat, label in enumerate(grid['target']):
            if label != 'free':
                continue
            x, remainder = divmod(flat, grid['grid_shape'][1] * grid['grid_shape'][2])
            y, z = divmod(remainder, grid['grid_shape'][2])
            cell = [(grid['grid_origin_m'][axis] + index * grid['grid_resolution_m'][axis],
                     grid['grid_origin_m'][axis] + (index + 1) * grid['grid_resolution_m'][axis])
                    for axis, index in enumerate((x, y, z))]
            if not any(_segment_intersects_cell(start, end, cell, plan['numerical_tolerance_m'])
                       for start, end in echo_segments):
                raise ValueError('scene free label outside all observed echo rays')
        if not expected and (any(grid['observed_mask']) or set(grid['target']) != {'unknown'}):
            raise ValueError('scene no-echo coverage must remain entirely unknown')
        if case['geometry'] == 'occluded':
            hidden = _local_point([0., 7.5, .2], origin_mid, rotation_mid)
            index = [math.floor((value - grid['grid_origin_m'][axis]) / grid['grid_resolution_m'][axis])
                     for axis, value in enumerate(hidden)]
            flat = (index[0] * grid['grid_shape'][1] + index[1]) * grid['grid_shape'][2] + index[2]
            if grid['target'][flat] != 'unknown' or grid['observed_mask'][flat]:
                raise ValueError('scene occluded obstacle must remain unknown')
            occlusion_checks += 1
        for value in grid['target']:
            labels[value] += 1
        echo_count += len(lidar['points'])
        ray_slots += len(lidar['ray_time_offsets_ns'])
    if any(not math.isfinite(error) or error > plan['numerical_tolerance_m']
           for error in raw_errors + compensated_errors):
        raise ValueError('scene raw-coordinate or compensation error exceeds numerical tolerance')
    return dict(case_id=case['case_id'], run_id=run_id, geometry=case['geometry'],
                speed_mps=case['speed_mps'], yaw_rate_deg_s=case['yaw_rate_deg_s'],
                sample_count=len(rows), ray_slot_count=ray_slots, echo_count=echo_count,
                radar_ir_oracle_count=len(rows),
                no_echo_slot_count=ray_slots - echo_count, interpolated_echo_count=interpolated,
                label_counts=labels, observed_fraction=(labels['free'] + labels['occupied']) / sum(labels.values()),
                occlusion_unknown_checks=occlusion_checks,
                complete_voxel_coverage_checked=plan.get('voxel_coverage_oracle') == 'positive_length',
                raw_coordinate_error_m=_summary(raw_errors), compensation_error_m=_summary(compensated_errors))


def _write_jsonl(path, values):
    with path.open('x', encoding='utf-8') as handle:
        for value in values:
            handle.write(json.dumps(value, allow_nan=False) + '\n')


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run_suite(matrix_path, output, root=ROOT):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(str(matrix_path), str(output / 'matrix.yaml'))
    plan = yaml.safe_load((output / 'matrix.yaml').read_text())
    report = dict(schema_version='sens_train_scene_report_v1', execution_mode='offline_fixture',
                  passed=False, errors=[], cases=[], case_count=0, sample_count=0, python=sys.executable,
                  run_id=output.name,
                  hardware_validated=False, model_quality_validated=False, formal_perf_validated=False)
    try:
        for case in plan['cases']:
            run_id = output.name + ':' + case['case_id']
            config, states, rows = build_case(case, plan, root, run_id=run_id)
            folder = output / case['case_id']
            folder.mkdir(exist_ok=False)
            with (folder / 'config.yaml').open('x', encoding='utf-8') as handle:
                yaml.safe_dump(config, handle, sort_keys=False)
            _write_jsonl(folder / 'states.jsonl', states)
            _write_jsonl(folder / 'training-records.jsonl', rows)
            saved_config = yaml.safe_load((folder / 'config.yaml').read_text())
            report['cases'].append(audit_case(case, plan, saved_config, _read_jsonl(folder / 'states.jsonl'),
                                             _read_jsonl(folder / 'training-records.jsonl'), run_id=run_id))
            report['case_count'] = len(report['cases'])
            report['sample_count'] = sum(item['sample_count'] for item in report['cases'])
        report['case_count'] = len(report['cases'])
        report['sample_count'] = sum(case['sample_count'] for case in report['cases'])
        report['label_counts'] = {label: sum(case['label_counts'][label] for case in report['cases'])
                                  for label in ('free', 'occupied', 'unknown')}
        report['observed_fraction'] = (report['label_counts']['free'] + report['label_counts']['occupied']) / sum(report['label_counts'].values())
        report['passed'] = True
    except Exception as error:
        report['errors'].append('%s: %s' % (type(error).__name__, error))
    with (output / 'report.json').open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--matrix', type=Path, default=ROOT / 'configs/sens_train_01_scene_matrix.yaml')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if sys.executable != '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python':
        raise RuntimeError('Radar-Diffusion Python required')
    output = args.output or ROOT / '.runtime/runs' / ('sens-train-scenes-' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
    report = run_suite(args.matrix, output)
    print(json.dumps(dict(run=str(output), passed=report['passed'], cases=report.get('case_count', 0),
                          samples=report.get('sample_count', 0), errors=report['errors'])))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
