"""Isolated, functional-level simulation training fixture; never an online input."""
import math
from sys import float_info


def _voxel_axis(position, origin, resolution):
    scaled = (position - origin) / resolution
    nearest = round(scaled)
    # Snap only float64 roundoff at integer grid boundaries, not geometric noise.
    if abs(scaled - nearest) <= 8 * float_info.epsilon * max(1., abs(scaled)):
        scaled = nearest
    return math.floor(scaled)


def _segment_voxel_indices(start, end, origin, resolution, shape):
    """Trace positive-length voxel intersections with a 3D DDA traversal."""
    if start == end:
        return ()
    delta = [end[axis] - start[axis] for axis in range(3)]
    stationary = [abs(value) <= 1e-12 for value in delta]
    entry, exit = 0., 1.
    for axis in range(3):
        low = origin[axis]
        high = low + shape[axis] * resolution[axis]
        if stationary[axis]:
            index = _voxel_axis(start[axis], low, resolution[axis])
            if not 0 <= index < shape[axis]:
                return ()
            continue
        first = (low - start[axis]) / delta[axis]
        second = (high - start[axis]) / delta[axis]
        entry = max(entry, min(first, second))
        exit = min(exit, max(first, second))
        if exit <= entry:
            return ()

    position = [start[axis] + entry * delta[axis] for axis in range(3)]
    index = []
    next_crossing = []
    crossing_step = []
    for axis in range(3):
        scaled = (position[axis] - origin[axis]) / resolution[axis]
        nearest = round(scaled)
        snap_tolerance = 8 * float_info.epsilon * max(1., abs(scaled))
        if abs(scaled - nearest) <= snap_tolerance:
            scaled = nearest
        cell = math.floor(scaled)
        if delta[axis] < -1e-12 and scaled == nearest:
            cell -= 1
        index.append(cell)
        if delta[axis] > 1e-12:
            boundary = origin[axis] + (cell + 1) * resolution[axis]
            next_crossing.append((boundary - start[axis]) / delta[axis])
            crossing_step.append(resolution[axis] / delta[axis])
        elif delta[axis] < -1e-12:
            boundary = origin[axis] + cell * resolution[axis]
            next_crossing.append((boundary - start[axis]) / delta[axis])
            crossing_step.append(-resolution[axis] / delta[axis])
        else:
            next_crossing.append(math.inf)
            crossing_step.append(math.inf)

    cells = []
    current = entry
    while current < exit:
        if any(not 0 <= index[axis] < shape[axis] for axis in range(3)):
            break
        cells.append((index[0] * shape[1] + index[1]) * shape[2] + index[2])
        crossing = min(next_crossing)
        if crossing >= exit:
            break
        tolerance = 1e-12 * max(1., abs(crossing))
        for axis in range(3):
            if abs(next_crossing[axis] - crossing) <= tolerance:
                index[axis] += 1 if delta[axis] > 1e-12 else -1
                next_crossing[axis] += crossing_step[axis]
        current = crossing
    return cells


def _transform(matrix, point):
    return [sum(matrix[4*r+c] * point[c] for c in range(3)) + matrix[4*r+3]
            for r in range(3)]


def _inverse_transform(matrix, point):
    delta = [point[i] - matrix[4*i+3] for i in range(3)]
    return [sum(matrix[4*r+c] * delta[r] for r in range(3)) for c in range(3)]


def _combine(left, right):
    return [sum(left[4*r+k]*right[4*k+c] for k in range(4))
            for r in range(4) for c in range(4)]


def _body_pose(state):
    x, y, z, w = state['orientation_xyzw']
    if (any(not math.isfinite(v) for v in (x, y, z, w, *state['position']))
            or abs(x*x+y*y+z*z+w*w-1) > 1e-3):
        raise ValueError('invalid training pose')
    rotation = [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w),
                2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w),
                2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]
    return [rotation[0], rotation[1], rotation[2], state['position'][0],
            rotation[3], rotation[4], rotation[5], state['position'][1],
            rotation[6], rotation[7], rotation[8], state['position'][2],
            0, 0, 0, 1]


