"""Offline structural recording contract. No writer, replay engine or provider."""
from pathlib import Path

from ufm_terrain_contract.bounds import (MESSAGE_BYTES, RECORDING_BYTES, REQUEST_BYTES,
    bounded_json, decode_json, fields, integer, reason, read_json, text)
from ufm_terrain_contract.contract import validate_request, validate_result, validate_status
from .terrain_dataset import dataset_context, validate_dataset

LIMITS = dict(max_datasets=64, max_events=64, max_dataset_bytes=REQUEST_BYTES,
              max_record_bytes=MESSAGE_BYTES, max_recording_bytes=RECORDING_BYTES)
HEADER = 'event_sequence record_elapsed_ns operation run_timestamp_available run_timestamp'
OPERATIONS = {
    'clock_observed': '',
    'clock_transport': 'online',
    'install': ('attempt_id dataset_ref attempt input_recorded input_reason outcome reason '
                'revision_before revision_after'),
    'query': 'request result',
    'disable': 'reason status',
    'status_change': 'status',
}


def _boolean(value):
    if type(value) is not bool:
        raise ValueError('terrain_record_boolean')


def validate_recording(manifest, datasets, events, require_complete=True):
    """Validate saved claims/structure, not replay consistency or external truth."""
    fields(manifest, 'schema_version profile recording_id provider_instance_id run_id clock_id mode '
                     'event_count recording_complete limits')
    bounded_json(manifest, MESSAGE_BYTES)
    if (manifest['schema_version'] != 'ufm.terrain.recording.v1' or manifest['profile'] != 'm5_fixture_v1' or
            manifest['mode'] != 'recorded'):
        raise ValueError('terrain_recording_schema_or_mode')
    for key in ('recording_id', 'provider_instance_id', 'run_id', 'clock_id'):
        text(manifest[key])
    if manifest['clock_id'] != 'sim:' + manifest['run_id']:
        raise ValueError('terrain_recording_clock_domain')
    fields(manifest['limits'], ' '.join(LIMITS))
    if any(type(manifest['limits'][k]) is not int or manifest['limits'][k] != v for k, v in LIMITS.items()):
        raise ValueError('terrain_recording_limits')
    _boolean(manifest['recording_complete'])
    integer(manifest['event_count'], 64)
    if (type(datasets) is not list or len(datasets) > 64 or type(events) is not list or len(events) > 64 or
            manifest['event_count'] != len(events)):
        raise ValueError('terrain_recording_counts')
    refs = {}
    total = len(bounded_json(manifest, MESSAGE_BYTES))
    total += len(bounded_json(datasets, RECORDING_BYTES))
    for entry in datasets:
        fields(entry, 'dataset_ref dataset')
        integer(entry['dataset_ref'], 64)
        if entry['dataset_ref'] in refs:
            raise ValueError('terrain_duplicate_dataset_ref')
        validate_dataset(entry['dataset'])
        reg = entry['dataset']['registration']
        if any(reg[k] != manifest[k] for k in ('run_id', 'clock_id')):
            raise ValueError('terrain_recording_dataset_domain')
        refs[entry['dataset_ref']] = entry['dataset']
    elapsed, attempt_id, revision, sequence = -1, 0, 0, 0
    incomplete_input, committed_context = False, None
    for index, event in enumerate(events):
        total += len(bounded_json(event, MESSAGE_BYTES)) + 1
        if total > RECORDING_BYTES:
            raise ValueError('terrain_recording_byte_limit')
        operation = event.get('operation') if type(event) is dict else None
        if type(operation) is not str or operation not in OPERATIONS:
            raise ValueError('terrain_event_operation')
        fields(event, HEADER + ' ' + OPERATIONS[operation])
        integer(event['event_sequence'], 64)
        integer(event['record_elapsed_ns'])
        if event['event_sequence'] != index or event['record_elapsed_ns'] < elapsed:
            raise ValueError('terrain_event_sequence_or_elapsed')
        elapsed = event['record_elapsed_ns']
        _boolean(event['run_timestamp_available'])
        integer(event['run_timestamp'])
        if not event['run_timestamp_available'] and event['run_timestamp'] != 0:
            raise ValueError('terrain_absent_event_time')
        if operation == 'clock_observed' and not event['run_timestamp_available']:
            raise ValueError('terrain_clock_event_time')
        if operation == 'clock_transport':
            _boolean(event['online'])
        if operation == 'install':
            integer(event['attempt_id'], 64)
            integer(event['revision_before'], 64)
            integer(event['revision_after'], 64)
            if event['attempt_id'] != attempt_id + 1 or event['revision_before'] != revision:
                raise ValueError('terrain_attempt_or_revision_sequence')
            attempt_id = event['attempt_id']
            outcome = event['outcome']
            if outcome not in ('installed', 'idempotent', 'rejected'):
                raise ValueError('terrain_install_outcome')
            reason(event['reason'])
            reason(event['input_reason'])
            _boolean(event['input_recorded'])
            if not event['input_recorded']:
                incomplete_input = True
                if event['dataset_ref'] is not None or event['attempt'] is not None or not event['input_reason']:
                    raise ValueError('terrain_missing_attempt_slots')
            else:
                if event['input_reason'] or (event['dataset_ref'] is None) == (event['attempt'] is None):
                    raise ValueError('terrain_attempt_input_ambiguity')
                if event['dataset_ref'] is not None:
                    integer(event['dataset_ref'], 64)
                    if event['dataset_ref'] not in refs:
                        raise ValueError('terrain_missing_dataset_ref')
                elif outcome != 'rejected' or type(event['attempt']) is not dict:
                    raise ValueError('terrain_raw_attempt_not_a_dataset')
                else:
                    bounded_json(event['attempt'], REQUEST_BYTES)
            if outcome == 'installed':
                if not event['run_timestamp_available'] or not event['input_recorded'] or event['dataset_ref'] is None:
                    raise ValueError('terrain_install_missing_input_or_time')
                revision += 1
                committed_context = dataset_context(refs[event['dataset_ref']], event['run_timestamp'])
            if (event['revision_after'] != revision or revision >= 2**64 or
                    outcome == 'idempotent' and revision == 0 or outcome == 'rejected' and not event['reason']):
                raise ValueError('terrain_install_revision_or_reason')
        if operation == 'query':
            validate_request(event['request'])
            validate_result(event['result'], event['request'], manifest['provider_instance_id'])
            result = event['result']
            if result['status'] != 'unavailable' and (result['terrain_revision'] != revision or
                    result['context'] != committed_context):
                raise ValueError('terrain_query_committed_context')
            if (event['run_timestamp_available'] != (result['evaluation_timestamp'] is not None) or
                    event['run_timestamp_available'] and event['run_timestamp'] != result['evaluation_timestamp']):
                raise ValueError('terrain_query_event_time')
        if operation in ('disable', 'status_change'):
            status = event['status']
            validate_status(status)
            if (status['provider_instance_id'] != manifest['provider_instance_id'] or
                    any(status[k] != manifest[k] for k in ('run_id', 'clock_id')) or
                    status['terrain_revision'] != revision or status['status_sequence'] <= sequence or
                    status['last_attempt_id'] != attempt_id or
                    status['context'] is not None and status['context'] != committed_context or
                    event['run_timestamp_available'] != (status['evaluation_timestamp'] is not None) or
                    event['run_timestamp_available'] and event['run_timestamp'] != status['evaluation_timestamp']):
                raise ValueError('terrain_status_event_binding')
            sequence = status['status_sequence']
            if operation == 'disable':
                reason(event['reason'])
                if status['state'] != 'disabled' or not event['reason'] or event['reason'] != status['reason']:
                    raise ValueError('terrain_disable_state')
    if incomplete_input and manifest['recording_complete']:
        raise ValueError('terrain_missing_input_marked_complete')
    if require_complete and not manifest['recording_complete']:
        raise ValueError('terrain_recording_incomplete')


