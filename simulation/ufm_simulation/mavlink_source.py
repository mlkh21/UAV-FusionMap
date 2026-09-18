"""只接受已审查PX4源组合，不从缺失的协方差或质量推断确定性。"""
import math

from pymavlink.dialects.v20 import common


def timestamp_ns(time_usec):
    if type(time_usec) is not int or not 0 <= time_usec <= (2**63 - 1)//1000:
        raise ValueError('invalid_source_timestamp')
    return time_usec * 1000


def unavailable_quality():
    return {'confidence': None, 'uncertainty': {
        'status': 'unavailable', 'kind': 'pose_covariance', 'value': None,
        'unit': '[x,y,z,rx,ry,rz]: m*m, m*rad, rad*rad',
        'source': 'PX4 v1.13.3 EKF2 pose angle covariance TODO; '
                  'ODOMETRY velocity covariance rotation TODO; quality not supplied'}}


def decode_source_packet(wire, framing_status=1, sysid=1, compid=1,
                         norm_tolerance=.001):
    """返回目标样本、非目标None；目标帧损坏/契约错误为ValueError。"""
    if framing_status != 1:
        raise ValueError('invalid_framing')
    if not isinstance(wire, (bytes, bytearray)) or len(wire) < 8:
        raise ValueError('invalid_wire')
    if not math.isfinite(norm_tolerance) or not 0 <= norm_tolerance <= .001:
        raise ValueError('invalid_norm_tolerance')
    if wire[0] == 253 and len(wire) >= 12:
        source = wire[5], wire[6]
        msgid = int.from_bytes(wire[7:10], 'little')
    elif wire[0] == 254:
        source = wire[3], wire[4]
        msgid = wire[5]
    else:
        raise ValueError('invalid_wire_magic')
    if source != (sysid, compid) or msgid not in (105, 331):
        return None
    try:
        msg = common.MAVLink(None).decode(bytearray(wire))
    except Exception as exc:
        raise ValueError('invalid_wire_decode') from exc
    ns = timestamp_ns(msg.time_usec)
    if msgid == 105:
        values = [getattr(msg, k) for k in ('xacc','yacc','zacc','xgyro','ygyro','zgyro')]
        if msg.fields_updated & 63 != 63 or not all(math.isfinite(v) for v in values):
            raise ValueError('invalid_imu_fields')
        return {'type': 'imu', 'time_usec': msg.time_usec}
    if (msg.frame_id, msg.child_frame_id, msg.estimator_type) != (1, 12, 8):
        raise ValueError('unsupported_odometry_source_frames')
    position = [msg.x, msg.y, msg.z]
    velocity = [msg.vx, msg.vy, msg.vz]
    if not all(math.isfinite(x) for x in position + velocity + list(msg.q)):
        raise ValueError('nonfinite_odometry')
    norm = math.sqrt(sum(x*x for x in msg.q))
    if norm == 0 or abs(norm - 1.) > norm_tolerance:
        raise ValueError('invalid_quaternion_norm')
    q = [v/norm for v in msg.q]
    state = {'header': {
        'schema_version': '0.1', 'timestamp': ns, 'clock_id': '', 'run_id': '',
        'sample_id': 'sim.odometry:%d:%d:%d' % (sysid, compid, msg.time_usec),
        'frame_id': 'world_ned', 'source_type': 'simulation', 'status': 'valid', 'reason': ''},
        'position': position, 'orientation_xyzw': q[1:] + q[:1],
        'linear_velocity': velocity, 'body_frame_id': 'body_frd',
        'velocity_frame_id': 'body_frd', 'state_source': 'estimated',
        'quality': unavailable_quality()}
    return {'type': 'odometry', 'state': state, 'reset_counter': msg.reset_counter}
