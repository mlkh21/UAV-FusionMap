"""Explicit bounded offline profile and raw FDM input validation, without conversion."""
from fractions import Fraction
import json
from pathlib import Path

from . import contract as c


def load_json(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('scene_json_size')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('scene_json_duplicate_key')
            result[key] = value
        return result
    try:
        value = json.loads(path.read_text(), object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('scene_json_nonfinite')))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('scene_json_encoding_or_depth') from exc
    remaining = [8192]
    def walk(item, depth):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 16:
            raise ValueError('scene_json_structure')
        if type(item) is dict:
            if len(item) > 64:
                raise ValueError('scene_json_object')
            for key, child in item.items():
                c.text(key)
                walk(child, depth + 1)
        elif type(item) is list:
            if len(item) > 512:
                raise ValueError('scene_json_list')
            for child in item:
                walk(child, depth + 1)
        elif type(item) is str:
            c.text(item, empty=True, limit=2048)
        elif item is not None and type(item) is not bool:
            c.number(item)
    walk(value, 0)
    return value


def validate_profile(value):
    fixed = dict(schema_version='sim_scene_motion_fixture.v1', fixture_only=True, mode='jsbsim_scene_truth',
        registration_id=c.REGISTRATION, body_origin_policy='jsbsim_cg_virtual_flu_v1', step_ns=c.STEP_NS,
        gazebo_step_ns=1_000_000, capture_period_steps=c.CAPTURE_STEPS, duration_steps=250,
        initial_forward_speed_mps=5.0, scene_anchor_m=[0.0, 0.0, 8.0], radar_mount_m=[.8, 0., 0.],
        thermal_optical_xyzw=[-.5, .5, -.5, .5], max_anchor_distance_m=200.0,
        limits=dict(identity_bytes=128, reason_bytes=256, wire_bytes=4096, receipts_per_stream=512,
                    receipt_bytes=16 * 1024 * 1024),
        deadlines_ns=dict(startup=60_000_000_000, first_capture=3_000_000_000,
                          transaction=1_000_000_000, session=120_000_000_000),
        pairing_ns=dict(radar_ir=5_000_000, pose_age=10_000_000, wait=40_000_000))
    # v1 is a named fixed test profile, not a silently tunable flight configuration.
    def match(actual, wanted):
        if type(actual) is not type(wanted):
            raise ValueError('scene_profile_type')
        if type(wanted) is dict:
            c.fields(actual, ' '.join(wanted))
            for key, child in wanted.items():
                match(actual[key], child)
        elif type(wanted) is list:
            if len(actual) != len(wanted):
                raise ValueError('scene_profile_shape')
            for a, b in zip(actual, wanted):
                match(a, b)
        else:
            if type(actual) is str:
                c.text(actual)
            if actual != wanted:
                raise ValueError('scene_profile_differs')
    match(value, fixed)


def validate_source_sample(value, profile):
    validate_profile(profile)
    c.fields(value, 'step_index sim_time_s ecef_ft R_ecef_frd uvw_ftps pqr_radps')
    c.integer(value['step_index'], profile['duration_steps'])
    c.number(value['sim_time_s'])
    raw_ns = Fraction(value['sim_time_s']) * 1_000_000_000
    if abs(raw_ns - value['step_index'] * profile['step_ns']) > 1:
        raise ValueError('scene_source_time_off_grid')
    for key, size in (('ecef_ft', 3), ('R_ecef_frd', 9), ('uvw_ftps', 3), ('pqr_radps', 3)):
        c.vector(value[key], size)
    m = value['R_ecef_frd']
    for i in range(3):
        for j in range(3):
            if abs(sum(m[3*i+k] * m[3*j+k] for k in range(3)) - int(i == j)) > 1e-9:
                raise ValueError('scene_source_rotation')
    determinant = (m[0] * (m[4]*m[8] - m[5]*m[7]) - m[1] * (m[3]*m[8] - m[5]*m[6]) +
                   m[2] * (m[3]*m[7] - m[4]*m[6]))
    if abs(determinant - 1.) > 1e-9:
        raise ValueError('scene_source_rotation_handedness')
