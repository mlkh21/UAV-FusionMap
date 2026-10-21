"""PERF-01-A功能级Radar/IR与SensorBundle业务契约。

本模块只产生/转换fixture字典，不依赖ROS、研究模型或LiDAR。ROS消息转换由
ros_ws中的薄包装完成，便于纯Python契约测试和后续替换真实驱动。
"""
import copy
import math
import random


SCHEMA_VERSION = "0.1"
FIXTURE_CALIBRATION = "perf01a_fixture_identity_v1"


def _header(run_id, clock_id, timestamp, sample_id, frame_id, source_type, status="valid", reason=""):
    if type(timestamp) is not int or timestamp < 0:
        raise ValueError("timestamp must be nonnegative int")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id required")
    if clock_id != "sim:" + run_id:
        raise ValueError("clock_id must identify run")
    if not isinstance(sample_id, str) or not sample_id.strip():
        raise ValueError("sample_id required")
    if status != "valid" and not reason.strip():
        raise ValueError("nonvalid status requires reason")
    return dict(schema_version=SCHEMA_VERSION, timestamp=timestamp, clock_id=clock_id,
                run_id=run_id, sample_id=sample_id, frame_id=frame_id,
                source_type=source_type, status=status, reason=reason)


def _quality(source="fixture; quality not calibrated"):
    return dict(confidence=None, uncertainty=dict(status="unavailable", kind="",
                   value=None, unit="", source=source))


def _finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + " must be finite")
    return float(value)


def _nonnegative(value, name):
    value = _finite(value, name)
    if value < 0:
        raise ValueError(name + " must be nonnegative")
    return value


def _duration(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + " must be a nonnegative integer")
    return value


def _interval(timestamp_ns, duration_ns, name):
    if type(timestamp_ns) is not int or timestamp_ns < 0:
        raise ValueError("timestamp must be nonnegative int")
    start = timestamp_ns - duration_ns // 2
    if start < 0:
        raise ValueError(name + " would start before simulation time zero")
    return start, start + duration_ns


def _fov(fov_deg):
    if fov_deg is None:
        return None
    if (not isinstance(fov_deg, (list, tuple)) or len(fov_deg) != 2 or
            any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                not math.isfinite(value) for value in fov_deg)):
        raise ValueError("fov_deg must be [horizontal, vertical]")
    horizontal, vertical = (float(value) for value in fov_deg)
    if not 0 < horizontal <= 360 or not 0 < vertical <= 180:
        raise ValueError("fov_deg must be within (0,360] x (0,180]")
    return horizontal, vertical


def normalize_fake_radar_options(options=None):
    """校验功能级Radar参数；参数不代表真实设备标定或验收值。"""
    options = {} if options is None else options
    if not isinstance(options, dict):
        raise ValueError("fake_radar options must be a mapping")
    fov_deg = _fov(options.get("fov_deg"))
    max_range_m = options.get("max_range_m")
    if max_range_m is not None:
        max_range_m = _nonnegative(max_range_m, "max_range_m")
        if max_range_m == 0:
            raise ValueError("max_range_m must be positive when enabled")
    return dict(
        fov_deg=fov_deg,
        max_range_m=max_range_m,
        position_noise_std_m=_nonnegative(options.get("position_noise_std_m", 0.0),
                                          "position_noise_std_m"),
        power_noise_std=_nonnegative(options.get("power_noise_std", 0.0),
                                     "power_noise_std"),
        scan_duration_ns=_duration(options.get("scan_duration_ns", 0), "scan_duration_ns"),
    )


def normalize_fake_infrared_options(options=None):
    """校验功能级IR参数；图像值仍是fixture_intensity而非辐射测量。"""
    options = {} if options is None else options
    if not isinstance(options, dict):
        raise ValueError("fake_infrared options must be a mapping")
    hotspots = options.get("hotspots", [])
    if not isinstance(hotspots, (list, tuple)):
        raise ValueError("hotspots must be a list")
    normalized_hotspots = []
    for hotspot in hotspots:
        if not isinstance(hotspot, dict):
            raise ValueError("each hotspot must be a mapping")
        x_px = hotspot.get("x_px")
        y_px = hotspot.get("y_px")
        radius_px = hotspot.get("radius_px", 0)
        if (type(x_px) is not int or type(y_px) is not int or
                x_px < 0 or y_px < 0 or type(radius_px) is not int or radius_px < 0):
            raise ValueError("hotspot pixel coordinates and radius must be nonnegative integers")
        normalized_hotspots.append(dict(
            x_px=x_px, y_px=y_px, radius_px=radius_px,
            value=_finite(hotspot.get("value", 0.0), "hotspot value")))
    return dict(
        background_value=_finite(options.get("background_value", 0.5), "background_value"),
        noise_std=_nonnegative(options.get("noise_std", 0.0), "noise_std"),
        exposure_duration_ns=_duration(options.get("exposure_duration_ns", 0),
                                       "exposure_duration_ns"),
        hotspots=normalized_hotspots,
    )


