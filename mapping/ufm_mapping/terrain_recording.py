"""Create-only public terrain recorder and deterministic offline operation replay."""
import copy
import os
from pathlib import Path
import threading
import time
import uuid
from functools import wraps

from ufm_terrain_contract.bounds import MESSAGE_BYTES, RECORDING_BYTES, REQUEST_BYTES, bounded_json
from .terrain_dataset import validate_dataset
from .terrain_provider import TerrainProvider
from .terrain_recording_contract import LIMITS, load_recording, validate_recording


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._io_lock:
            return method(self, *args, **kwargs)
    return call


class TerrainRecorder:
    def __init__(self, directory, dataset, provider_instance_id):
        validate_dataset(dataset)
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self._io_lock = threading.RLock()
        reg = dataset['registration']
        self.manifest = dict(schema_version='ufm.terrain.recording.v1', profile='m5_fixture_v1',
            recording_id=str(uuid.uuid4()), provider_instance_id=provider_instance_id,
            run_id=reg['run_id'], clock_id=reg['clock_id'], mode='recorded', event_count=0,
            recording_complete=False, limits=dict(LIMITS))
        self.datasets = [dict(dataset_ref=0, dataset=copy.deepcopy(dataset))]
        self.events = []
        self.failed, self.error, self.closed = False, '', False
        self._persist()

    def _persist(self):
        manifest = bounded_json(self.manifest, MESSAGE_BYTES)
        datasets = bounded_json(self.datasets, RECORDING_BYTES)
        events = b''.join(bounded_json(e, MESSAGE_BYTES) + b'\n' for e in self.events)
        if len(manifest) + len(datasets) + len(events) > RECORDING_BYTES:
            raise ValueError('terrain_recording_byte_limit')
        # Manifest remains incomplete until both content files are fully replaced.
        for name, payload in (('datasets.json', datasets), ('events.jsonl', events), ('manifest.json', manifest)):
            temporary = self.directory / (name + '.pending')
            with temporary.open('wb') as handle:
                handle.write(payload)
                handle.flush()
            os.replace(str(temporary), str(self.directory / name))

    @_serialized
    def fail(self, code):
        self.failed, self.error = True, code
        self.manifest['recording_complete'] = False
        try: self._persist()
        except (OSError, ValueError): pass  # Previous incomplete manifest remains on disk.

    @_serialized
    def append(self, event, dataset=None):
        if self.closed or self.failed:
            return False
        try:
            if len(self.events) == 64:
                raise ValueError('terrain_recording_event_limit')
            event = copy.deepcopy(event)
            if dataset is not None:
                try:
                    validate_dataset(dataset)
                    encoded = bounded_json(dataset, REQUEST_BYTES)
                    ref = next((entry['dataset_ref'] for entry in self.datasets
                                if bounded_json(entry['dataset'], REQUEST_BYTES) == encoded), None)
                    if ref is None:
                        if len(self.datasets) == 64:
                            raise ValueError('terrain_recording_dataset_limit')
                        ref = len(self.datasets)
                        self.datasets.append(dict(dataset_ref=ref, dataset=copy.deepcopy(dataset)))
                    event.update(dataset_ref=ref, attempt=None, input_recorded=True, input_reason='')
                except ValueError:
                    try:
                        bounded_json(dataset, REQUEST_BYTES)
                        if type(dataset) is not dict: raise ValueError('terrain_attempt_type')
                        event.update(dataset_ref=None, attempt=copy.deepcopy(dataset), input_recorded=True, input_reason='')
                    except ValueError:
                        event.update(dataset_ref=None, attempt=None, input_recorded=False, input_reason='input_unrecordable')
                        self.manifest['recording_complete'] = False
                        self.failed, self.error = True, 'input_unrecordable'
            event['event_sequence'] = len(self.events)
            bounded_json(event, MESSAGE_BYTES)
            self.events.append(event)
            self.manifest['event_count'] = len(self.events)
            validate_recording(self.manifest, self.datasets, self.events, require_complete=False)
            self._persist()
            return not self.failed
        except (ValueError, OSError, TypeError, RecursionError):
            self.fail('recording_write_or_limit_failed')
            return False

    @_serialized
    def close(self):
        if self.closed:
            return not self.failed
        try:
            if not self.failed:
                self.manifest['recording_complete'] = True
                validate_recording(self.manifest, self.datasets, self.events)
                self._persist()
        except (OSError, ValueError):
            self.fail('recording_finalize_failed')
        self.closed = True
        return not self.failed


