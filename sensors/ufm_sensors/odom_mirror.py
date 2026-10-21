"""AircraftState到ROS兼容Odometry/TF所需的无ROS契约转换。"""
import copy
import math
from numbers import Real


def _vector(value, size, name):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(name + ' dimension mismatch')
    if any(isinstance(item, bool) or not isinstance(item, Real)
           or not math.isfinite(float(item)) for item in value):
        raise ValueError(name + ' must contain finite values')
    return [float(item) for item in value]


def build_odom_mirror(state):
    """Build a read-only compatibility representation from adapted AircraftState.

    AircraftState remains the authoritative record.  Odometry intentionally carries
    unknown covariance and cannot represent terminal/unavailable state geometry.
    """
    if not isinstance(state, dict) or not isinstance(state.get('header'), dict):
        raise ValueError('state header required')
    header = state['header']
    if header.get('status') not in ('valid', 'degraded'):
        raise ValueError('unavailable state cannot become odometry')
    if header.get('frame_id') != 'odom':
        raise ValueError('adapted odometry frame required')
    if state.get('body_frame_id') != 'base_link' or state.get('velocity_frame_id') != 'base_link':
        raise ValueError('adapted body frame required')
    timestamp = header.get('timestamp')
    if type(timestamp) is not int or not 0 <= timestamp < 2**63:
        raise ValueError('invalid state timestamp')
    orientation = _vector(state.get('orientation_xyzw'), 4, 'orientation_xyzw')
    norm = math.sqrt(sum(value * value for value in orientation))
    if norm == 0 or abs(norm - 1.) > .001:
        raise ValueError('orientation must be a unit quaternion')
    mirror = dict(
        header=copy.deepcopy(header),
        frame_id='odom',
        child_frame_id='base_link',
        position=_vector(state.get('position'), 3, 'position'),
        orientation_xyzw=orientation,
        linear_velocity=_vector(state.get('linear_velocity'), 3, 'linear_velocity'),
        pose_covariance=[-1.0] + [0.0] * 35,
        twist_covariance=[-1.0] + [0.0] * 35,
        covariance_available=False,
    )
    return mirror
