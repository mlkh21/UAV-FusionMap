"""Device-specific time contract tests; no hardware or ROS graph required."""
import sys
import copy
import json
import unittest
from pathlib import Path
import tempfile
import subprocess


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'sensors'))

from ufm_sensors.device_time_adapter import (
    adapt_ars548_detection_list,
    adapt_mid360_custom_msg,
)
from ufm_sensors.device_time_record import (
    make_ars548_record,
    make_mid360_record,
    validate_device_time_record,
    validate_device_time_stream,
)
from iface01_device_record_replay import audit_jsonl


def identity(model):
    return dict(run_id='device-run', clock_id='device:' + model,
                sample_id='raw:' + model + ':1', frame_id=model + '_frame')


def mid360_frame():
    return dict(timebase=10_000_000_000, point_num=2, points=[
        dict(offset_time=0, x=1.0, y=2.0, z=3.0, reflectivity=10, tag=0, line=0),
        dict(offset_time=250_000, x=1.1, y=2.1, z=3.1, reflectivity=11, tag=0, line=1),
    ])


def ars548_message():
    return dict(timestamp_seconds=12, timestamp_nanoseconds=345,
                timestamp_syncstatus=2, list_numofdetections=2,
                list_detections=[
                    dict(f_range=10.0, f_rangerate=-2.0),
                    dict(f_range=20.0, f_rangerate=1.0),
                ])


def ros_message(**fields):
    message_type = type('GeneratedMessage', (), {'__slots__': tuple(fields)})
    message = message_type()
    for name, value in fields.items():
        setattr(message, name, value)
    return message