def _slerp(first, second, fraction):
    first_norm = math.sqrt(sum(value*value for value in first))
    second_norm = math.sqrt(sum(value*value for value in second))
    first = [value/first_norm for value in first]
    second = [value/second_norm for value in second]
    dot = sum(a*b for a, b in zip(first, second))
    if dot < 0:
        second = [-value for value in second]
        dot = -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > 0.9995:
        value = [a + fraction*(b-a) for a, b in zip(first, second)]
    else:
        angle = math.acos(dot)
        scale = math.sin(angle)
        a_scale = math.sin((1-fraction)*angle) / scale
        b_scale = math.sin(fraction*angle) / scale
        value = [a_scale*a + b_scale*b for a, b in zip(first, second)]
    norm = math.sqrt(sum(value_i*value_i for value_i in value))
    return [value_i/norm for value_i in value]


def _state_pose_at(states, timestamp_ns, run_id, clock_id):
    if not isinstance(states, (list, tuple)) or not states:
        raise ValueError('nonzero scan requires state history')
    prior_time = None
    sample_ids = set()
    for item in states:
        item_header = item.get('header', {})
        stamp = item_header.get('timestamp')
        sample_id = item_header.get('sample_id')
        if (item_header.get('run_id') != run_id or item_header.get('clock_id') != clock_id
                or item_header.get('frame_id') != 'odom' or item_header.get('status') != 'valid'
                or item_header.get('source_type') != 'derived'
                or item.get('body_frame_id') != 'base_link'
                or item.get('state_source') != 'estimated'
                or not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids
                or type(stamp) is not int or stamp < 0
                or (prior_time is not None and stamp <= prior_time)):
            raise ValueError('invalid or unordered training pose history')
        _body_pose(item)
        sample_ids.add(sample_id)
        prior_time = stamp
    if timestamp_ns < states[0]['header']['timestamp'] or timestamp_ns > states[-1]['header']['timestamp']:
        raise ValueError('pose history does not cover acquisition time')
    for item in states:
        if item['header']['timestamp'] == timestamp_ns:
            return _body_pose(item), [item['header']['sample_id']]
    for first, second in zip(states, states[1:]):
        t0, t1 = first['header']['timestamp'], second['header']['timestamp']
        if t0 < timestamp_ns < t1:
            fraction = float(timestamp_ns-t0) / float(t1-t0)
            position = [a+fraction*(b-a) for a, b in zip(first['position'], second['position'])]
            orientation = _slerp(first['orientation_xyzw'], second['orientation_xyzw'], fraction)
            return _body_pose(dict(position=position, orientation_xyzw=orientation)), [
                first['header']['sample_id'], second['header']['sample_id']]
    raise ValueError('pose interpolation bracket missing')


def _checked_mount(values, name):
    if (len(values) != 16 or any(not isinstance(v, (int, float)) or
                                  not math.isfinite(v) for v in values) or
            values[12:] != [0, 0, 0, 1]):
        raise ValueError('invalid ' + name)
    rows = [[values[4*r+c] for c in range(3)] for r in range(3)]
    for a in range(3):
        for b in range(3):
            if abs(sum(rows[a][k]*rows[b][k] for k in range(3)) - (1 if a == b else 0)) > 1e-6:
                raise ValueError('nonrigid ' + name)
    determinant = (rows[0][0]*(rows[1][1]*rows[2][2]-rows[1][2]*rows[2][1])
                   -rows[0][1]*(rows[1][0]*rows[2][2]-rows[1][2]*rows[2][0])
                   +rows[0][2]*(rows[1][0]*rows[2][1]-rows[1][1]*rows[2][0]))
    if abs(determinant-1) > 1e-6:
        raise ValueError('improper rotation ' + name)
    return values


def _in_fov(point, sensor):
    return (point[0] > 0 and math.dist(point, [0, 0, 0]) <= sensor['max_range_m']
            and abs(math.degrees(math.atan2(point[1], point[0]))) <= sensor['fov_horizontal_deg']/2
            and abs(math.degrees(math.atan2(point[2], point[0]))) <= sensor['fov_vertical_deg']/2)


def _first_hit(origin, direction, obstacles, max_range):
    closest = None
    tolerance_m = 1e-9  # Numerical edge tolerance, not a sensor resolution.
    for obstacle in obstacles:
        center, size = obstacle['center_m'], obstacle['size_m']
        low = [c-s/2 for c, s in zip(center, size)]
        high = [c+s/2 for c, s in zip(center, size)]
        near, far = 0.0, max_range
        for axis in range(3):
            if abs(direction[axis]) < 1e-12:
                if not low[axis]+tolerance_m < origin[axis] < high[axis]-tolerance_m:
                    far = -1
                    break
                continue
            a = (low[axis]-origin[axis])/direction[axis]
            b = (high[axis]-origin[axis])/direction[axis]
            near, far = max(near, min(a, b)), min(far, max(a, b))
        if tolerance_m < near and near+tolerance_m < far and (closest is None or near < closest):
            closest = near
    return closest


