"""Thin PointCloud2 decoder for the explicitly declared fixture-only Radar adapter."""
from sensor_msgs import point_cloud2
from sensor_msgs.msg import PointCloud2, PointField
from ufm_sensors.radar_raw_adapter import _semantics, adapt_radar_rows


def decode_radar_cloud(cloud, profile, identity):
    names = _semantics(profile)
    if not isinstance(identity, dict):
        raise ValueError('Radar acquisition identity required')
    if (not isinstance(cloud, PointCloud2) or cloud.header.frame_id != profile['frame_id']
            or cloud.header.stamp.to_nsec() != identity.get('scan_start_ns')
            or cloud.point_step <= 0 or cloud.row_step < cloud.width*cloud.point_step
            or len(cloud.data) != cloud.row_step*cloud.height):
        raise ValueError('Radar PointCloud2 frame, timestamp or layout mismatch')
    by_name = {}
    for field in cloud.fields:
        if field.name in by_name:
            raise ValueError('ambiguous duplicate PointField name')
        by_name[field.name] = field
    if set(by_name) != set(names):
        raise ValueError('undeclared PointField might contain point time or unknown units')
    spans = []
    for name in names:
        field = by_name.get(name)
        width = {PointField.FLOAT32:4, PointField.FLOAT64:8}.get(field.datatype) if field else None
        if (width is None or field.count != 1 or field.offset < 0
                or field.offset+width > cloud.point_step):
            raise ValueError('mapped Radar fields require scalar floats')
        spans.append((field.offset, field.offset+width))
    spans.sort()
    if any(left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError('Radar PointField byte regions overlap')
    try:
        rows = (dict(zip(names, values)) for values in
                point_cloud2.read_points(cloud, field_names=names, skip_nans=False))
        return adapt_radar_rows(rows, profile, dict(identity, timestamp_ns=cloud.header.stamp.to_nsec()))
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError('invalid Radar PointCloud2 payload') from exc
