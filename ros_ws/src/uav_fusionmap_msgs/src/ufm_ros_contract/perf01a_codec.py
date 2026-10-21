"""PERF-01-A业务字典与ROS消息之间的最小编码。

这里仅负责公共消息序列化，不实现同步、感知或地图算法；消息中的业务时间保持原值。
"""
from .codec import from_ros_state, to_ros_state


SOURCE = {"simulation": 0, "measured": 1, "fixture": 2, "model": 3, "derived": 4}
STATUS = {"valid": 0, "degraded": 1, "unavailable": 2}
STATE_SOURCE = {"ground_truth": 0, "estimated": 1}
REVERSE_SOURCE = {value: key for key, value in SOURCE.items()}
REVERSE_STATUS = {value: key for key, value in STATUS.items()}
REVERSE_STATE_SOURCE = {value: key for key, value in STATE_SOURCE.items()}


def _header(msg, value):
    msg.schema_version = value["schema_version"]
    msg.timestamp = int(value["timestamp"])
    msg.clock_id = value["clock_id"]
    msg.run_id = value["run_id"]
    msg.sample_id = value["sample_id"]
    msg.frame_id = value["frame_id"]
    msg.source_type = SOURCE[value["source_type"]]
    msg.status = STATUS[value["status"]]
    msg.reason = value.get("reason", "")


def _header_dict(msg):
    return dict(schema_version=msg.schema_version, timestamp=msg.timestamp,
                clock_id=msg.clock_id, run_id=msg.run_id, sample_id=msg.sample_id,
                frame_id=msg.frame_id, source_type=REVERSE_SOURCE[msg.source_type],
                status=REVERSE_STATUS[msg.status], reason=msg.reason)


def _quality(msg, value):
    quality = value or {}
    confidence = quality.get("confidence")
    msg.confidence_available = confidence is not None
    msg.confidence = float(confidence) if confidence is not None else 0.0
    uncertainty = quality.get("uncertainty", {})
    msg.uncertainty.status = 1 if uncertainty.get("status") == "available" else 0
    msg.uncertainty.kind = uncertainty.get("kind", "")
    msg.uncertainty.value = list(uncertainty.get("value") or [])
    msg.uncertainty.unit = uncertainty.get("unit", "")
    msg.uncertainty.source = uncertainty.get("source", "")


def _quality_dict(msg):
    return dict(confidence=float(msg.confidence) if msg.confidence_available else None,
                uncertainty=dict(status="available" if msg.uncertainty.status else "unavailable",
                                  kind=msg.uncertainty.kind,
                                  value=list(msg.uncertainty.value) if msg.uncertainty.status else None,
                                  unit=msg.uncertainty.unit, source=msg.uncertainty.source))


def _uncertainty(msg, value):
    value = value or {}
    msg.status = 1 if value.get("status") == "available" else 0
    msg.kind = value.get("kind", "")
    msg.value = list(value.get("value") or [])
    msg.unit = value.get("unit", "")
    msg.source = value.get("source", "")


def _uncertainty_dict(msg):
    return dict(status="available" if msg.status else "unavailable",
                kind=msg.kind, value=list(msg.value) if msg.status else None,
                unit=msg.unit, source=msg.source)


def to_ros_radar(value):
    from uav_fusionmap_msgs.msg import RadarFrame, RadarPoint
    msg = RadarFrame()
    _header(msg.header, value["header"])
    for point in value["points"]:
        out = RadarPoint()
        out.x, out.y, out.z = point["x"], point["y"], point["z"]
        out.doppler, out.power = point.get("doppler", 0.0), point.get("power", 0.0)
        out.doppler_available = bool(point.get("doppler_available", False))
        out.power_available = bool(point.get("power_available", False))
        msg.points.append(out)
    msg.scan_start, msg.scan_end = int(value["scan_start"]), int(value["scan_end"])
    msg.power_quantity, msg.power_unit = value["power_quantity"], value["power_unit"]
    msg.doppler_reference = value["doppler_reference"]
    _quality(msg.quality, value.get("quality"))
    return msg


def from_ros_radar(msg):
    return dict(header=_header_dict(msg.header),
                points=[dict(x=p.x, y=p.y, z=p.z, doppler=p.doppler, power=p.power,
                             doppler_available=p.doppler_available,
                             power_available=p.power_available) for p in msg.points],
                scan_start=msg.scan_start, scan_end=msg.scan_end,
                power_quantity=msg.power_quantity, power_unit=msg.power_unit,
                doppler_reference=msg.doppler_reference, quality=_quality_dict(msg.quality))


def to_ros_infrared(value):
    from uav_fusionmap_msgs.msg import InfraredFrame
    msg = InfraredFrame()
    _header(msg.header, value["header"])
    msg.width, msg.height = int(value["width"]), int(value["height"])
    msg.encoding, msg.value_unit = value["encoding"], value["value_unit"]
    msg.image = list(value["image"])
    msg.exposure_start, msg.exposure_end = int(value["exposure_start"]), int(value["exposure_end"])
    msg.calibration_id = value.get("camera_info", {}).get("calibration_id", "")
    _quality(msg.quality, value.get("quality"))
    return msg


def from_ros_infrared(msg, borrow_image=False):
    return dict(header=_header_dict(msg.header), width=msg.width, height=msg.height,
                encoding=msg.encoding, value_unit=msg.value_unit,
                image=msg.image if borrow_image else list(msg.image),
                exposure_start=msg.exposure_start, exposure_end=msg.exposure_end,
                camera_info=dict(width=msg.width, height=msg.height,
                                 calibration_id=msg.calibration_id),
                quality=_quality_dict(msg.quality))


