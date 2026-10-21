"""功能级载荷和明确注入的时间错误；不修正或掩盖采样时间。"""
import copy

from .perf01a_fixture import make_fake_radar, make_fake_infrared


def scenario_inputs(run_id, sequence, state, profile, measure=None):
    stamp = state['header']['timestamp']
    sensor_seed = profile.get('sensor_noise_seed', profile.get('seed', 0))
    radar = make_fake_radar(run_id, sequence, stamp, point=(4., 0., 0.),
                            seed=sensor_seed, **profile.get('fake_radar', {}))
    active = profile.get('start_sequence', 0) <= sequence < profile.get('stop_sequence', 0)
    fault = profile['fault'] if active else 'none'
    offset = profile['ir_offset_ns'] if fault == 'ir_offset' else 0
    width, height = profile['ir_resolution']
    if fault == 'ir_missing':
        infrared = None
    elif measure is None:
        infrared = make_fake_infrared(run_id, sequence, stamp + offset, width, height,
                                      seed=sensor_seed, **profile.get('fake_infrared', {}))
    else:
        infrared = measure('infrared_generation', make_fake_infrared,
                           run_id, sequence, stamp + offset, width, height,
                           seed=sensor_seed, **profile.get('fake_infrared', {}))
    pose = state
    if fault == 'pose_age':
        pose = copy.deepcopy(state)
        pose['header']['timestamp'] -= profile['pose_age_ns']
        pose['header']['sample_id'] += ':injected_stale'
    return radar, infrared, [pose]