def load_recording(directory, require_complete=True):
    """Bound the whole three-file directory and each line before decoding JSON."""
    directory = Path(directory)
    paths = {p.name: p for p in directory.iterdir()}
    if set(paths) != {'manifest.json', 'datasets.json', 'events.jsonl'} or any(not p.is_file() for p in paths.values()):
        raise ValueError('terrain_recording_files')
    if sum(p.stat().st_size for p in paths.values()) > RECORDING_BYTES:
        raise ValueError('terrain_recording_input_limit')
    manifest = read_json(paths['manifest.json'], MESSAGE_BYTES)
    datasets = read_json(paths['datasets.json'], RECORDING_BYTES)
    events = []
    total = paths['manifest.json'].stat().st_size + paths['datasets.json'].stat().st_size
    with paths['events.jsonl'].open('rb') as stream:
        while True:
            line = stream.readline(MESSAGE_BYTES + 2)
            if not line:
                break
            total += len(line)
            if len(events) == 64 or len(line) > MESSAGE_BYTES + 1 or total > RECORDING_BYTES or not line.endswith(b'\n'):
                raise ValueError('terrain_event_input_limit_or_truncated_line')
            events.append(decode_json(line[:-1], MESSAGE_BYTES))
    validate_recording(manifest, datasets, events, require_complete)
    return manifest, datasets, events