def to_ros_context(value):
    from uav_fusionmap_msgs.msg import SpatialContext
    msg = SpatialContext()
    msg.reference_timestamp = int(value["reference_timestamp"])
    msg.clock_id = value["clock_id"]
    msg.mapping_frame_id = value["mapping_frame_id"]
    msg.source_frame_id = value["source_frame_id"]
    msg.T_mapping_source = list(value["T_mapping_source"])
    msg.T_mapping_source_status = 1 if value["T_mapping_source_status"] == "available" else 0
    msg.T_mapping_body = list(value["T_mapping_body"])
    msg.T_mapping_body_status = 1 if value["T_mapping_body_status"] == "available" else 0
    msg.calibration_id = value["calibration_id"]
    msg.state_source = value["state_source"]
    _uncertainty(msg.pose_uncertainty, value.get("pose_uncertainty"))
    return msg


def from_ros_context(msg):
    return dict(reference_timestamp=msg.reference_timestamp, clock_id=msg.clock_id,
                mapping_frame_id=msg.mapping_frame_id, source_frame_id=msg.source_frame_id,
                T_mapping_source=list(msg.T_mapping_source),
                T_mapping_source_status="available" if msg.T_mapping_source_status else "unavailable",
                T_mapping_body=list(msg.T_mapping_body),
                T_mapping_body_status="available" if msg.T_mapping_body_status else "unavailable",
                calibration_id=msg.calibration_id, state_source=msg.state_source,
                pose_uncertainty=_uncertainty_dict(msg.pose_uncertainty))


def to_ros_bundle(value):
    from uav_fusionmap_msgs.msg import SensorBundle
    msg = SensorBundle()
    _header(msg.header, value["header"])
    msg.radar = to_ros_radar(value["radar"])
    msg.infrared = to_ros_infrared(value["infrared"])
    msg.state = to_ros_state(value["state"])
    msg.context = to_ros_context(value["context"])
    msg.calibration_id = value["calibration_id"]
    msg.radar_ir_delta_ns = int(value["radar_ir_delta_ns"])
    msg.pose_age_ns = int(value["pose_age_ns"])
    return msg


def from_ros_bundle(msg):
    return dict(header=_header_dict(msg.header), radar=from_ros_radar(msg.radar),
                infrared=from_ros_infrared(msg.infrared), state=from_ros_state(msg.state),
                context=from_ros_context(msg.context), calibration_id=msg.calibration_id,
                radar_ir_delta_ns=msg.radar_ir_delta_ns, pose_age_ns=msg.pose_age_ns)


def to_ros_occupancy(value):
    from uav_fusionmap_msgs.msg import OccupancyObservation, OccupancyVoxel
    msg = OccupancyObservation()
    _header(msg.header, value["header"])
    for voxel in value["voxels"]:
        out = OccupancyVoxel()
        out.x, out.y, out.z = voxel["index"]
        out.probability = voxel["probability"]
        out.observed = bool(voxel.get("observed", False))
        out.confidence_available = voxel.get("confidence") is not None
        out.confidence = voxel.get("confidence") or 0.0
        _uncertainty(out.uncertainty, voxel.get("uncertainty"))
        msg.voxels.append(out)
    msg.resolution, msg.shape, msg.origin = list(value["resolution"]), list(value["shape"]), list(value["origin"])
    msg.context = to_ros_context(value["context"])
    msg.observed_domain_source = value["observed_domain_source"]
    return msg


def from_ros_occupancy(msg):
    return dict(header=_header_dict(msg.header),
                voxels=[dict(index=[v.x, v.y, v.z], probability=v.probability,
                             observed=v.observed,
                             confidence=v.confidence if v.confidence_available else None,
                             uncertainty=_uncertainty_dict(v.uncertainty)) for v in msg.voxels],
                resolution=list(msg.resolution), shape=list(msg.shape), origin=list(msg.origin),
                context=from_ros_context(msg.context), observed_domain_source=msg.observed_domain_source)


def to_ros_snapshot(value):
    from uav_fusionmap_msgs.msg import MapSnapshot, MapCell
    msg = MapSnapshot()
    _header(msg.header, value["header"])
    msg.map_id, msg.revision = value["map_id"], int(value["revision"])
    for cell in value["cells"]:
        out = MapCell()
        out.x, out.y, out.z = cell["index"]
        out.probability = cell["probability"]
        out.observed = cell["observed"]
        out.last_observed_timestamp = cell["last_observed_timestamp"]
        out.confidence_available = cell.get("confidence") is not None
        out.confidence = cell.get("confidence") or 0.0
        _uncertainty(out.uncertainty, cell.get("uncertainty"))
        msg.cells.append(out)
    msg.resolution, msg.shape, msg.origin, msg.coverage = list(value["resolution"]), list(value["shape"]), list(value["origin"]), list(value["coverage"])
    msg.source_types = list(value["source_types"])
    return msg


def from_ros_snapshot(msg):
    return dict(header=_header_dict(msg.header), map_id=msg.map_id, revision=msg.revision,
                cells=[dict(index=[c.x, c.y, c.z], probability=c.probability,
                            observed=c.observed, last_observed_timestamp=c.last_observed_timestamp,
                            confidence=c.confidence if c.confidence_available else None,
                            uncertainty=_uncertainty_dict(c.uncertainty))
                       for c in msg.cells], resolution=list(msg.resolution), shape=list(msg.shape),
                origin=list(msg.origin), coverage=list(msg.coverage), source_types=list(msg.source_types))
