"""IMU逻辑样本与ROS消息往返；不可用协方差不编码为零方差。"""
from uav_fusionmap_msgs.msg import ImuSample

from .codec import decode_header, encode_header, _decode, _encode, _text, _vector


ACCELERATION = {'specific_force': 0, 'gravity_removed': 1}


def to_ros_imu(sample):
    try:
        msg = ImuSample()
        h = sample['header']
        encode_header(msg.header, h)
        if h['clock_id'] != 'sim:' + h['run_id']:
            raise ValueError('invalid_imu_schema_or_clock')
        if h['source_type'] not in ('simulation', 'derived'):
            raise ValueError('invalid_imu_source')
        msg.acceleration_type = _encode(sample['acceleration_type'], ACCELERATION, 'acceleration_type')
        msg.linear_acceleration = _vector(sample['linear_acceleration'], 3, 'linear_acceleration')
        msg.angular_velocity = _vector(sample['angular_velocity'], 3, 'angular_velocity')
        if h['status'] == 'unavailable' and (any(msg.linear_acceleration) or any(msg.angular_velocity)):
            raise ValueError('unavailable_imu_has_values')
        for name in ('acceleration_covariance', 'angular_velocity_covariance'):
            value = sample[name]
            if value is not None:
                raise ValueError('imu_covariance_not_verified')
            setattr(msg, name + '_available', False)
            setattr(msg, name, [0.] * 9)  # 无效槽位，由available=false判定。
        msg.calibration_id = _text(sample['calibration_id'], 'calibration_id',
                                   allow_empty=h['source_type'] == 'simulation')
        return msg
    except (KeyError, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('invalid_imu_sample: ' + str(exc)) from exc


def from_ros_imu(msg):
    try:
        h = decode_header(msg.header)
        sample = dict(header=h,
                      acceleration_type=_decode(msg.acceleration_type, ACCELERATION, 'acceleration_type'),
                      linear_acceleration=list(msg.linear_acceleration),
                      angular_velocity=list(msg.angular_velocity), calibration_id=msg.calibration_id)
        for name in ('acceleration_covariance', 'angular_velocity_covariance'):
            if getattr(msg, name + '_available') or any(getattr(msg, name)):
                raise ValueError('imu_covariance_not_verified')
            sample[name] = None
        to_ros_imu(sample)
        return sample
    except (TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('invalid_imu_message: ' + str(exc)) from exc
