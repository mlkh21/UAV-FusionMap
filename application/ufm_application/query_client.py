"""Preserve public map states; never infer free space from a failed query."""
import copy
import math
import struct


class QueryTransportError(OSError):
    """Transport could not provide a public MapQueryResult."""


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate_quality(result):
    confidence = result['confidence']
    if confidence is not None and (not _finite(confidence) or not 0 <= confidence <= 1):
        raise ValueError('invalid query confidence')
    quality = result['uncertainty']
    if quality is None:  # Legacy public unavailable representation.
        return
    if not isinstance(quality, dict) or quality['status'] not in ('available', 'unavailable'):
        raise ValueError('invalid query uncertainty status')
    available = quality['status'] == 'available'
    for key in ('kind', 'unit', 'source'):
        if not isinstance(quality[key], str) or (available and not quality[key].strip()):
            raise ValueError('invalid query uncertainty metadata')
    values = quality['value']
    if not available:
        if values is not None:
            raise ValueError('unavailable query uncertainty must have value None')
        return
    if not isinstance(values, (list, tuple)) or not values or any(not _finite(v) for v in values):
        raise ValueError('invalid query uncertainty values')
    if quality['kind'] == 'occupancy_variance' and (len(values) != 1 or values[0] < 0):
        raise ValueError('invalid occupancy variance')
    if quality['kind'] == 'occupancy_probability_interval':
        if (quality['unit'] != 'dimensionless' or len(values) != 2 or
                not 0 <= values[0] <= values[1] <= 1):
            raise ValueError('invalid occupancy probability interval')
        probability = result['probability']
        if probability is None:
            raise ValueError('probability interval lacks nominal probability')
        def round32(value):
            return struct.unpack('!f', struct.pack('!f', value))[0]
        # Accept exact logical containment or the nearest-even float32 wire image.
        if not (values[0] <= probability <= values[1] or
                probability == round32(probability) and
                round32(values[0]) <= probability <= round32(values[1])):
            raise ValueError('probability interval excludes nominal probability')


def _validate_request(request):
    for key in ('map_id', 'frame_id', 'run_id', 'clock_id'):
        if not isinstance(request[key], str) or not request[key].strip():
            raise ValueError('query requires ' + key)
    for key in ('query_timestamp', 'max_age_ns'):
        if type(request[key]) is not int or not 0 <= request[key] < 2**63:
            raise ValueError('query requires nonnegative int64 ' + key)
    point = request['point']
    if len(point) != 3 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or
                            not math.isfinite(value) for value in point):
        raise ValueError('query point must be finite XYZ metres')


def unavailable(request, reason):
    return dict(map_id=request['map_id'], revision=0, run_id=request['run_id'],
        clock_id=request['clock_id'], frame_id=request['frame_id'],
        query_timestamp=request['query_timestamp'], point=list(request['point']),
        status='unavailable', reason=reason, observed=False, index=None, probability=None,
        confidence=None, last_observed_timestamp=None,
        uncertainty=dict(status='unavailable', kind='', value=None, unit='', source=''))


class MapQueryClient:
    def __init__(self, transport):
        self.transport = transport

    def query(self, **request):
        _validate_request(request)
        try:
            result = self.transport(copy.deepcopy(request))
        except (OSError, TimeoutError) as exc:
            return unavailable(request, 'map_query_transport_unavailable:' + type(exc).__name__)
        except ValueError as exc:
            return unavailable(request, 'map_query_response_invalid:' + str(exc))
        try:
            if result['status'] not in ('occupied', 'free', 'unknown', 'stale', 'unavailable'):
                raise ValueError('unknown map status')
            for key in ('run_id', 'clock_id', 'frame_id', 'query_timestamp'):
                if result[key] != request[key]:
                    raise ValueError('query response identity or time mismatch')
            if list(result['point']) != list(request['point']):
                raise ValueError('query response point mismatch')
            if result['status'] != 'unavailable' and result['map_id'] != request['map_id']:
                raise ValueError('query response map mismatch')
            probability = result['probability']
            if probability is not None and (isinstance(probability, bool) or
                    not isinstance(probability, (int, float)) or not math.isfinite(probability) or
                    not 0 <= probability <= 1):
                raise ValueError('invalid query probability')
            stamp = result['last_observed_timestamp']
            if type(result['observed']) is not bool or (stamp is not None and (
                    type(stamp) is not int or not 0 <= stamp <= request['query_timestamp'])):
                raise ValueError('invalid query evidence time or observed flag')
            if result['status'] in ('occupied', 'free') and (result['observed'] is not True or
                    result['probability'] is None or result['last_observed_timestamp'] is None):
                raise ValueError('classified result lacks evidence')
            if result['status'] not in ('occupied', 'free') and not result['reason']:
                raise ValueError('query failure or unknown reason missing')
            _validate_quality(result)
            # Keep the complete public result, including stale historical probability and quality.
            return copy.deepcopy(result)
        except (ValueError, KeyError, TypeError) as exc:
            return unavailable(request, 'map_query_response_invalid:' + str(exc))
