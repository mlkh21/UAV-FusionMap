"""功能级仿真源；不依赖sensors业务实现或真实飞控。"""
import math


def make_motion_state(run_id, sequence, timestamp_ns, speed_mps):
    """沿world_ned北向匀速运动；适配后为odom的y轴，保留真实姿态。"""
    if not math.isfinite(speed_mps) or speed_mps < 0 or timestamp_ns < 0:
        raise ValueError('speed and timestamp must be nonnegative')
    position_x = float(speed_mps) * float(timestamp_ns) / 1e9
    return dict(header=dict(schema_version='0.1', timestamp=timestamp_ns,
        clock_id='sim:' + run_id, run_id=run_id,
        sample_id='fixture.state:%s:%d' % (run_id, sequence),
        frame_id='world_ned', source_type='simulation', status='valid', reason=''),
        position=[position_x, 0., 0.], orientation_xyzw=[0., 0., 0., 1.],
        linear_velocity=[float(speed_mps), 0., 0.], body_frame_id='body_frd',
        velocity_frame_id='body_frd', state_source='estimated',
        quality=dict(confidence=None, uncertainty=dict(status='unavailable', kind='',
            value=None, unit='', source='motion fixture state covariance unavailable')))


def make_fixture_state(run_id, sequence, timestamp_ns):
    return dict(header=dict(schema_version='0.1', timestamp=timestamp_ns,
        clock_id='sim:' + run_id, run_id=run_id,
        sample_id='fixture.state:%s:%d' % (run_id, sequence),
        frame_id='world_ned', source_type='simulation', status='valid', reason=''),
        position=[0., 0., 0.], orientation_xyzw=[0., 0., 0., 1.],
        linear_velocity=[0., 0., 0.], body_frame_id='body_frd',
        velocity_frame_id='body_frd', state_source='estimated',
        quality=dict(confidence=None, uncertainty=dict(status='unavailable', kind='',
            value=None, unit='', source='fixture state covariance unavailable')))


def make_scan_motion_state(run_id, sequence, timestamp_ns, anchor_timestamp_ns,
                           speed_mps, yaw_rate_deg_s):
    """Kinematic scan fixture: northward translation and an independent yaw sweep.

    This is not a dynamically consistent aircraft turn or a PX4 estimate.
    At the named anchor time, position and NED yaw are zero.
    """
    if (type(timestamp_ns) is not int or timestamp_ns < 0
            or type(anchor_timestamp_ns) is not int or anchor_timestamp_ns < 0
            or not math.isfinite(speed_mps) or speed_mps < 0
            or not math.isfinite(yaw_rate_deg_s)):
        raise ValueError('finite scan motion and integer timestamps required')
    elapsed = (timestamp_ns - anchor_timestamp_ns) / 1e9
    yaw = math.radians(yaw_rate_deg_s) * elapsed
    state = make_motion_state(run_id, sequence, timestamp_ns, 0.)
    state['position'] = [speed_mps * elapsed, 0., 0.]
    state['orientation_xyzw'] = [0., 0., math.sin(yaw / 2), math.cos(yaw / 2)]
    state['linear_velocity'] = [speed_mps * math.cos(yaw), -speed_mps * math.sin(yaw), 0.]
    return state


def make_training_fixture_state(run_id, sequence, timestamp_ns, config):
    """Select a bounded training motion profile; preserve historical straight fixtures."""
    if config.get('mode') != 'training_data_generation':
        raise ValueError('training fixture source cannot run in inference mode')
    profile = config.get('fixture_motion')
    if profile is None:
        return make_motion_state(run_id, sequence, timestamp_ns, .1)
    return make_scan_motion_state(run_id, sequence, timestamp_ns, **profile)
