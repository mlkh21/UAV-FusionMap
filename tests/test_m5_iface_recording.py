"""Public dataset/recording schema rejection, bounds and preserved source payloads."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from m5_fixture import input_cases, load_spec
from m5_iface_fixture import expected, request, result, status
from ufm_mapping.terrain_dataset import (dataset_context, from_private_fixture, load_dataset, to_private_fixture,
                                        validate_dataset)
from ufm_mapping.terrain_recording_contract import LIMITS, load_recording, validate_recording
from ufm_terrain_contract.bounds import bounded_json, decode_json


def saved_recording():
    """Explicit operation/receipt fixture; does not execute a provider or replay."""
    dataset = from_private_fixture(load_spec())
    events = [
        dict(operation='clock_observed'),
        dict(operation='clock_transport', online=True),
        dict(operation='install', attempt_id=1, dataset_ref=0, attempt=None, input_recorded=True,
             input_reason='', outcome='installed', reason='', revision_before=0, revision_after=1),
        dict(operation='query', request=request(), result=result()),
        dict(operation='status_change', status=status()),
    ]
    for i, event in enumerate(events):
        event.update(event_sequence=i, record_elapsed_ns=i * 1000,
                     run_timestamp_available=True, run_timestamp=100)
    manifest = dict(schema_version='ufm.terrain.recording.v1', profile='m5_fixture_v1', recording_id='offline-schema-a',
        provider_instance_id='terrain-instance-a', run_id='m5-fixture', clock_id='sim:m5-fixture', mode='recorded',
        event_count=len(events), recording_complete=True, limits=dict(LIMITS))
    return manifest, [dict(dataset_ref=0, dataset=dataset)], events


def write_recording(directory, values):
    manifest, datasets, events = values
    directory = Path(directory)
    directory.joinpath('manifest.json').write_bytes(bounded_json(manifest, 65536))
    directory.joinpath('datasets.json').write_bytes(bounded_json(datasets, 4 * 1024 * 1024))
    directory.joinpath('events.jsonl').write_bytes(b''.join(bounded_json(e, 65536) + b'\n' for e in events))


class TerrainPublicRecordingTest(unittest.TestCase):
    def test_public_dataset_changes_only_wrapping_and_returns_independent_copies(self):
        spec = load_spec()
        dataset = from_private_fixture(spec)
        self.assertEqual(dataset['schema_version'], 'ufm.terrain.dataset.v1')
        self.assertEqual(dataset['profile'], 'm5_fixture_v1')
        self.assertNotIn('fixture_only', dataset)
        self.assertNotIn('enabled_by_default', dataset)
        self.assertEqual(to_private_fixture(dataset), spec)
        self.assertEqual(dataset_context(dataset, 100), expected()['context'])
        dataset['grid']['heights'][0] = 9.
        self.assertEqual(spec['grid']['heights'][0], 10.)
        self.assertEqual(type(dataset['registration']['T_map_terrain'][0]), int)

    def test_all_45_frozen_private_input_cases_preserve_public_acceptance(self):
        for case in input_cases(load_spec()):
            raw = copy.deepcopy(case['spec'])
            raw.pop('fixture_only')
            raw.pop('enabled_by_default')
            raw.update(schema_version='ufm.terrain.dataset.v1', profile='m5_fixture_v1')
            with self.subTest(name=case['name']):
                if case['accepts']: validate_dataset(raw)
                else:
                    with self.assertRaises(ValueError): validate_dataset(raw)

    def test_public_dataset_rejects_private_unknown_and_training_fields_at_all_groups(self):
        dataset = from_private_fixture(load_spec())
        for changes in (dict(schema_version='m5_terrain_fixture.v1'), dict(profile='unknown'),
                        dict(fixture_only=True), dict(enabled_by_default=False)):
            with self.assertRaises(ValueError): validate_dataset(dict(dataset, **changes))
        for group in (None, 'identity', 'source_time', 'horizontal', 'vertical', 'grid', 'map_grid',
                      'registration', 'eligibility', 'limits'):
            for field in ('lidar', 'target', 'observed_mask'):
                row = copy.deepcopy(dataset)
                (row if group is None else row[group])[field] = []
                with self.subTest(group=group, field=field), self.assertRaises(ValueError): validate_dataset(row)

    def test_dataset_file_bytes_duplicates_nonfinite_and_unicode_are_checked_before_acceptance(self):
        dataset = from_private_fixture(load_spec())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dataset.json'
            path.write_bytes(bounded_json(dataset, 16384))
            self.assertEqual(load_dataset(path), dataset)
            for payload in (b' ' * 16385, b'{"profile":1,"profile":2}', b'{"height":NaN}', b'\xff',
                            b'[' * 1100 + b']' * 1100):
                path.write_bytes(payload)
                with self.assertRaises(ValueError): load_dataset(path)
        dataset['identity']['source_ref'] = '\u4e2d' * 5462
        with self.assertRaises(ValueError): validate_dataset(dataset)

    def test_complete_three_file_recording_roundtrips_as_structured_data(self):
        values = saved_recording()
        validate_recording(*values)
        with tempfile.TemporaryDirectory() as tmp:
            write_recording(tmp, values)
            self.assertEqual(load_recording(tmp), values)
        self.assertIsInstance(values[1][0]['dataset'], dict)

    def test_missing_dataset_events_bad_sequences_domains_and_versions_fail(self):
        cases = []
        for field, value in (('schema_version', 'unknown'), ('profile', 'unknown'), ('mode', 'live'),
                             ('event_count', 6), ('recording_complete', 1), ('clock_id', 'sim:other')):
            values = saved_recording()
            values[0][field] = value
            cases.append(values)
        for index, field, value in ((1, 'event_sequence', 2), (2, 'record_elapsed_ns', 0),
                (2, 'dataset_ref', 99), (2, 'revision_after', 2), (2, 'attempt_id', 0),
                (3, 'run_timestamp', 101), (3, 'run_timestamp_available', False)):
            values = saved_recording()
            values[2][index][field] = value
            cases.append(values)
        values = saved_recording()
        values[1].clear()
        cases.append(values)
        values = saved_recording()
        values[2][3]['result']['provider_instance_id'] = 'restarted'
        cases.append(values)
        for values in cases:
            with self.subTest(values=values[0]), self.assertRaises(ValueError): validate_recording(*values)

    def test_bounded_rejected_attempt_is_preserved_without_becoming_a_dataset(self):
        values = saved_recording()
        event = copy.deepcopy(values[2][2])
        raw = copy.deepcopy(values[1][0]['dataset'])
        raw['grid']['observed_mask'] = [True]
        event.update(event_sequence=5, record_elapsed_ns=5000, attempt_id=2, dataset_ref=None,
            attempt=raw, outcome='rejected', reason='invalid_dataset', revision_before=1, revision_after=1)
        values[2].append(event)
        values[0]['event_count'] = 6
        validate_recording(*values)
        self.assertEqual(values[2][-1]['attempt'], raw)
        self.assertEqual(len(values[1]), 1)
        with self.assertRaises(ValueError): validate_dataset(raw)
        event['outcome'] = 'installed'
        with self.assertRaises(ValueError): validate_recording(*values)

    def test_absent_input_requires_incomplete_and_strict_reader_rejects_it(self):
        values = saved_recording()
        event = values[2][2]
        event.update(input_recorded=False, input_reason='input_too_large', dataset_ref=None, outcome='rejected',
                     reason='input_too_large', revision_after=0)
        del values[2][3:]
        values[0].update(event_count=3, recording_complete=False)
        validate_recording(*values, require_complete=False)
        with self.assertRaisesRegex(ValueError, 'incomplete'): validate_recording(*values)
        values[0]['recording_complete'] = True
        with self.assertRaises(ValueError): validate_recording(*values, require_complete=False)

    def test_file_missing_extra_line_truncation_and_actual_total_byte_limit_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            write_recording(tmp, saved_recording())
            path = directory / 'events.jsonl'
            original = path.read_bytes()
            path.write_bytes(original[:-1])
            with self.assertRaises(ValueError): load_recording(tmp)
            path.write_bytes(b' ' * 65537 + b'\n')
            with self.assertRaises(ValueError): load_recording(tmp)
            path.write_bytes(b' ' * (4 * 1024 * 1024))
            with self.assertRaises(ValueError): load_recording(tmp)
            path.write_bytes(original)
            (directory / 'extra.json').write_text('{}')
            with self.assertRaises(ValueError): load_recording(tmp)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): load_recording(tmp)

    def test_dataset_and_event_capacity_limits_include_exact_64_and_reject_65(self):
        values = saved_recording()
        base = values[1][0]['dataset']
        values[1][:] = [dict(dataset_ref=i, dataset=copy.deepcopy(base)) for i in range(64)]
        validate_recording(*values)
        values[1].append(dict(dataset_ref=64, dataset=base))
        with self.assertRaises(ValueError): validate_recording(*values)
        values = saved_recording()
        values[2][:] = [dict(event_sequence=i, record_elapsed_ns=i, operation='clock_observed',
                            run_timestamp_available=True, run_timestamp=100) for i in range(64)]
        values[0]['event_count'] = 64
        validate_recording(*values)
        values[2].append(dict(values[2][-1], event_sequence=64, record_elapsed_ns=64))
        values[0]['event_count'] = 65
        with self.assertRaises(ValueError): validate_recording(*values)

    def test_independent_per_record_limits_and_unavailable_time_canonical_slot(self):
        values = saved_recording()
        values[2][2].update(dataset_ref=None, attempt={'payload': ['x' * 16000] * 5},
                            outcome='rejected', reason='too_large', revision_after=0)
        with self.assertRaises(ValueError): validate_recording(*values)
        values = saved_recording()
        values[2][1]['run_timestamp_available'] = False
        with self.assertRaises(ValueError): validate_recording(*values)
        with self.assertRaises(ValueError): decode_json(b'{"a":1,"a":2}', 16384)

    def test_context_receipts_cannot_claim_another_revision_or_dataset(self):
        for key, value in (('terrain_revision', 2), ('context', dict(expected()['context'], dataset_version='unrecorded'))):
            values = saved_recording()
            values[2][3]['result'][key] = value
            with self.assertRaises(ValueError): validate_recording(*values)
        values = saved_recording()
        values[2][4]['status']['context']['dataset_version'] = 'unrecorded'
        with self.assertRaises(ValueError): validate_recording(*values)

    def test_status_sequence_can_skip_and_disable_retains_install_receipt(self):
        values = saved_recording()
        disabled = status()
        disabled.update(state='disabled', reason='operator_disabled', context=None, status_sequence=5)
        values[2].append(dict(event_sequence=5, record_elapsed_ns=5000, operation='disable',
            run_timestamp_available=True, run_timestamp=100, reason='operator_disabled', status=disabled))
        values[0]['event_count'] = 6
        validate_recording(*values)
        disabled['status_sequence'] = 1
        with self.assertRaises(ValueError): validate_recording(*values)


if __name__ == '__main__':
    unittest.main()