def _sample_rng(seed, sequence, index, stream):
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    if type(sequence) is not int or sequence < 0:
        raise ValueError("sequence must be a nonnegative integer")
    # 算术种子保持跨进程可复现，不依赖Python进程随机化的hash。
    return random.Random(seed + sequence * 1_000_003 + index * 9_176 + stream * 101_003)


def _visible(point, options):
    x, y, z = point
    distance = math.sqrt(x * x + y * y + z * z)
    if options["max_range_m"] is not None and distance > options["max_range_m"]:
        return False
    if options["fov_deg"] is None:
        return True
    if x <= 0:
        return False
    horizontal = math.degrees(math.atan2(y, x))
    vertical = math.degrees(math.atan2(z, math.hypot(x, y)))
    horizontal_fov, vertical_fov = options["fov_deg"]
    return (abs(horizontal) <= horizontal_fov / 2.0 and
            abs(vertical) <= vertical_fov / 2.0)


def _noisy_point(point, options, seed, sequence, index):
    rng = _sample_rng(seed, sequence, index, 0)
    std = options["position_noise_std_m"]
    return tuple(value + rng.gauss(0.0, std) for value in point)


def _radar_power(options, seed, sequence, index):
    rng = _sample_rng(seed, sequence, index, 1)
    return max(0.0, 1.0 + rng.gauss(0.0, options["power_noise_std"]))


def _radar_frame(run_id, sequence, timestamp_ns, points, options):
    clock_id = "sim:" + run_id
    sample_id = "fixture.radar:%s:%d" % (run_id, sequence)
    scan_start, scan_end = _interval(timestamp_ns, options["scan_duration_ns"], "radar scan")
    return dict(header=_header(run_id, clock_id, timestamp_ns, sample_id, "radar", "fixture"),
                points=points, scan_start=scan_start, scan_end=scan_end,
                power_quantity="uncalibrated_intensity", power_unit="arbitrary",
                doppler_reference="sensor_relative", quality=_quality())


def make_fake_radar(run_id, sequence, timestamp_ns, point=(8.0, 0.0, 0.0), *,
                    fov_deg=None, max_range_m=None, position_noise_std_m=0.0,
                    power_noise_std=0.0, scan_duration_ns=0, seed=0):
    """生成单回波功能级RadarFrame；可选视场、量程、噪声和扫描时长。"""
    options = normalize_fake_radar_options(dict(
        fov_deg=fov_deg, max_range_m=max_range_m,
        position_noise_std_m=position_noise_std_m, power_noise_std=power_noise_std,
        scan_duration_ns=scan_duration_ns))
    if len(point) != 3:
        raise ValueError("radar point must have three coordinates")
    point = tuple(_finite(value, "radar point") for value in point)
    points = []
    if _visible(point, options):
        x, y, z = _noisy_point(point, options, seed, sequence, 0)
        points.append(dict(x=x, y=y, z=z, doppler=0.0,
                           power=_radar_power(options, seed, sequence, 0),
                           doppler_available=True, power_available=True))
    return _radar_frame(run_id, sequence, timestamp_ns, points, options)


def make_motion_radar(run_id, sequence, timestamp_ns, speed_mps, obstacles_odom, *,
                      fov_deg=None, max_range_m=None, position_noise_std_m=0.0,
                      power_noise_std=0.0, scan_duration_ns=0, seed=0):
    """北向直线fixture的固定世界点逆投影；真值不进入Radar业务字段。

    R_odom_radar为绕z正90度，p_odom=(0,v*t,0)，单位外参限命名fixture。
    可选参数只用于功能级FOV、量程和噪声注入；Doppler尚未模拟，明确标不可用。
    """
    options = normalize_fake_radar_options(dict(
        fov_deg=fov_deg, max_range_m=max_range_m,
        position_noise_std_m=position_noise_std_m, power_noise_std=power_noise_std,
        scan_duration_ns=scan_duration_ns))
    speed_mps = _finite(speed_mps, "speed_mps")
    points = []
    for index, obstacle in enumerate(obstacles_odom):
        if len(obstacle) != 3:
            raise ValueError("obstacles_odom points must have three coordinates")
        east, north, up = (_finite(value, "obstacle coordinate") for value in obstacle)
        point = (north - speed_mps * timestamp_ns / 1e9, -east, up)
        if not _visible(point, options):
            continue
        x, y, z = _noisy_point(point, options, seed, sequence, index)
        points.append(dict(x=x, y=y, z=z, doppler=0.0,
                           power=_radar_power(options, seed, sequence, index),
                           doppler_available=False, power_available=True))
    return _radar_frame(run_id, sequence, timestamp_ns, points, options)