def _header(state, frame, stamp, source):
    identity = state['header']
    return dict(schema_version='0.1', timestamp=stamp, run_id=identity['run_id'],
                clock_id=identity['clock_id'], sample_id=source+':'+identity['sample_id'],
                frame_id=frame, source_type='fixture', status='valid', reason='')


def build_training_sample(state, config, radar_timestamp_ns=None,
                          infrared_timestamp_ns=None, lidar_timestamp_ns=None,
                          state_history=None):
    """Construct one explicitly aligned Radar/IR pair and separate LiDAR labels."""
    schema_version = config.get('schema_version')
    if (config.get('mode') != 'training_data_generation'
            or schema_version not in ('0.1', '0.2')):
        raise ValueError('training configuration required')
    header = state['header']
    if (header['status'] != 'valid' or header['frame_id'] != 'odom'
            or header['clock_id'] != 'sim:'+header['run_id']
            or state.get('body_frame_id') != 'base_link' or state.get('state_source') != 'estimated'):
        raise ValueError('valid estimated AircraftState required')
    reference = header['timestamp'] if radar_timestamp_ns is None else radar_timestamp_ns
    ir_time = reference if infrared_timestamp_ns is None else infrared_timestamp_ns
    lidar_time = reference if lidar_timestamp_ns is None else lidar_timestamp_ns
    times = config['time']
    if (any(not isinstance(t, int) or isinstance(t, bool) or t < 0 for t in
            (reference, ir_time, lidar_time))
            or reference < header['timestamp']
            or reference-header['timestamp'] > times['max_pose_age_ns']
            or abs(ir_time-reference) > times['max_pair_offset_ns']
            or abs(lidar_time-reference) > times['max_pair_offset_ns']):
        raise ValueError('training timestamp/pose age mismatch')
    calibration = config['calibration']
    lidar = config['lidar']
    duration = lidar.get('scan_duration_ns')
    if (type(duration) is not int or duration < 0 or duration % 2 != 0
            or (duration > 0 and schema_version != '0.2')):
        raise ValueError('nonzero LiDAR scans require training record schema 0.2')
    scan_start = lidar_time - duration//2
    scan_end = scan_start + duration
    ray_offsets = lidar.get('ray_time_offsets_ns')
    if ray_offsets is None and duration == 0:
        ray_offsets = [0] * len(lidar['rays_lidar'])
    if (not isinstance(ray_offsets, list) or len(ray_offsets) != len(lidar['rays_lidar'])
            or any(type(offset) is not int or not 0 <= offset <= duration for offset in ray_offsets)
            or any(a > b for a, b in zip(ray_offsets, ray_offsets[1:]))
            or (duration > 0 and (not ray_offsets or ray_offsets[0] != 0
                                  or ray_offsets[-1] != duration))
            or (duration == 0 and any(ray_offsets))):
        raise ValueError('explicit ordered per-ray time offsets required')
    interval = [reference, ir_time, scan_start, scan_end]
    if (calibration['status'] != 'fixture_only' or not calibration['calibration_id']
            or not calibration['valid_from_ns'] <= min(interval)
            or max(interval) >= calibration['valid_until_ns']):
        raise ValueError('calibration interval mismatch')
    body = _body_pose(state)
    mounts = {key: _checked_mount(calibration['T_body_'+key], key)
              for key in ('radar', 'thermal_optical', 'training_lidar')}
    mounts['radar'] = _combine(body, mounts['radar'])
    mounts['thermal_optical'] = _combine(body, mounts['thermal_optical'])
    scene = config['scene']
    obstacles = scene['obstacles_odom']
    radar_points = []
    pixels = config['infrared']
    image = [pixels['background_fixture_intensity']] * (pixels['width']*pixels['height'])
    for obstacle in obstacles:
        center = obstacle['center_m']
        if any(s <= 0 for s in obstacle['size_m']):
            raise ValueError('invalid obstacle size')
        local = _inverse_transform(mounts['radar'], center)
        if _in_fov(local, config['radar']):
            radar_points.append(dict(x=local[0], y=local[1], z=local[2],
                                     doppler_available=False, power_available=False,
                                     obstacle_id=obstacle['obstacle_id']))
        optical = _inverse_transform(mounts['thermal_optical'], center)
        if optical[2] <= 0 or 'ir_pixel' not in obstacle:
            raise ValueError('missing or behind-camera IR correspondence')
        u = round(pixels['fx']*optical[0]/optical[2]+pixels['cx'])
        v = round(pixels['fy']*optical[1]/optical[2]+pixels['cy'])
        if ([u, v] != obstacle['ir_pixel'] or not 0 <= u < pixels['width']
                or not 0 <= v < pixels['height']):
            raise ValueError('IR projection/correspondence mismatch')
        image[v*pixels['width']+u] = pixels['hotspot_fixture_intensity']
    shape = lidar['grid_shape']
    origin = lidar['grid_origin_m']
    resolution = lidar['grid_resolution_m']
    if any(n <= 0 for n in shape) or any(v <= 0 for v in resolution):
        raise ValueError('invalid supervision grid')
    target = ['unknown'] * math.prod(shape)
    observed = [False] * len(target)
    lidar_points = []
    first_hit_odom = None
    if duration:
        if schema_version != '0.2' or state_history is None:
            raise ValueError('nonzero scan requires schema 0.2 and bracketing AircraftState history')
        history = list(state_history)
        if (len(history) < 2 or history[0]['header']['timestamp'] > scan_start
                or history[-1]['header']['timestamp'] < scan_end):
            raise ValueError('pose history must cover the complete LiDAR scan')
        reference_body, reference_state_ids = _state_pose_at(
            history, lidar_time, header['run_id'], header['clock_id'])
        lidar_pose = _combine(reference_body, mounts['training_lidar'])
        motion_method = 'linear_position_shortest_arc_slerp_to_scan_midpoint'
    else:
        history = [state]
        reference_state_ids = [header['sample_id']]
        lidar_pose = _combine(body, mounts['training_lidar'])
        motion_method = 'not_required_zero_duration'
    for ray_index, (ray, offset_ns) in enumerate(zip(lidar['rays_lidar'], ray_offsets)):
        norm = math.sqrt(sum(v*v for v in ray))
        if abs(norm-1) > 1e-6 or not _in_fov(ray, dict(lidar, max_range_m=1e9)):
            raise ValueError('ray outside declared LiDAR FOV')
        point_time = scan_start + offset_ns
        if duration:
            point_body, point_state_ids = _state_pose_at(
                history, point_time, header['run_id'], header['clock_id'])
            point_pose = _combine(point_body, mounts['training_lidar'])
        else:
            point_state_ids = reference_state_ids
            point_pose = lidar_pose
        sensor_origin = _transform(point_pose, [0, 0, 0])
        direction = [sum(point_pose[4*r+c]*ray[c] for c in range(3)) for r in range(3)]
        distance = _first_hit(sensor_origin, direction, obstacles, lidar['max_range_m'])
        if distance is None:
            continue  # no return cannot certify free space
        raw_hit = [distance*v for v in ray]
        hit = _transform(point_pose, raw_hit)
        if first_hit_odom is None:
            first_hit_odom = hit
        compensated_hit = _inverse_transform(lidar_pose, hit)
        lidar_points.append(dict(x=compensated_hit[0], y=compensated_hit[1], z=compensated_hit[2],
                                 raw_xyz=raw_hit, point_time_ns=point_time,
                                 time_offset_ns=offset_ns, ray_index=ray_index,
                                 pose_sample_ids=point_state_ids))
        ray_origin_ref = _inverse_transform(lidar_pose, sensor_origin)
        segment_length = math.dist(ray_origin_ref, compensated_hit)
        if segment_length <= 0:
            raise ValueError('degenerate compensated LiDAR ray')
        for flat in _segment_voxel_indices(ray_origin_ref, compensated_hit, origin,
                                          resolution, shape):
            if target[flat] != 'occupied':
                target[flat] = 'free'
            observed[flat] = True
        index = [_voxel_axis(compensated_hit[axis], origin[axis], resolution[axis])
                 for axis in range(3)]
        if all(0 <= index[axis] < shape[axis] for axis in range(3)):
            flat = (index[0]*shape[1]+index[1])*shape[2]+index[2]
            target[flat] = 'occupied'
            observed[flat] = True
    sample = dict(schema_version=schema_version, mode='training_data_generation',
                  scene_id=scene['scene_id'], calibration_id=calibration['calibration_id'],
                  run_id=header['run_id'], clock_id=header['clock_id'],
                  state_sample_id=header['sample_id'],
                  radar=dict(header=_header(state, 'radar', reference, 'train.radar'),
                             scan_start=reference, scan_end=reference, points=radar_points,
                             power_quantity='uncalibrated_intensity', power_unit='arbitrary',
                             doppler_reference='sensor_relative'),
                  infrared=dict(header=_header(state, 'thermal_optical', ir_time, 'train.ir'),
                                exposure_start=ir_time, exposure_end=ir_time,
                                width=pixels['width'], height=pixels['height'], image=image,
                                encoding='32FC1', value_unit='fixture_intensity',
                                camera_info=dict(width=pixels['width'], height=pixels['height'],
                                                 calibration_id=calibration['calibration_id'])),
                  lidar=dict(header=_header(state, 'training_lidar', lidar_time, 'train.lidar'),
                             scan_start=scan_start, scan_end=scan_end,
                             scan_duration_ns=duration,
                             ray_time_offsets_ns=list(ray_offsets),
                             coordinate_frame_timestamp_ns=lidar_time,
                             coordinate_semantics='deskewed_to_scan_midpoint',
                             motion_compensation_method=motion_method,
                             reference_pose_sample_ids=reference_state_ids,
                             points=lidar_points, first_hit_odom=first_hit_odom),
                  supervision=dict(frame_id='training_lidar', reference_timestamp_ns=lidar_time,
                                   grid_origin_m=origin,
                                   grid_resolution_m=resolution, grid_shape=shape,
                                   target=target, observed_mask=observed))
    validate_training_sample(sample, config)
    return sample


