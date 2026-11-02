"""Public terrain consumer with heartbeat proof and atomic pinned sample groups."""
import copy
from fractions import Fraction as F
import threading
import time

from ufm_terrain_contract.contract import validate_request, validate_result, validate_status


def local_unavailable(request, reason):
    value = {k: copy.deepcopy(request[k]) for k in
             ('terrain_id', 'run_id', 'clock_id', 'frame_id', 'query_timestamp', 'point_xy')}
    quality = dict(status='unavailable', kind='', value=None, unit='', source='')
    value.update(protocol_version=1, provider_instance_id='', terrain_revision=0, evaluation_timestamp=None,
        status='unavailable', reason=reason, context=None, height=None, source_index=None, source_xy=None,
        height_quality=quality, sample_quality=copy.deepcopy(quality))
    return value


class TerrainClient:
    def __init__(self, transport, terrain_id, run_id, clock_id, monotonic=time.monotonic):
        validate_request(dict(terrain_id=terrain_id, run_id=run_id, clock_id=clock_id, frame_id='map',
            query_timestamp=0, point_xy=[0., 0.], pin_version=False, expected_provider_instance_id='', expected_terrain_revision=0))
        self.transport, self._now = transport, monotonic
        self.domain = dict(terrain_id=terrain_id, run_id=run_id, clock_id=clock_id, frame_id='map')
        self._lock = threading.RLock()
        self._status = None
        self._receipt, self._proof = 0., False
        self._generation = 0
        self._group = None

    def _clear(self):
        self._generation += 1
        self._group = None

    def invalidate(self):
        with self._lock:
            self._clear()
            self._proof = False

    def receive_status(self, value):
        try:
            validate_status(value)
            if any(value[k] != v for k, v in self.domain.items()):
                raise ValueError('terrain_status_domain')
        except (ValueError, TypeError, KeyError):
            self.invalidate()
            return False
        with self._lock:
            previous = self._status
            same = previous is not None and previous['provider_instance_id'] == value['provider_instance_id']
            advancing = same and value['status_sequence'] > previous['status_sequence']
            if same and (not advancing or value['terrain_revision'] < previous['terrain_revision']):
                self._clear()
                self._proof = False
                return False
            changed = (not same or previous['terrain_revision'] != value['terrain_revision'] or
                       previous['state'] != value['state'] or previous['context'] != value['context'])
            if changed:
                self._clear()
            self._proof = bool(advancing)
            self._status, self._receipt = copy.deepcopy(value), self._now()
            if value['state'] not in ('current', 'expired'):
                self._group = None
            return self._proof

    def _live_status(self):
        if self._status is None or self._now() - self._receipt >= 1.5:
            self._clear()
            self._proof = False
            return None
        return self._status

    def query(self, request):
        validate_request(request)
        with self._lock:
            generation = self._generation
            status = self._live_status()
            generation = self._generation
            instance = status['provider_instance_id'] if status else None
        try:
            value = self.transport(copy.deepcopy(request))
            validate_result(value, request, instance)
        except (OSError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
            self.invalidate()
            return local_unavailable(request, 'terrain_query_transport_or_response_invalid')
        with self._lock:
            if generation != self._generation:
                return local_unavailable(request, 'terrain_response_superseded')
            if value['status'] == 'unavailable':
                self._group = None
            elif status is not None:
                self._proof = True  # An active response proves this instance replied.
            return copy.deepcopy(value)

    def sample_group(self):
        with self._lock:
            status = self._live_status()
            if status is None or status['state'] not in ('current', 'expired') or status['context'] is None:
                self._group = None
                return None
            context = copy.deepcopy(status['context'])
            instance, revision, stamp = status['provider_instance_id'], status['terrain_revision'], status['evaluation_timestamp']
            generation = self._generation
        a, matrix = context['affine'], context['T_map_terrain']
        results = []
        for row in range(context['rows']):
            for col in range(context['columns']):
                point = [float(F(str(a[0])) + (F(col) + F(1, 2)) * F(str(a[1])) + F(str(matrix[3]))),
                         float(F(str(a[3])) + (F(row) + F(1, 2)) * F(str(a[5])) + F(str(matrix[7])))]
                request = dict(self.domain, query_timestamp=stamp, point_xy=point, pin_version=True,
                    expected_provider_instance_id=instance, expected_terrain_revision=revision)
                result = self.query(request)
                with self._lock:
                    current = self._live_status()
                    valid = (generation == self._generation and current is not None and self._proof and
                        result['status'] != 'unavailable' and result['provider_instance_id'] == instance and
                        result['terrain_revision'] == revision and result['context'] == context and
                        (result['status']=='stale') == (status['state']=='expired'))
                    if not valid:
                        self._group = None
                        return None
                results.append(result)
        with self._lock:
            if generation != self._generation or self._live_status() is None:
                self._group = None
                return None
            group = dict(mode='live', provider_instance_id=instance, terrain_revision=revision,
                         context=context, results=results)
            self._group = group
            return copy.deepcopy(group)

    def current_group(self):
        with self._lock:
            if self._live_status() is None or not self._proof:
                return None
            return copy.deepcopy(self._group)
