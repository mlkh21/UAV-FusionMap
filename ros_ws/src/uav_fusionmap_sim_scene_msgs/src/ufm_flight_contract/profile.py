"""Named observation-only 40 s metadata; validation never runs or advances a source."""
import json
from pathlib import Path

from . import contract as c

PROFILE = dict(schema_version='sim_flight_scene_fixture.v2', profile_id='sim-flight-scene-observe-v2',
    fixture_only=True, simulation_only=True, observation_only=True, commands_enabled=False,
    protocol_version=2, mode='jsbsim_scene_truth', registration_id=c.REGISTRATION,
    body_origin_policy='jsbsim_cg_virtual_flu_v1', step_ns=c.STEP_NS, gazebo_step_ns=1_000_000,
    duration_steps=c.MAX_STEPS, capture_start_after_step=c.CAPTURE_AFTER_STEP,
    capture_period_steps=c.CAPTURE_STEPS, scene_anchor_m=[0., 0., .5], min_scene_z_exclusive_m=.2,
    max_anchor_distance_m=250., radar_mount_m=[.8, 0., 0.], thermal_optical_xyzw=[-.5, .5, -.5, .5],
    limits=dict(identity_bytes=128, reason_bytes=256, wire_bytes=4096, receipts_per_stream=12288,
        control_events=4096, record_bytes=16384, control_log_bytes=67108864,
        subscribed_wire_bytes=134217728, artifact_bytes=536870912),
    deadlines_ns=dict(startup=60_000_000_000, first_capture=3_000_000_000,
        transaction=1_000_000_000, session=240_000_000_000),
    pairing_ns=dict(radar_ir=5_000_000, pose_age=0, wait=40_000_000))
JSON_BYTES = 256 * 1024


def validate_profile(value):
    def match(actual, wanted):
        if type(actual) is not type(wanted):
            raise ValueError('flight_profile_type')
        if type(wanted) is dict:
            c.fields(actual, ' '.join(wanted))
            for key, item in wanted.items():
                match(actual[key], item)
        elif type(wanted) is list:
            if len(actual) != len(wanted):
                raise ValueError('flight_profile_shape')
            for a, b in zip(actual, wanted):
                match(a, b)
        elif actual != wanted:
            raise ValueError('flight_profile_differs')
    match(value, PROFILE)


def load_profile(path):
    # Read at most one byte past the limit, including files changed during the read.
    with Path(path).open('rb') as stream:
        raw = stream.read(JSON_BYTES + 1)
    if len(raw) > JSON_BYTES:
        raise ValueError('flight_profile_json_size')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('flight_profile_duplicate_key')
            result[key] = value
        return result
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('flight_profile_nonfinite')))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('flight_profile_encoding_or_depth') from exc
    remaining = [8192]
    def walk(item, depth):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 8:
            raise ValueError('flight_profile_structure')
        if type(item) is dict:
            for key, child in item.items():
                c.text(key)
                walk(child, depth + 1)
        elif type(item) is list:
            for child in item:
                walk(child, depth + 1)
        elif type(item) is str:
            c.text(item, empty=True)
        elif item is not None and type(item) is not bool:
            c.number(item)
    walk(value, 0)
    validate_profile(value)
    return value