def validate_training_sample(sample, config):
    """Reject pairings with inconsistent provenance; do not infer free from no echo."""
    if not isinstance(sample, dict) or not isinstance(config, dict):
        raise ValueError('training record/config must be mappings')
    required_sample = ('mode', 'schema_version', 'scene_id', 'calibration_id',
                       'run_id', 'clock_id', 'state_sample_id', 'radar',
                       'infrared', 'lidar', 'supervision')
    required_config = ('scene', 'calibration', 'lidar', 'time')
    if (any(key not in sample for key in required_sample)
            or any(key not in config for key in required_config)
            or any(not isinstance(sample[key], dict)
                   for key in ('radar', 'infrared', 'lidar', 'supervision'))
            or not isinstance(config['scene'], dict)
            or not isinstance(config['calibration'], dict)
            or not isinstance(config['lidar'], dict)
            or not isinstance(config['time'], dict)):
        raise ValueError('training record/config structure incomplete')
    required_sections = {
        'radar': ('header', 'scan_start', 'scan_end', 'points'),
        'infrared': ('header', 'exposure_start', 'exposure_end'),
        'lidar': ('header', 'scan_start', 'scan_end', 'scan_duration_ns',
                  'coordinate_frame_timestamp_ns', 'coordinate_semantics',
                  'motion_compensation_method', 'reference_pose_sample_ids', 'points'),
        'supervision': ('reference_timestamp_ns', 'frame_id', 'grid_shape',
                        'grid_origin_m', 'grid_resolution_m', 'target', 'observed_mask'),
    }
    if any(any(key not in sample[section] for key in keys)
           for section, keys in required_sections.items()):
        raise ValueError('training record section incomplete')
    if (not all(isinstance(sample[key], str) and sample[key]
                for key in ('schema_version', 'scene_id', 'calibration_id',
                            'run_id', 'clock_id', 'state_sample_id'))):
        raise ValueError('training record identity fields invalid')
    if (sample['mode'] != 'training_data_generation'
            or sample['schema_version'] != config.get('schema_version')
            or sample['schema_version'] not in ('0.1', '0.2')
            or sample['scene_id'] != config['scene']['scene_id']
            or sample['calibration_id'] != config['calibration']['calibration_id']
            or sample['clock_id'] != 'sim:'+sample['run_id']):
        raise ValueError('training record identity mismatch')
    for kind, frame in (('radar', 'radar'), ('infrared', 'thermal_optical'),
                        ('lidar', 'training_lidar')):
        header = sample[kind].get('header')
        if (not isinstance(header, dict)
                or any(key not in header for key in
                       ('timestamp', 'run_id', 'clock_id', 'sample_id',
                        'frame_id', 'source_type', 'status'))
                or (kind in ('radar', 'lidar')
                    and not isinstance(sample[kind].get('points'), list))):
            raise ValueError(kind+' record structure invalid')
        if (header['run_id'] != sample['run_id'] or header['clock_id'] != sample['clock_id']
                or header['frame_id'] != frame or header['status'] != 'valid'
                or header['source_type'] != 'fixture'
                or header['sample_id'] != 'train.'+({'infrared':'ir'}.get(kind, kind))+':'+sample['state_sample_id']):
            raise ValueError(kind+' header identity mismatch')
    radar = sample['radar']['header']['timestamp']
    ir = sample['infrared']['header']['timestamp']
    lidar = sample['lidar']['header']['timestamp']
    duration = config['lidar']['scan_duration_ns']
    expected_motion_method = ('not_required_zero_duration' if duration == 0 else
                              'linear_position_shortest_arc_slerp_to_scan_midpoint')
    scan_start = lidar-duration//2
    scan_end = scan_start+duration
    if (sample['radar']['scan_start'] != radar or sample['radar']['scan_end'] != radar
            or sample['infrared']['exposure_start'] != ir or sample['infrared']['exposure_end'] != ir
            or sample['lidar']['scan_start'] != scan_start or sample['lidar']['scan_end'] != scan_end
            or sample['lidar']['scan_duration_ns'] != duration
            or sample['lidar']['coordinate_frame_timestamp_ns'] != lidar
            or sample['supervision']['reference_timestamp_ns'] != lidar
            or sample['lidar']['coordinate_semantics'] != 'deskewed_to_scan_midpoint'
            or sample['lidar']['motion_compensation_method'] != expected_motion_method
            or not sample['lidar']['reference_pose_sample_ids']
            or abs(ir-radar) > config['time']['max_pair_offset_ns']
            or abs(lidar-radar) > config['time']['max_pair_offset_ns']):
        raise ValueError('training acquisition time mismatch')
    ray_offsets = config['lidar'].get('ray_time_offsets_ns', [0] * len(config['lidar']['rays_lidar']))
    recorded_offsets = sample['lidar'].get('ray_time_offsets_ns')
    if recorded_offsets is None and sample['schema_version'] == '0.1':
        recorded_offsets = [0] * len(config['lidar']['rays_lidar'])
    if (not isinstance(recorded_offsets, list)
            or recorded_offsets != ray_offsets
            or len(recorded_offsets) != len(config['lidar']['rays_lidar'])
            or any(type(offset) is not int or not 0 <= offset <= duration
                   for offset in recorded_offsets)
            or any(a > b for a, b in zip(recorded_offsets, recorded_offsets[1:]))
            or (duration > 0 and (not recorded_offsets or recorded_offsets[0] != 0
                                  or recorded_offsets[-1] != duration))
            or (duration == 0 and any(recorded_offsets))):
        raise ValueError('training ray time contract mismatch')
    seen_ray_indices = set()
    for point in sample['lidar']['points']:
        if not isinstance(point, dict):
            raise ValueError('training point record must be a mapping')
        index = point.get('ray_index')
        if (type(index) is not int or not 0 <= index < len(config['lidar']['rays_lidar'])
                or index in seen_ray_indices
                or point.get('point_time_ns') != scan_start+recorded_offsets[index]
                or point.get('time_offset_ns') != recorded_offsets[index]
                or (not isinstance(point.get('pose_sample_ids'), list)
                    or not all(isinstance(sample_id, str) and sample_id
                               for sample_id in point['pose_sample_ids']))
                or not isinstance(point.get('raw_xyz'), list) or len(point['raw_xyz']) != 3
                or any(not isinstance(value, (int, float)) or not math.isfinite(value)
                       for value in point['raw_xyz']+[point.get('x'), point.get('y'), point.get('z')])):
            raise ValueError('training per-point time or coordinate record invalid')
        seen_ray_indices.add(index)
    grid = sample['supervision']
    if (any(key not in grid for key in
            ('frame_id', 'grid_shape', 'grid_origin_m', 'grid_resolution_m',
             'target', 'observed_mask'))
            or not isinstance(grid.get('target'), list)
            or not isinstance(grid.get('observed_mask'), list)):
        raise ValueError('training target/mask structure invalid')
    if (grid['frame_id'] != 'training_lidar' or grid['grid_shape'] != config['lidar']['grid_shape']
            or grid['grid_origin_m'] != config['lidar']['grid_origin_m']
            or grid['grid_resolution_m'] != config['lidar']['grid_resolution_m']
            or len(grid['target']) != math.prod(grid['grid_shape'])
            or len(grid['target']) != len(grid['observed_mask'])
            or any(type(mask) is not bool for mask in grid['observed_mask'])
            or any((t == 'unknown') == bool(m) for t, m in zip(grid['target'], grid['observed_mask']))
            or set(grid['target']) - {'free', 'occupied', 'unknown'}):
        raise ValueError('training target/mask invalid')
    return True