class RecordedTerrainProvider:
    """Serialize operation receipts with provider actions; recording failures do not stop terrain."""
    def __init__(self, dataset, run_id, clock_id, directory, monotonic_ns=time.monotonic_ns):
        self.provider = TerrainProvider(dataset, run_id, clock_id, enabled=True, monotonic_ns=monotonic_ns)
        self.recorder = TerrainRecorder(directory, dataset, self.provider.provider_instance_id)
        self._lock = threading.RLock()
        self._now, self._origin = monotonic_ns, monotonic_ns()
        self._clock, self._revision = None, 0
        self._source, self._last_status = None, None
        self._template = copy.deepcopy(dataset)

    @property
    def provider_instance_id(self):
        return self.provider.provider_instance_id

    def _event(self, operation, **values):
        return dict(record_elapsed_ns=self._now() - self._origin, operation=operation,
            run_timestamp_available=self._clock is not None, run_timestamp=self._clock or 0, **values)

    def set_clock_source(self, available, failure_reason='clock_source_unavailable'):
        with self._lock:
            self.provider.set_clock_source(available, failure_reason)
            if self._source != available:
                # v1 only records transport availability. Rich source-failure reasons
                # cannot be reconstructed from its bool, so fail completeness explicitly.
                if not available and self._clock is not None and failure_reason != 'clock_transport_unavailable':
                    self.recorder.fail('source_failure_not_representable_in_v1')
                self.recorder.append(self._event('clock_transport', online=available))
                self._source = available

    def observe_clock(self, timestamp, received_ns=None):
        with self._lock:
            accepted = self.provider.observe_clock(timestamp, received_ns)
            if accepted:
                self._clock = timestamp
                self.recorder.append(self._event('clock_observed'))
            return accepted

    def _install_receipt(self, receipt, dataset):
        if receipt is not None:
            self.recorder.append(self._event('install', attempt_id=receipt['attempt_id'],
                dataset_ref=None, attempt=None, input_recorded=False, input_reason='',
                outcome=receipt['outcome'], reason=receipt['reason'], revision_before=self._revision,
                revision_after=receipt['terrain_revision']), dataset)
            self._revision = receipt['terrain_revision']
        return receipt

    def install(self, dataset):
        with self._lock:
            return self._install_receipt(self.provider.install(dataset), dataset)

    def startup_install(self):
        with self._lock:
            return self._install_receipt(self.provider.startup_install(), self._template)

    def query(self, request):
        if not self._lock.acquire(blocking=False):
            self.recorder.fail('concurrent_busy_not_recorded')
            return self.provider.busy_result(request)
        try:
            result = self.provider.query(request)
            self.recorder.append(self._event('query', request=request, result=result))
            return result
        except Exception:
            self.recorder.fail('query_failure_not_representable_in_v1')
            raise
        finally:
            self._lock.release()

    def busy_result(self, request):
        self.recorder.fail('concurrent_busy_not_recorded')
        return self.provider.busy_result(request)

    def status(self):
        with self._lock:
            result = self.provider.status()
            signature = {k: v for k, v in result.items() if k not in ('status_sequence', 'evaluation_timestamp')}
            if signature != self._last_status:
                self.recorder.append(self._event('status_change', status=result))
                self._last_status = copy.deepcopy(signature)
            return result

    def disable(self):
        with self._lock:
            self.provider.disable()
            result = self.provider.status()
            self.recorder.append(self._event('disable', reason=result['reason'], status=result))

    def close_recording(self):
        with self._lock:
            return self.recorder.close()


def replay_recording(directory):
    manifest, datasets, events = load_recording(directory)
    if not datasets or datasets[0]['dataset_ref'] != 0:
        raise ValueError('terrain_recording_initial_dataset_missing')
    elapsed = [0]
    provider = TerrainProvider(datasets[0]['dataset'], manifest['run_id'], manifest['clock_id'],
                               enabled=True, monotonic_ns=lambda: elapsed[0])
    refs = {item['dataset_ref']: item['dataset'] for item in datasets}
    original_id, replay_id = manifest['provider_instance_id'], provider.provider_instance_id
    results, statuses, sequence = [], [], 0
    for event in events:
        elapsed[0] = event['record_elapsed_ns']
        op = event['operation']
        if op == 'clock_transport':
            provider.set_clock_source(event['online'], 'clock_transport_unavailable')
        elif op == 'clock_observed':
            if not provider.observe_clock(event['run_timestamp']):
                raise ValueError('terrain_replay_unaccepted_clock')
        elif op == 'install':
            dataset = refs[event['dataset_ref']] if event['dataset_ref'] is not None else event['attempt']
            receipt = provider.install(dataset)
            expected = dict(attempt_id=event['attempt_id'], outcome=event['outcome'], reason=event['reason'],
                            terrain_revision=event['revision_after'])
            if receipt != expected:
                raise ValueError('terrain_replay_install_differs')
        elif op == 'query':
            request = copy.deepcopy(event['request'])
            if request['expected_provider_instance_id'] == original_id:
                request['expected_provider_instance_id'] = replay_id
            result = provider.query(request)
            result['provider_instance_id'] = original_id
            if result != event['result']:
                raise ValueError('terrain_replay_query_differs')
            results.append(result)
        elif op in ('status_change', 'disable'):
            if op == 'disable': provider.disable()
            wanted = event['status']['status_sequence']
            if not 0 < wanted - sequence <= 4096:
                raise ValueError('terrain_replay_status_gap_limit')
            while sequence < wanted:
                status = provider.status()
                sequence += 1
            status['provider_instance_id'] = original_id
            if status != event['status']:
                raise ValueError('terrain_replay_status_differs')
            statuses.append(status)
    return dict(mode='recorded', playback_session_id=str(uuid.uuid4()),
        provider_instance_id=original_id, results=results, statuses=statuses, event_count=len(events), passed=True)
