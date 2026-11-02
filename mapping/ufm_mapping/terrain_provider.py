"""Optional serialized terrain provider; no ROS, occupancy, GIS or model imports."""
import copy
from dataclasses import dataclass
import threading
import time
import uuid

from ufm_terrain_contract.bounds import integer, reason, text
from ufm_terrain_contract.contract import (unavailable_quality, validate_request,
                                         validate_result, validate_status)
from .terrain_dataset import dataset_context, to_private_fixture, validate_dataset
from .terrain_fixture import TerrainFixture


@dataclass(frozen=True)
class _Published:
    revision: int = 0
    context: object = None


def _binding(dataset):
    return dict(identity={k: v for k, v in dataset['identity'].items() if k != 'dataset_version'},
        horizontal=dataset['horizontal'], vertical=dataset['vertical'], map_grid=dataset['map_grid'],
        registration=dataset['registration'], limits=dataset['limits'], profile=dataset['profile'],
        geometry={k: dataset['grid'][k] for k in ('rows', 'columns', 'affine', 'sample_anchor')})


class TerrainProvider:
    """Explicit run-bound provider. Queries do not advance either clock or activation."""
    def __init__(self, dataset, run_id, clock_id, enabled=False, monotonic_ns=time.monotonic_ns):
        validate_dataset(dataset)
        if type(enabled) is not bool:
            raise ValueError('terrain_enabled_flag')
        if (run_id, clock_id) != (dataset['registration']['run_id'], dataset['registration']['clock_id']):
            raise ValueError('terrain_provider_domain')
        self._instance_id = str(uuid.uuid4())
        self._domain = dict(terrain_id=dataset['identity']['terrain_id'], run_id=run_id, clock_id=clock_id, frame_id='map')
        self._template = copy.deepcopy(dataset)
        self._binding = copy.deepcopy(_binding(dataset))
        self._layer = TerrainFixture(to_private_fixture(dataset), run_id, clock_id)
        self._lock = threading.RLock()
        self._now = monotonic_ns
        self._enabled, self._locked_reason = enabled, ''
        self._clock = self._received_ns = None
        self._source_ok, self._source_reason = False, 'clock_source_unavailable'
        self._published = _Published()
        self._versions = set()
        self._status_sequence = self._attempt_id = 0
        self._last_outcome, self._last_reason = 'none', ''

    @property
    def provider_instance_id(self):
        return self._instance_id

    def set_clock_source(self, available, failure_reason='clock_source_unavailable'):
        if type(available) is not bool:
            raise ValueError('terrain_clock_source_flag')
        reason(failure_reason)
        if not failure_reason:
            raise ValueError('terrain_clock_source_reason')
        with self._lock:
            if not available:
                self._received_ns = None
            self._source_ok, self._source_reason = available, failure_reason

    def observe_clock(self, timestamp, received_ns=None):
        integer(timestamp)
        with self._lock:
            now = self._now()
            received = now if received_ns is None else received_ns
            integer(received)
            if received > now or self._received_ns is not None and received < self._received_ns:
                raise ValueError('terrain_clock_receipt_order')
            if not self._source_ok:
                return False
            if self._clock is not None and timestamp < self._clock:
                self._locked_reason = 'clock_reset_new_run_required'
            self._layer.observe_clock(timestamp)
            self._clock, self._received_ns = timestamp, received
            return True

    def _gate(self):
        if not self._enabled:
            return 'terrain_disabled'
        if self._locked_reason:
            return self._locked_reason
        if self._clock is None:
            return 'clock_unavailable'
        if not self._source_ok:
            return self._source_reason
        if self._received_ns is None or self._now() - self._received_ns >= 1_000_000_000:
            return 'clock_transport_unavailable'
        start, end = self._template['registration']['valid_interval_ns']
        if not start <= self._clock < end:
            return 'registration_unavailable'
        return ''

    def _reject(self, code):
        self._last_outcome, self._last_reason = 'rejected', code
        return dict(attempt_id=self._attempt_id, outcome='rejected', reason=code,
                    terrain_revision=self._published.revision)

    def install(self, dataset):
        """Offline multi-version entry; ROS exposes no install service or topic."""
        with self._lock:
            if self._attempt_id == 2**64 - 1:
                self._locked_reason = 'counter_exhausted_new_run_required'
                raise ValueError(self._locked_reason)
            self._attempt_id += 1
            gate = self._gate()
            if gate:
                return self._reject(gate)
            try:
                validate_dataset(dataset)
                if _binding(dataset) != self._binding:
                    self._locked_reason = 'registration_changed_new_run_required'
                    return self._reject(self._locked_reason)
                version = dataset['identity']['dataset_version']
                if version not in self._versions and len(self._versions) == 64:
                    self._locked_reason = 'version_capacity_new_run_required'
                    return self._reject(self._locked_reason)
                if self._published.revision == 2**64 - 1:
                    self._locked_reason = 'counter_exhausted_new_run_required'
                    return self._reject(self._locked_reason)
                # Prepare every public object before the private layer's commit.
                context = dataset_context(dataset, self._clock) if version not in self._versions else None
                staged = _Published(self._published.revision + 1, context)
                versions = self._versions | {version}
                changed = self._layer.install(to_private_fixture(dataset), self._clock)
            except ValueError:
                return self._reject('candidate_rejected')
            except Exception:
                self._locked_reason = 'installation_failed_new_run_required'
                self._reject('installation_failed')
                raise
            if changed:
                self._published, self._versions = staged, versions
            self._last_outcome, self._last_reason = 'installed' if changed else 'idempotent', ''
            return dict(attempt_id=self._attempt_id, outcome=self._last_outcome, reason='',
                        terrain_revision=self._published.revision)

    def startup_install(self):
        """Single startup candidate: wait before authorization, never retry a rejection."""
        with self._lock:
            if self._attempt_id or self._published.revision or self._gate():
                return None
            if self._clock < self._template['eligibility']['valid_interval_ns'][0]:
                return None
            return self.install(self._template)

    def disable(self):
        with self._lock:
            self._enabled = False
            self._layer.disable()

    def _unavailable(self, request, code, revision=0, evaluation=None):
        value = {k: copy.deepcopy(request[k]) for k in
                 ('terrain_id', 'run_id', 'clock_id', 'frame_id', 'query_timestamp', 'point_xy')}
        value.update(protocol_version=1, provider_instance_id=self._instance_id, evaluation_timestamp=evaluation,
            terrain_revision=revision, status='unavailable', reason=code, context=None, height=None,
            source_index=None, source_xy=None, height_quality=unavailable_quality(), sample_quality=unavailable_quality())
        validate_result(value, request)
        return value

    def busy_result(self, request):
        validate_request(request)
        return self._unavailable(request, 'terrain_busy')

    def query(self, request):
        validate_request(request)
        if not self._lock.acquire(blocking=False):
            return self.busy_result(request)
        try:
            published, evaluation = self._published, self._clock
            if any(request[k] != v for k, v in self._domain.items()):
                return self._unavailable(request, 'request_domain_mismatch', evaluation=evaluation)
            code = self._gate()
            if not code and request['query_timestamp'] > evaluation:
                code = 'query_ahead_of_clock'
            if not code and request['pin_version']:
                if request['expected_provider_instance_id'] != self._instance_id:
                    code = 'provider_instance_mismatch'
                elif request['expected_terrain_revision'] != published.revision:
                    code = 'revision_mismatch'
            if not code and published.context is None:
                code = 'terrain_unavailable'
            if code:
                return self._unavailable(request, code, published.revision, evaluation)
            private = self._layer.query({k: request[k] for k in
                                       ('run_id', 'clock_id', 'frame_id', 'query_timestamp', 'point_xy')})
            if private['status'] == 'unavailable':
                return self._unavailable(request, private['reason'], published.revision, evaluation)
            value = self._unavailable(request, 'pending', published.revision, evaluation)
            value.update(status=private['status'], reason=private['reason'], context=copy.deepcopy(published.context),
                height=private['height'], source_index=private['source_index'], source_xy=private['source_xy'],
                height_quality=private['height_quality'], sample_quality=(private['quality_contributors']['sample']
                    if private['quality_contributors'] is not None else unavailable_quality()))
            if evaluation >= published.context['eligibility_valid_interval_ns'][1]:
                value.update(status='stale', reason='terrain_expired')
            validate_result(value, request)
            return value
        finally:
            self._lock.release()

    def status(self):
        with self._lock:
            if self._status_sequence == 2**64 - 1:
                self._locked_reason = 'counter_exhausted_new_run_required'
                raise ValueError(self._locked_reason)
            self._status_sequence += 1
            code, context = self._gate(), None
            if code == 'terrain_disabled':
                state = 'disabled'
            elif self._locked_reason:
                state = 'locked'
            elif code == 'clock_unavailable':
                state = 'waiting_clock'
            elif code:
                state = 'unavailable'
            elif self._published.context is None:
                state = 'unavailable' if self._last_outcome == 'rejected' else 'empty'
                code = self._last_reason if state == 'unavailable' else 'terrain_unavailable'
            else:
                context = copy.deepcopy(self._published.context)
                state = 'expired' if self._clock >= context['eligibility_valid_interval_ns'][1] else 'current'
                code = 'terrain_expired' if state == 'expired' else ''
            value = dict(self._domain, protocol_version=1, provider_instance_id=self._instance_id,
                status_sequence=self._status_sequence, terrain_revision=self._published.revision,
                evaluation_timestamp=self._clock, state=state, reason=code, context=context,
                last_attempt_id=self._attempt_id, last_install_outcome=self._last_outcome,
                last_install_reason=self._last_reason)
            validate_status(value)
            return value