def make_fake_infrared(run_id, sequence, timestamp_ns, width=2, height=2, *,
                       background_value=0.5, noise_std=0.0,
                       exposure_duration_ns=0, hotspots=None, seed=0):
    """生成小尺寸热图fixture；参数不是Micro III Lite硬件验收参数。"""
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        raise ValueError("positive image dimensions required")
    options = normalize_fake_infrared_options(dict(
        background_value=background_value, noise_std=noise_std,
        exposure_duration_ns=exposure_duration_ns, hotspots=hotspots or []))
    if any(hotspot["x_px"] >= width or hotspot["y_px"] >= height
           for hotspot in options["hotspots"]):
        raise ValueError("hotspot center must be inside image dimensions")
    clock_id = "sim:" + run_id
    sample_id = "fixture.infrared:%s:%d" % (run_id, sequence)
    image = [options["background_value"]] * (width * height)
    for hotspot in options["hotspots"]:
        radius_squared = hotspot["radius_px"] ** 2
        for y_px in range(max(0, hotspot["y_px"] - hotspot["radius_px"]),
                          min(height, hotspot["y_px"] + hotspot["radius_px"] + 1)):
            for x_px in range(max(0, hotspot["x_px"] - hotspot["radius_px"]),
                              min(width, hotspot["x_px"] + hotspot["radius_px"] + 1)):
                dx = x_px - hotspot["x_px"]
                dy = y_px - hotspot["y_px"]
                if dx * dx + dy * dy <= radius_squared:
                    image[y_px * width + x_px] += hotspot["value"]
    if options["noise_std"]:
        rng = _sample_rng(seed, sequence, 0, 2)
        image = [value + rng.gauss(0.0, options["noise_std"]) for value in image]
    exposure_start, exposure_end = _interval(timestamp_ns, options["exposure_duration_ns"],
                                             "infrared exposure")
    return dict(header=_header(run_id, clock_id, timestamp_ns, sample_id, "thermal_optical",
                               "fixture"),
                width=width, height=height, encoding="32FC1", value_unit="fixture_intensity",
                image=image, exposure_start=exposure_start, exposure_end=exposure_end,
                camera_info=dict(width=width, height=height,
                    calibration_id=FIXTURE_CALIBRATION), quality=_quality())


def make_fixture_state(run_id, sequence, timestamp_ns):
    """生成仅供ROS fixture驱动的AircraftState源字典。"""
    return dict(header=_header(run_id, "sim:" + run_id, timestamp_ns,
                               "fixture.state:%s:%d" % (run_id, sequence),
                               "world_ned", "simulation"),
                position=[0.0, 0.0, 0.0], orientation_xyzw=[0.0, 0.0, 0.0, 1.0],
                linear_velocity=[0.0, 0.0, 0.0], body_frame_id="body_frd",
                velocity_frame_id="body_frd", state_source="estimated",
                quality=_quality("fixture state covariance unavailable"))


def fixture_spatial_context(state, timestamp_ns, run_id, calibration_id):
    """使用已适配位姿；单位T_body_radar只由命名fixture标定明确授权。"""
    position, orientation = state["position"], state["orientation_xyzw"]
    if len(position) != 3 or len(orientation) != 4:
        raise ValueError("invalid pose dimensions")
    if any(not math.isfinite(value) for value in position + orientation):
        raise ValueError("pose must be finite")
    norm = math.sqrt(sum(value * value for value in orientation))
    if norm == 0 or abs(norm - 1.0) > .001:
        raise ValueError("invalid quaternion norm")
    x, y, z, w = (value / norm for value in orientation)
    transform = [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w), position[0],
                 2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w), position[1],
                 2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y), position[2],
                 0.0, 0.0, 0.0, 1.0]
    return dict(reference_timestamp=timestamp_ns, clock_id="sim:" + run_id,
                mapping_frame_id="odom", source_frame_id="radar",
                T_mapping_source=list(transform), T_mapping_source_status="available",
                T_mapping_body=list(transform), T_mapping_body_status="available",
                pose_uncertainty=copy.deepcopy(state["quality"]["uncertainty"]),
                calibration_id=calibration_id, state_source=state["state_source"])


