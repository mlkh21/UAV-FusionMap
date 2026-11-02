"""SIM-01A：将估计 NED/FRD 状态转换为明确配置的 odom/FLU。

本模块不维护时钟、不发布 TF；接收时钟覆盖和 run 终止由薄包装负责。
base_link 同源 Body 原点仅为本次仿真虚拟框架约定，不是实机标定。
"""
import copy
import math
from numbers import Real


def _vector(value, size, name):
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise ValueError(name + ": wrong dimension")
    if any(isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x)
           for x in value):
        raise ValueError(name + ": finite numeric values required")
    return [float(x) for x in value]


def ned_to_enu(vector):
    """同原点世界轴变换 C_enu_ned，不处理未声明的平移。"""
    x, y, z = _vector(vector, 3, "NED vector")
    return [y, x, -z]


def frd_to_flu(vector):
    """机体轴变换 D_flu_frd，适用于同原点机体系向量。"""
    x, y, z = _vector(vector, 3, "FRD vector")
    return [x, -y, -z]


def _quaternion_product(a, b):
    x, y, z, w = a
    X, Y, Z, W = b
    return [w*X + x*W + y*Z - z*Y,
            w*Y - x*Z + y*W + z*X,
            w*Z + x*Y - y*X + z*W,
            w*W - x*X - y*Y - z*Z]


def orientation_ned_frd_to_enu_flu(orientation_xyzw, norm_tolerance=.001):
    """归一化微小模长误差后，返回 C R_ned_frd D^T 的 xyzw 四元数。"""
    if (isinstance(norm_tolerance, bool) or not isinstance(norm_tolerance, Real)
            or not math.isfinite(norm_tolerance) or norm_tolerance < 0):
        raise ValueError("norm_tolerance must be finite and nonnegative")
    q = _vector(orientation_xyzw, 4, "orientation_xyzw")
    norm = math.sqrt(sum(x*x for x in q))
    if not math.isfinite(norm) or norm == 0 or abs(norm - 1) > norm_tolerance:
        raise ValueError("orientation_xyzw: norm outside tolerance")
    q = [x/norm for x in q]
    s = math.sqrt(.5)
    # C 是绕水平 [1,1,0] 轴旋转 pi；D^T 是绕 x 轴旋转 pi 的逆。
    result = _quaternion_product(
        _quaternion_product([s, s, 0., 0.], q), [-1., 0., 0., 0.])
    result_norm = math.sqrt(sum(x*x for x in result))
    return [x/result_norm for x in result]


def _validate_header(header):
    if not isinstance(header, dict):
        raise ValueError("header must be a dict")
    for key in ("schema_version", "clock_id", "run_id", "sample_id", "frame_id"):
        if not isinstance(header.get(key), str) or not header[key].strip():
            raise ValueError("header." + key + " is required")
    if header["schema_version"] != "0.1":
        raise ValueError("unsupported schema_version")
    if header["clock_id"] != "sim:" + header["run_id"]:
        raise ValueError("clock_id must identify this simulation run")
    timestamp = header.get("timestamp")
    if isinstance(timestamp, bool) or not isinstance(timestamp, int) or not 0 <= timestamp < 2**63:
        raise ValueError("timestamp must be nonnegative int64 nanoseconds")
    if header.get("status") not in ("valid", "degraded", "unavailable"):
        raise ValueError("unknown status")
    if header.get("source_type") != "simulation":
        raise ValueError("expected simulation source")
    if not isinstance(header.get("reason"), str):
        raise ValueError("reason must be a string")
    if header["status"] != "valid" and not header["reason"].strip():
        raise ValueError("nonvalid status requires reason")


def _target_state(source):
    result = copy.deepcopy(source)
    result["header"].update(frame_id="odom", source_type="derived",
                            sample_id="sensors.state:" + source["header"]["sample_id"])
    result["body_frame_id"] = "base_link"
    result["velocity_frame_id"] = "base_link"
    result["quality"] = {
        "confidence": None,
        "uncertainty": {"status": "unavailable", "kind": "", "value": None,
                        "unit": "", "source": "PX4 full pose covariance not validated"},
    }
    original_quality = source.get("quality", {})
    original_uncertainty = original_quality.get("uncertainty", {}) if isinstance(original_quality, dict) else {}
    if isinstance(original_uncertainty, dict) and original_uncertainty.get("status") == "unavailable":
        for key in ("kind", "unit", "source"):
            if key in original_uncertainty:
                result["quality"]["uncertainty"][key] = copy.deepcopy(original_uncertainty[key])
    return result


def adapt_state(state, frames_config, norm_tolerance=.001):
    """返回新 AircraftState dict；无效输入抛 ValueError，不修改调用者对象。

    terminal:code 的 unavailable 在基本身份验证后直接传播；其几何槽不作为观测。
    正常状态要求显式原点配置和 estimated/world_ned/body_frd 输入。
    """
    if not isinstance(state, dict):
        raise ValueError("state must be a dict")
    header = state.get("header")
    _validate_header(header)
    if header["status"] == "unavailable" and header["reason"].startswith("terminal:"):
        return _target_state(state)
    if header["status"] == "unavailable":
        raise ValueError("unavailable state is not a geometric observation")
    if (not isinstance(frames_config, dict)
            or frames_config.get("odom_origin_policy") != "px4_estimator_local_origin"
            or frames_config.get("body_origin_policy") != "source_body_virtual_flu"):
        raise ValueError("explicit simulation origin policies required")
    if (header["frame_id"] != "world_ned" or state.get("body_frame_id") != "body_frd"
            or state.get("velocity_frame_id") != "body_frd"
            or state.get("state_source") != "estimated"):
        raise ValueError("expected estimated world_ned/body_frd state and body velocity")
    position = ned_to_enu(state.get("position"))
    velocity = frd_to_flu(state.get("linear_velocity"))
    orientation = orientation_ned_frd_to_enu_flu(state.get("orientation_xyzw"), norm_tolerance)
    result = _target_state(state)
    result.update(position=position, linear_velocity=velocity, orientation_xyzw=orientation)
    return result


def adapt_scene_ground_truth(state, registration_id):
    """Explicit scene-world ENU truth; retain source, including non-geometric terminal."""
    _validate_header(state['header'])
    if registration_id != 'gazebo_scene_world_enu_identity_v1':
        raise ValueError('explicit scene ENU registration required')
    if (state['header']['frame_id'] != 'scene_world' or state['state_source'] != 'ground_truth' or
            state['body_frame_id'] != 'base_link' or state['velocity_frame_id'] != 'base_link'):
        raise ValueError('expected Gazebo scene ground truth ENU/FLU state')
    if state['header']['status'] == 'unavailable' and state['header']['reason'].startswith('terminal:'):
        return _target_state(state)
    if state['header']['status'] != 'valid':
        raise ValueError('unavailable scene state is not a geometric observation')
    _vector(state['position'], 3, 'scene position')
    _vector(state['linear_velocity'], 3, 'scene body velocity')
    q = _vector(state['orientation_xyzw'], 4, 'scene orientation')
    if abs(sum(v*v for v in q) - 1) > .001:raise ValueError('invalid scene orientation')
    return _target_state(state)
