"""Single-point map query ROS encoding; no map cache or classification logic."""
from .perf01a_codec import _uncertainty, _uncertainty_dict


STATUS = {'occupied': 0, 'free': 1, 'unknown': 2, 'stale': 3, 'unavailable': 4}
REVERSE_STATUS = {value: key for key, value in STATUS.items()}


def from_ros_query_request(message):
    return dict(map_id=message.map_id, frame_id=message.frame_id,
                run_id=message.run_id, clock_id=message.clock_id,
                query_timestamp=message.query_timestamp, point=list(message.point),
                max_age_ns=message.max_age_ns)


def to_ros_query_result(value):
    from uav_fusionmap_msgs.msg import MapQueryResult
    message = MapQueryResult()
    for key in ('map_id', 'revision', 'run_id', 'clock_id', 'frame_id',
                'query_timestamp', 'reason', 'observed'):
        setattr(message, key, value[key])
    if value['status'] not in STATUS:
        raise ValueError('unknown map query status')
    message.status = STATUS[value['status']]
    message.point = list(value['point'])
    message.index_available = value['index'] is not None
    message.index = list(value['index']) if message.index_available else [0, 0, 0]
    for key in ('probability', 'confidence', 'last_observed_timestamp'):
        available = value[key] is not None
        setattr(message, key + '_available', available)
        setattr(message, key, value[key] if available else 0)
    _uncertainty(message.uncertainty, value['uncertainty'])
    return message


def from_ros_query_result(message):
    if message.status not in REVERSE_STATUS:
        raise ValueError('unknown map query status')
    result = {key: getattr(message, key) for key in
              ('map_id', 'revision', 'run_id', 'clock_id', 'frame_id',
               'query_timestamp', 'reason', 'observed')}
    result.update(status=REVERSE_STATUS[message.status], point=list(message.point),
                  index=list(message.index) if message.index_available else None,
                  uncertainty=_uncertainty_dict(message.uncertainty))
    for key in ('probability', 'confidence', 'last_observed_timestamp'):
        result[key] = getattr(message, key) if getattr(message, key + '_available') else None
    return result
