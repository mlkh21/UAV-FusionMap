"""不依赖模型/GPU/LiDAR的确定性占位感知。"""
import copy
import math


def _header(bundle, sample_id, status="valid", reason=""):
    source = bundle["header"]
    return dict(schema_version="0.1", timestamp=source["timestamp"],
                clock_id=source["clock_id"], run_id=source["run_id"],
                sample_id=sample_id, frame_id="odom", source_type="fixture",
                status=status, reason=reason)


def placeholder_infer(bundle, resolution=(0.5, 0.5, 0.5),
                      shape=(64, 32, 16), origin=(-16.0, -8.0, -4.0),
                      rolling_grid=False):
    """将fixture Radar回波投影为一个占据体素；不产生自由空间证据。"""
    context = copy.deepcopy(bundle["context"])
    transform = context["T_mapping_source"]
    if (context["source_frame_id"] != "radar" or context["mapping_frame_id"] != "odom" or
            context["reference_timestamp"] != bundle["header"]["timestamp"] or
            context["clock_id"] != bundle["header"]["clock_id"]):
        raise ValueError("bundle context frame or time mismatch")
    available = (context["T_mapping_source_status"] == "available" and
                 context["T_mapping_body_status"] == "available")
    context["source_frame_id"] = "odom"
    context["T_mapping_source"] = [1.0 if row == col else 0.0
                                   for row in range(4) for col in range(4)]
    if bundle["header"]["status"] != "valid" or not available:
        return dict(header=_header(bundle, "perception.occupancy:" +
                                    bundle["header"]["sample_id"], "unavailable",
                                    "transform_unavailable" if not available else
                                    "sensor_bundle_unavailable"), voxels=[],
                    resolution=list(resolution), shape=list(shape), origin=list(origin),
                    context=context,
                    observed_domain_source="fixture_radar_point")
    if len(resolution) != 3 or len(shape) != 3 or len(origin) != 3:
        raise ValueError("resolution, shape and origin must have three values")
    if (any(not math.isfinite(value) for value in tuple(resolution) + tuple(origin)) or
            any(value <= 0 for value in resolution) or
            any(int(value) != value or value <= 0 for value in shape)):
        raise ValueError("invalid occupancy grid geometry")
    if len(transform) != 16 or any(not math.isfinite(value) for value in transform):
        raise ValueError("invalid radar to odom transform")
    if any(abs(a-b) > 1e-9 for a, b in zip(transform[12:], (0, 0, 0, 1))):
        raise ValueError("radar transform must be homogeneous")
    for row in range(3):
        for col in range(3):
            dot = sum(transform[4*row+k] * transform[4*col+k] for k in range(3))
            if abs(dot - (1.0 if row == col else 0.0)) > 1e-6:
                raise ValueError("radar transform rotation must be orthonormal")
    if rolling_grid:
        body = context["T_mapping_body"]
        if len(body) != 16 or any(not math.isfinite(value) for value in body):
            raise ValueError("invalid observation-time body transform")
        if any(abs(a-b) > 1e-9 for a, b in zip(body[12:], (0, 0, 0, 1))):
            raise ValueError("body transform must be homogeneous")
        origin = tuple(float(origin[axis]) + math.floor(
            (body[4*axis+3] - origin[axis] - shape[axis]*resolution[axis]/2) /
            resolution[axis] + .5) * resolution[axis] for axis in range(3))
        if any(not math.isfinite(value) for value in origin):
            raise ValueError("invalid moving observation grid origin")
    voxels = []
    for point in bundle["radar"]["points"]:
        radar_point = (point["x"], point["y"], point["z"], 1.0)
        coordinates = [sum(transform[4 * axis + col] * radar_point[col] for col in range(4))
                       for axis in range(3)]
        index = tuple(int(math.floor((float(coordinates[axis]) - origin[axis]) /
                                  resolution[axis])) for axis in range(3))
        if any(index[axis] < 0 or index[axis] >= int(shape[axis]) for axis in range(3)):
            continue
        voxels.append(dict(index=list(index), probability=0.9, observed=True,
                           confidence=None, uncertainty=dict(status="unavailable",
                           kind="", value=None, unit="", source="fixture placeholder")))
    if len({tuple(item["index"]) for item in voxels}) != len(voxels):
        raise ValueError("duplicate occupancy voxel")
    return dict(header=_header(bundle, "perception.occupancy:" + bundle["header"]["sample_id"]),
                voxels=voxels, resolution=list(resolution), shape=[int(value) for value in shape],
                origin=[float(value) for value in origin], context=context,
                observed_domain_source="fixture_radar_point")