class DeviceTimeAdapterTest(unittest.TestCase):
    def test_mid360_expands_per_point_time(self):
        result = adapt_mid360_custom_msg(mid360_frame(), identity('mid360'),
                                         packet_time_type=1)
        self.assertEqual(result['time_source'], 'ptp_or_gptp')
        self.assertTrue(result['time_sync_source_present'])
        self.assertEqual([p['point_time_ns'] for p in result['points']],
                         [10_000_000_000, 10_000_250_000])
        self.assertEqual(result['scan_start_ns'], 10_000_000_000)
        self.assertEqual(result['scan_end_ns'], 10_000_250_000)

    def test_mid360_unsynchronized_clock_is_preserved_not_promoted(self):
        result = adapt_mid360_custom_msg(mid360_frame(), identity('mid360'),
                                         packet_time_type=0)
        self.assertEqual(result['time_source'], 'device_boot')
        self.assertFalse(result['time_sync_source_present'])
        self.assertTrue(result['point_time_available'])

    def test_mid360_custom_msg_without_raw_time_type_keeps_sync_unproven(self):
        result = adapt_mid360_custom_msg(mid360_frame(), identity('mid360'))
        self.assertEqual(result['time_type_provenance'],
                         'unavailable_in_custom_msg')
        self.assertEqual(result['time_source'], 'unspecified')
        self.assertIsNone(result['time_sync_source_present'])

    def test_adapts_ros_generated_slot_messages_without_ros_import(self):
        points = [ros_message(offset_time=0, x=1.0, y=2.0, z=3.0,
                              reflectivity=10, tag=0, line=0)]
        frame = ros_message(timebase=1000, point_num=1, points=points)
        mid360 = adapt_mid360_custom_msg(frame, identity('mid360'))
        self.assertEqual(mid360['points'][0]['point_time_ns'], 1000)

        detections = [ros_message(f_range=10.0, f_rangerate=-2.0)]
        message = ros_message(timestamp_seconds=12,
                              timestamp_nanoseconds=345,
                              timestamp_syncstatus=2,
                              list_numofdetections=1,
                              list_detections=detections)
        ars548 = adapt_ars548_detection_list(message, identity('ars548'))
        self.assertEqual(ars548['observation_timestamp_ns'], 12_000_000_345)

    def test_mid360_rejects_count_order_and_invalid_time_type(self):
        frame = mid360_frame()
        frame['point_num'] = 1
        with self.assertRaises(ValueError):
            adapt_mid360_custom_msg(frame, identity('mid360'),
                                    packet_time_type=1)
        frame = mid360_frame()
        frame['points'][1]['offset_time'] = 0
        frame['points'][0]['offset_time'] = 1
        with self.assertRaises(ValueError):
            adapt_mid360_custom_msg(frame, identity('mid360'),
                                    packet_time_type=1)
        with self.assertRaises(ValueError):
            adapt_mid360_custom_msg(mid360_frame(), identity('mid360'),
                                    packet_time_type=3)

    def test_ars548_combines_list_timestamp_and_keeps_point_time_unknown(self):
        result = adapt_ars548_detection_list(ars548_message(), identity('ars548'))
        self.assertEqual(result['observation_timestamp_ns'], 12_000_000_345)
        self.assertEqual(result['timestamp_syncstatus'], 2)
        self.assertFalse(result['point_time_available'])
        self.assertIsNone(result['time_sync_source_present'])
        self.assertEqual([p['point_time_ns'] for p in result['points']], [None, None])
        self.assertIsNone(result['scan_start_ns'])
        self.assertIsNone(result['scan_end_ns'])

    def test_ars548_accepts_fixed_array_with_declared_count(self):
        message = ars548_message()
        message['list_detections'].append(dict(f_range=99.0))
        result = adapt_ars548_detection_list(message, identity('ars548'))
        self.assertEqual(len(result['points']), 2)

    def test_ars548_rejects_invalid_timestamp_count_and_missing_clock(self):
        message = ars548_message()
        message['timestamp_nanoseconds'] = 1_000_000_000
        with self.assertRaises(ValueError):
            adapt_ars548_detection_list(message, identity('ars548'))
        message = ars548_message()
        message['list_numofdetections'] = 3
        with self.assertRaises(ValueError):
            adapt_ars548_detection_list(message, identity('ars548'))
        broken_identity = identity('ars548')
        del broken_identity['clock_id']
        with self.assertRaises(ValueError):
            adapt_ars548_detection_list(ars548_message(), broken_identity)

    def test_record_keeps_device_and_receive_timestamps_separate(self):
        record = make_ars548_record(ars548_message(), identity('ars548'),
                                    receive_timestamp_ns=90_000,
                                    receive_clock_id='host:ros')
        self.assertEqual(record['device_timestamp_ns'], 12_000_000_345)
        self.assertEqual(record['receive_timestamp_ns'], 90_000)
        self.assertEqual(record['time_mapping_status'], 'unmapped')
        self.assertIsNone(record['time_mapping_offset_ns'])
        self.assertEqual(json.loads(json.dumps(record))['sample_id'],
                         record['sample_id'])
        self.assertTrue(validate_device_time_record(record))

    def test_record_rejects_missing_or_invented_clock_mapping(self):
        with self.assertRaises(ValueError):
            make_ars548_record(ars548_message(), identity('ars548'),
                               receive_timestamp_ns=90_000,
                               receive_clock_id='')
        record = make_ars548_record(ars548_message(), identity('ars548'),
                                    receive_timestamp_ns=90_000,
                                    receive_clock_id='host:ros')
        broken = copy.deepcopy(record)
        broken['device_timestamp_ns'] += 1
        with self.assertRaises(ValueError):
            validate_device_time_record(broken)
        broken = copy.deepcopy(record)
        broken['time_mapping_offset_ns'] = 10
        with self.assertRaises(ValueError):
            validate_device_time_record(broken)

    def test_mid360_raw_time_type_requires_explicit_transport_provenance(self):
        with self.assertRaises(ValueError):
            make_mid360_record(mid360_frame(), identity('mid360'),
                               receive_timestamp_ns=90_000,
                               receive_clock_id='host:ros', packet_time_type=1)
        record = make_mid360_record(
            mid360_frame(), identity('mid360'), receive_timestamp_ns=90_000,
            receive_clock_id='host:ros', packet_time_type=1,
            transport='ros_custom_msg_plus_raw_packet_metadata')
        self.assertTrue(validate_device_time_record(record))

    def test_record_rejects_spoofed_sync_source_and_time_semantics(self):
        ars548 = make_ars548_record(ars548_message(), identity('ars548'),
                                    receive_timestamp_ns=90_000,
                                    receive_clock_id='host:ros')
        mid360 = make_mid360_record(mid360_frame(), identity('mid360'),
                                    receive_timestamp_ns=90_000,
                                    receive_clock_id='host:ros')
        for record, field, value in (
                (ars548, 'time_source', 'ptp_or_gptp'),
                (ars548, 'time_sync_source_present', True),
                (ars548, 'point_time_semantics', 'timebase_plus_offset_time_ns'),
                (mid360, 'time_source', 'ptp_or_gptp'),
                (mid360, 'point_time_semantics', 'detection_list_timestamp_only')):
            broken = copy.deepcopy(record)
            broken['payload'][field] = value
            with self.subTest(kind=record['record_kind'], field=field), self.assertRaises(ValueError):
                validate_device_time_record(broken)

    def test_mid360_uint64_device_time_is_preserved_in_record(self):
        frame = mid360_frame()
        frame['timebase'] = 2**64 - 1
        frame['points'] = [dict(frame['points'][0], offset_time=0)]
        frame['point_num'] = 1
        record = make_mid360_record(frame, identity('mid360'),
                                    receive_timestamp_ns=90_000,
                                    receive_clock_id='host:ros')
        self.assertEqual(record['device_timestamp_ns'], 2**64 - 1)
        self.assertTrue(validate_device_time_record(record))

    def test_device_stream_rejects_duplicate_and_mixed_identity(self):
        first = make_ars548_record(ars548_message(), identity('ars548'),
                                   receive_timestamp_ns=90_000,
                                   receive_clock_id='host:ros')
        duplicate = copy.deepcopy(first)
        with self.assertRaises(ValueError):
            validate_device_time_stream([first, duplicate])
        other = make_ars548_record(ars548_message(), identity('ars548-other'),
                                   receive_timestamp_ns=91_000,
                                   receive_clock_id='host:ros')
        with self.assertRaises(ValueError):
            validate_device_time_stream([first, other])

    def test_device_stream_keeps_one_frame_but_allows_delivery_reordering(self):
        first = make_mid360_record(mid360_frame(), identity('mid360'),
                                   receive_timestamp_ns=90_000,
                                   receive_clock_id='host:ros')
        second_identity = identity('mid360')
        second_identity['sample_id'] = 'raw:mid360:2'
        second = make_mid360_record(mid360_frame(), second_identity,
                                    receive_timestamp_ns=89_000,
                                    receive_clock_id='host:ros')
        self.assertTrue(validate_device_time_stream([first, second]))
        changed_identity = dict(second_identity, frame_id='other_frame')
        changed = make_mid360_record(mid360_frame(), changed_identity,
                                     receive_timestamp_ns=89_000,
                                     receive_clock_id='host:ros')
        with self.assertRaises(ValueError):
            validate_device_time_stream([first, changed])

    def test_jsonl_replay_preserves_unmapped_device_and_receive_clocks(self):
        first = make_mid360_record(mid360_frame(), identity('mid360'), 90_000,
                                   'host:ros')
        second_id = dict(identity('mid360'), sample_id='raw:mid360:2')
        second = make_mid360_record(mid360_frame(), second_id, 89_000,
                                    'host:ros')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'device.jsonl'
            path.write_text(''.join(json.dumps(item) + '\n' for item in (first, second)))
            result = audit_jsonl(path)
        self.assertEqual(result['record_count'], 2)
        self.assertEqual(result['record_kind'], 'mid360_custom_msg')
        self.assertEqual(result['device_timestamp_bounds_ns'], [10_000_000_000, 10_000_000_000])
        self.assertEqual(result['receive_timestamp_bounds_ns'], [89_000, 90_000])
        self.assertEqual(result['time_mapping_status'], 'unmapped')
        self.assertFalse(result['hardware_validated'])

    def test_jsonl_replay_rejects_corrupt_empty_duplicate_and_mixed(self):
        first = make_ars548_record(ars548_message(), identity('ars548'), 90_000,
                                   'host:ros')
        changed = make_ars548_record(ars548_message(),
                                     dict(identity('ars548'), frame_id='other'),
                                     91_000, 'host:ros')
        cases = (('', 'empty'), ('\n', 'blank'), ('{bad}\n', 'malformed'),
                 (json.dumps(first) + '\n' + json.dumps(first) + '\n', 'duplicate'),
                 (json.dumps(first) + '\n' + json.dumps(changed) + '\n', 'mixed'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'device.jsonl'
            for text, name in cases:
                path.write_text(text)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    audit_jsonl(path)

    def test_jsonl_replay_command_is_read_only_and_rejects_forged_clock(self):
        first = make_ars548_record(ars548_message(), identity('ars548'), 90_000,
                                   'host:ros')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'device.jsonl'
            script = ROOT / 'tests/iface01_device_record_replay.py'
            original = json.dumps(first) + '\n'
            path.write_text(original)
            result = subprocess.run([sys.executable, '-B', str(script), '--input', str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)['passed'])
            self.assertEqual(path.read_text(), original)
            forged = copy.deepcopy(first)
            forged['time_mapping_status'] = 'verified'
            path.write_text(json.dumps(forged) + '\n')
            result = subprocess.run([sys.executable, '-B', str(script), '--input', str(path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stderr)['passed'])
            self.assertEqual(path.read_text(), json.dumps(forged) + '\n')


if __name__ == '__main__':
    unittest.main()
