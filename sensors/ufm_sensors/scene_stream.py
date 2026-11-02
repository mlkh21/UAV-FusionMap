"""Explicit mounts and bounded pairing for the independent Gazebo sensor scene."""
import collections
import copy
import math

from .perf01a_fixture import fixture_spatial_context


def validate_scene_profile(profile):
    if (profile['schema_version'] != 'sensor_scene_fixture.v1' or
            profile['calibration_id'] != 'gazebo_sensor_scene_mount_v1' or
            profile['world_to_odom_registration'] != 'gazebo_scene_world_enu_identity_v1'):
        raise ValueError('explicit scene calibration and registration required')
    if profile['infrared']['value_unit'] != 'fixture_intensity':
        raise ValueError('IR scene values are not radiometric temperature')
    if profile['thermal_optical_xyzw'] != [-.5, .5, -.5, .5]:
        raise ValueError('explicit camera optical axes required')
    for name in ('radar_mount_xyz', 'thermal_mount_xyz'):
        if len(profile[name]) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in profile[name]):
            raise ValueError('invalid mount translation')
    radar = profile['radar']
    if 'measurement_model' in radar:
        if radar['measurement_model'] != 'parameterized_v1':
            raise ValueError('unknown scene Radar measurement model')
        for key, lower, upper in (('detection_probability',0,1),('detection_distance_m',.01,10000),
                ('range_std_m',0,2),('angle_std_rad',0,.05),('doppler_std_mps',0,5)):
            v=radar[key]
            if type(v) not in (int,float) or not math.isfinite(v) or not lower <= v <= upper:
                raise ValueError('invalid Radar parameter: '+key)
        for key, lower, upper in (('noise_seed',0,4294967295),('max_points',1,4096)):
            if type(radar[key]) is not int or not lower <= radar[key] <= upper:
                raise ValueError('invalid Radar integer: '+key)


def scene_context(state, stamp, run_id, profile):
    validate_scene_profile(profile)
    context = fixture_spatial_context(state, stamp, run_id, profile['calibration_id'])
    body = context['T_mapping_body']
    transform = list(body)
    for axis in range(3):
        transform[axis * 4 + 3] += sum(body[axis * 4 + col] * profile['radar_mount_xyz'][col]
                                              for col in range(3))
    context['T_mapping_source'] = transform
    return context


class SceneStream:
    def __init__(self, run_id, profile, require_exact_pose=False):
        validate_scene_profile(profile)
        if type(require_exact_pose) is not bool:
            raise ValueError('exact pose policy must be bool')
        self.require_exact_pose = require_exact_pose
        self.run_id, self.profile = run_id, copy.deepcopy(profile)
        self.states = collections.deque(maxlen=200)
        self.infrared = collections.deque(maxlen=8)
        self.radar = collections.OrderedDict()
        self.clock = None
        self.last_stamp = -1
        self.failed = False
        self.rejected = collections.Counter()

    def set_clock(self, stamp):
        if self.clock is not None and stamp < self.clock:
            self.failed = True
            self.radar.clear()
        self.clock = stamp

    def add(self, kind, value):
        header = value['header']
        if header['run_id'] != self.run_id or header['clock_id'] != 'sim:' + self.run_id:
            raise ValueError('scene input identity or status mismatch')
        if (kind == 'state' and header['frame_id'] == 'odom' and value['state_source'] == 'ground_truth'
                and header['status'] == 'unavailable' and header['reason'].startswith('terminal:')):
            self.failed = True
            self.radar.clear()
            self.infrared.clear()
            self.states.clear()
            self.rejected['terminal'] += 1
            return
        if header['status'] != 'valid':
            raise ValueError('scene input identity or status mismatch')
        if self.failed:
            self.rejected['locked'] += 1
            return
        if kind == 'state':
            if header['frame_id'] != 'odom' or value['state_source'] != 'ground_truth':
                raise ValueError('scene requires declared ground truth odom state')
            self.states.append(value)
        elif kind == 'infrared':
            if (header['frame_id'] != 'thermal_optical' or value['value_unit'] != 'fixture_intensity' or
                    value['camera_info']['calibration_id'] != self.profile['calibration_id']):
                raise ValueError('scene IR calibration mismatch')
            self.infrared.append(value)
        elif kind == 'radar':
            if header['frame_id'] != 'radar':raise ValueError('scene Radar frame mismatch')
            if header['timestamp'] <= self.last_stamp:
                self.rejected['old_radar'] += 1
                return
            self.radar[header['timestamp']] = value
            while len(self.radar) > 30:
                self.radar.popitem(last=False)
                self.rejected['pending_capacity'] += 1
        else:raise ValueError('unknown scene stream')

    def ready(self):
        if self.failed or self.clock is None:return []
        result = []
        for stamp, radar in sorted(list(self.radar.items())):
            if stamp > self.clock:continue
            if stamp <= self.last_stamp or self.clock - stamp > 40_000_000:
                self.rejected['old_radar' if stamp <= self.last_stamp else 'pair_timeout'] += 1
                del self.radar[stamp]
                continue
            candidates = [ir for ir in self.infrared if abs(ir['header']['timestamp'] - stamp) <= 5_000_000]
            states = [s for s in self.states if 0 <= stamp - s['header']['timestamp'] <= 10_000_000]
            if self.require_exact_pose:
                states = [s for s in states if s['header']['timestamp'] == stamp]
            if candidates and states:
                infrared = min(candidates, key=lambda ir:(abs(ir['header']['timestamp'] - stamp), ir['header']['timestamp']))
                state = max(states, key=lambda s:s['header']['timestamp'])
                context = scene_context(state, stamp, self.run_id, self.profile)
                header = dict(radar['header'], source_type='derived',
                              sample_id='sensors.bundle:' + radar['header']['sample_id'])
                result.append(dict(header=header, radar=radar, infrared=infrared, state=state,
                    calibration_id=self.profile['calibration_id'], context=context,
                    radar_ir_delta_ns=abs(infrared['header']['timestamp'] - stamp),
                    pose_age_ns=stamp - state['header']['timestamp']))
                self.last_stamp = stamp
                del self.radar[stamp]
        return result