def _nearest_state(states, timestamp_ns):
    candidates = [state for state in states
                  if state["header"]["timestamp"] <= timestamp_ns and
                  state["header"]["status"] == "valid"]
    if not candidates:
        return None
    return max(candidates, key=lambda value: value["header"]["timestamp"])


def build_sensor_bundle(radar, infrared, states, max_delta_ns=5_000_000,
                        max_pose_age_ns=10_000_000,
                        calibration_id=FIXTURE_CALIBRATION):
    """按Radar参考时刻配对IR和状态；返回(bundle, reason)。"""
    if radar["header"]["status"] != "valid":
        return None, "radar_unavailable"
    if not infrared or infrared["header"]["status"] != "valid":
        return None, "infrared_unavailable"
    if radar["header"]["run_id"] != infrared["header"]["run_id"]:
        return None, "run_mismatch"
    if radar["header"]["clock_id"] != infrared["header"]["clock_id"]:
        return None, "clock_mismatch"
    if (calibration_id != FIXTURE_CALIBRATION or
            radar["header"]["source_type"] != "fixture" or
            infrared["header"]["source_type"] != "fixture" or
            infrared["camera_info"]["calibration_id"] != calibration_id):
        return None, "calibration_unavailable"
    if (radar["header"]["frame_id"] != "radar" or
            infrared["header"]["frame_id"] != "thermal_optical"):
        return None, "sensor_frame_mismatch"
    delta_ns = infrared["header"]["timestamp"] - radar["header"]["timestamp"]
    if abs(delta_ns) > max_delta_ns:
        return None, "radar_ir_timeout"
    state = _nearest_state(states, radar["header"]["timestamp"])
    if state is None:
        return None, "pose_unavailable"
    if (state["header"]["run_id"] != radar["header"]["run_id"] or
            state["header"]["clock_id"] != radar["header"]["clock_id"]):
        return None, "pose_run_mismatch"
    pose_age_ns = radar["header"]["timestamp"] - state["header"]["timestamp"]
    if pose_age_ns < 0 or pose_age_ns > max_pose_age_ns:
        return None, "pose_age_exceeded"
    if state["header"]["frame_id"] != "odom" or state["body_frame_id"] != "base_link":
        return None, "pose_frame_mismatch"
    run_id = radar["header"]["run_id"]
    timestamp_ns = radar["header"]["timestamp"]
    bundle_id = "sensors.bundle:" + radar["header"]["sample_id"]
    try:
        context = fixture_spatial_context(state, timestamp_ns, run_id, calibration_id)
    except (ValueError, TypeError):
        return None, "pose_invalid"
    # 32FC1像素是不可变数值；独立复制容器即可，避免deepcopy逐像素递归。
    infrared_copy = copy.deepcopy({key: value for key, value in infrared.items() if key != 'image'})
    infrared_copy['image'] = list(infrared['image'])
    return dict(
        header=_header(run_id, radar["header"]["clock_id"], timestamp_ns, bundle_id,
                       "radar", "derived"),
        radar=copy.deepcopy(radar), infrared=infrared_copy,
        state=copy.deepcopy(state), calibration_id=calibration_id,
        context=context,
        radar_ir_delta_ns=abs(delta_ns), pose_age_ns=pose_age_ns,
    ), ""


def validate_bundle(bundle):
    if bundle["header"]["source_type"] != "derived":
        raise ValueError("bundle must be derived")
    if bundle["header"]["frame_id"] != "radar":
        raise ValueError("bundle frame must be radar")
    if bundle["header"]["timestamp"] != bundle["radar"]["header"]["timestamp"]:
        raise ValueError("bundle timestamp must use radar reference")
    if bundle["radar"]["header"]["run_id"] != bundle["infrared"]["header"]["run_id"]:
        raise ValueError("bundle sensor runs differ")
    if bundle["radar_ir_delta_ns"] < 0 or bundle["pose_age_ns"] < 0:
        raise ValueError("sync ages must be nonnegative")
    if "lidar" in bundle or "occupancy_target" in bundle or "observed_mask" in bundle:
        raise ValueError("LiDAR supervision must not enter SensorBundle")
    return True
