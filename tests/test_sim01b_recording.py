"""B 对账反例：相同计数不能替代身份、姿态和落盘完整性。"""
import copy
from collections import Counter
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sim01b_validation import (SOURCE, SENSOR, CLOCK, validate_business, check_audit,
                              load_records, check_recomputed, validate_replay, check_raw, RAW)


def fixture():
    rows = []
    source = []
    sensor = []
    q = 2 ** -.5
    quality = {'confidence': None, 'uncertainty': {
        'status': 'unavailable', 'value': None, 'kind': 'pose_covariance',
        'unit': 'mixed', 'source': 'PX4 TODO'}}
    for i in range(12001):
        ns = 1_000_000_000 + i * 25_000_000
        rows.append({'topic': CLOCK, 'timestamp': ns, 'wire_hex': 'clock%d' % ns})
        if i % 4:
            continue
        h = dict(schema_version='0.1', run_id='run', clock_id='sim:run',
                 timestamp=ns, sample_id='sim.odometry:1:1:%d' % (ns//1000),
                 frame_id='world_ned', source_type='simulation', status='valid', reason='')
        state = dict(header=h, position=[1., 2., 3.], orientation_xyzw=[0., 0., 0., 1.],
                     linear_velocity=[4., 5., 6.], body_frame_id='body_frd',
                     velocity_frame_id='body_frd', state_source='estimated', quality=quality)
        adapted = copy.deepcopy(state)
        adapted['header'].update(frame_id='odom', source_type='derived', sample_id='sensors.state:'+h['sample_id'])
        adapted.update(position=[2., 1., -3.], linear_velocity=[4., -5., -6.],
                       orientation_xyzw=[0., 0., q, q], body_frame_id='base_link', velocity_frame_id='base_link')
        a = {'topic': SOURCE, 'state': state, 'timestamp': ns, 'wire_hex': 'source%d' % ns}
        b = {'topic': SENSOR, 'state': adapted, 'timestamp': ns, 'wire_hex': 'sensor%d' % ns}
        rows.extend([a, b])
        source.append(a)
        sensor.append(b)
    return rows, source, sensor, dict(t0_ns=1_000_000_000, t1_ns=301_000_000_000,
                                    first_sample_id=source[0]['state']['header']['sample_id'],
                                    last_sample_id=source[-1]['state']['header']['sample_id'])


class RecordingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = fixture()

    def validate(self, rows=None, window=None):
        base = self.baseline
        errors = []
        metrics = validate_business(rows if rows is not None else base[0],
                                    window if window is not None else base[3], errors)
        return errors, metrics

    def test_good_300_second_fixture(self):
        errors, metrics = self.validate()
        self.assertEqual(errors, [])
        self.assertEqual(metrics['source_samples'], 3001)
        self.assertEqual(metrics['clock_hz'], 40.)

    def test_missing_first_or_last_or_extra_sensor(self):
        for index in (0, -1):
            target = self.baseline[2][index]
            errors, _ = self.validate([r for r in self.baseline[0] if r is not target])
            self.assertTrue(any('identity' in e for e in errors), errors)
        rows = self.baseline[0] + [self.baseline[2][-1]]
        self.assertTrue(self.validate(rows)[0])

    def test_same_count_wrong_id(self):
        rows = copy.deepcopy(self.baseline[0])
        next(r for r in rows if r['topic'] == SENSOR)['state']['header']['sample_id'] = 'sensors.state:wrong'
        self.assertTrue(any('identity' in e for e in self.validate(rows)[0]))

    def test_missing_first_or_last_source_cannot_reselect_window(self):
        for target in (self.baseline[1][0], self.baseline[1][-1]):
            errors, _ = self.validate([r for r in self.baseline[0] if r is not target])
            self.assertTrue(any('identity' in e or 'window' in e or 'first_source' in e
                                for e in errors), errors)

    def test_duplicate_extra_identity_is_failure(self):
        rows = self.baseline[0] + [self.baseline[1][-1], self.baseline[2][-1]]
        self.assertTrue(any('duplicate' in e for e in self.validate(rows)[0]))

    def test_unit_norm_wrong_rotation(self):
        rows = copy.deepcopy(self.baseline[0])
        next(r for r in rows if r['topic'] == SENSOR)['state']['orientation_xyzw'] = [0., 0., 0., 1.]
        self.assertTrue(any('orientation' in e for e in self.validate(rows)[0]))

    def test_quality_provenance_changed(self):
        rows = copy.deepcopy(self.baseline[0])
        next(r for r in rows if r['topic'] == SENSOR)['state']['quality']['uncertainty']['source'] = 'invented'
        self.assertTrue(any('quality' in e for e in self.validate(rows)[0]))

    def test_quality_kind_and_unit_are_part_of_contract(self):
        for key in ('kind', 'unit'):
            rows = copy.deepcopy(self.baseline[0])
            next(r for r in rows if r['topic'] == SENSOR)['state']['quality']['uncertainty'][key] = 'invented'
            self.assertTrue(any('quality' in e for e in self.validate(rows)[0]))

    def test_opposite_quaternion_sign_is_equivalent(self):
        rows = copy.deepcopy(self.baseline[0])
        state = next(r for r in rows if r['topic'] == SENSOR)['state']
        state['orientation_xyzw'] = [-v for v in state['orientation_xyzw']]
        self.assertEqual(self.validate(rows)[0], [])

    def test_final_clock_not_covering(self):
        rows = [r for r in self.baseline[0] if not (r['topic'] == CLOCK and r['timestamp'] == 301_000_000_000)]
        self.assertTrue(any('clock_coverage' in e for e in self.validate(rows)[0]))

    def test_t0_cannot_skip_first_source(self):
        window = dict(self.baseline[3], t0_ns=1_100_000_000)
        self.assertTrue(any('first_source' in e for e in self.validate(window=window)[0]))

    def test_audit_detects_missing_first_source(self):
        errors = []
        check_audit(self.baseline[1], self.baseline[1][1:], [SOURCE], errors)
        self.assertTrue(errors)

    def test_missing_close_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = []
            self.assertEqual(load_records(Path(directory), 'live.bag', errors), [])
            self.assertTrue(any('writer-closed' in e for e in errors), errors)

    def test_b2_eof_missing_output_and_exact_metadata(self):
        states = [row['state'] for row in self.baseline[2][:2]]
        errors = []
        check_recomputed(states, states[:1], errors)
        self.assertTrue(any('EOF' in e for e in errors))
        wrong = copy.deepcopy(states)
        wrong[0]['quality']['uncertainty']['source'] = 'invented'
        errors = []
        check_recomputed(states, wrong, errors)
        self.assertTrue(any('quality' in e for e in errors))

    def test_b1_eof_missing_clock_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            live = Path(directory) / 'live'
            replay = Path(directory) / 'replay'
            live.mkdir()
            replay.mkdir()
            (live / 'window.json').write_text(json.dumps(self.baseline[3]))
            actual = [row for row in self.baseline[0] if row is not self.baseline[0][-3]]
            with mock.patch('sim01b_validation.load_records', side_effect=[self.baseline[0], actual]):
                result = validate_replay(live, replay, 'B1')
            self.assertFalse(result['passed'])
            self.assertTrue(any('EOF' in e for e in result['errors']), result)


class BagIntegrityTest(unittest.TestCase):
    """实际ROS Clock序列化和bag重读；无需启动ROS Master。"""
    def create_bag(self, run):
        import genpy
        import rosbag
        from rosgraph_msgs.msg import Clock
        rows = []
        with rosbag.Bag(str(run / 'live.bag'), 'w') as bag:
            for i in range(1, 4):
                msg = Clock(genpy.Time(i, 123))
                wire = io.BytesIO()
                msg.serialize(wire)
                row = dict(record_seq=i, topic=CLOCK, receipt_monotonic_ns=10000+i,
                           bag_time_ns=i, timestamp=msg.clock.to_nsec(), wire_hex=wire.getvalue().hex())
                rows.append(row)
                bag.write(CLOCK, msg, t=genpy.Time(0, i))
        self.write_sidecar(run, rows)
        return rows

    def write_sidecar(self, run, rows):
        (run / 'records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        counts = dict(Counter(row['topic'] for row in rows))
        (run / 'writer-closed.json').write_text(json.dumps(dict(
            passed=True, errors=[], records=len(rows), topic_counts=counts,
            received_counts=counts, queue_empty=True, record_start_monotonic_ns=10000)))

    def test_actual_bag_bytes_and_integer_index(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            rows = self.create_bag(run)
            errors = []
            self.assertEqual(load_records(run, 'live.bag', errors), rows)
            self.assertEqual(errors, [])

    def test_missing_disk_record_is_failure_even_with_matching_closed_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            rows = self.create_bag(run)
            self.write_sidecar(run, rows[:2])
            errors = []
            load_records(run, 'live.bag', errors)
            self.assertTrue(any('bag: more records' in e for e in errors), errors)

    def test_sidecar_wire_and_clock_cannot_override_bag(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            rows = self.create_bag(run)
            rows[0]['wire_hex'] = rows[1]['wire_hex']
            rows[0]['timestamp'] += 1
            self.write_sidecar(run, rows)
            errors = []
            actual = load_records(run, 'live.bag', errors)
            self.assertEqual(actual[0]['timestamp'], 1_000_000_123)
            self.assertTrue(any('wire differs' in e for e in errors), errors)
            self.assertTrue(any('clock differs' in e for e in errors), errors)

    def test_incomplete_writer_marker_is_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            self.create_bag(run)
            marker = json.loads((run / 'writer-closed.json').read_text())
            marker['queue_empty'] = False
            (run / 'writer-closed.json').write_text(json.dumps(marker))
            errors = []
            load_records(run, 'live.bag', errors)
            self.assertTrue(any('writer-closed: incomplete' in e for e in errors), errors)


class RawSafetyTest(unittest.TestCase):
    def raw_rows(self, foreign_armed=False, imu_ns=20_000_000_000):
        from pymavlink.dialects.v20 import common
        rows = []
        heartbeat = common.MAVLink_heartbeat_message(1, 3, 0, 0, 4, 3)
        imu = common.MAVLink_highres_imu_message(imu_ns//1000, *([0.]*13), 0)
        for msg in (heartbeat, imu):
            wire = msg.pack(common.MAVLink(None, srcSystem=1, srcComponent=1))
            rows.append(dict(topic=RAW, framing=1, msgid=msg.get_msgId(), sysid=1,
                             compid=1, raw_wire_hex=wire.hex()))
        rows.append(dict(topic=RAW, framing=1, msgid=331, sysid=1, compid=1, raw_wire_hex=''))
        if foreign_armed:
            msg = common.MAVLink_heartbeat_message(1, 3, 128, 0, 4, 3)
            wire = msg.pack(common.MAVLink(None, srcSystem=2, srcComponent=1))
            rows.append(dict(topic=RAW, framing=1, msgid=0, sysid=2, compid=1, raw_wire_hex=wire.hex()))
        return rows

    def test_foreign_armed_heartbeat_cannot_escape_safety_check(self):
        errors = []
        check_raw(self.raw_rows(), errors)
        self.assertEqual(errors, [])
        check_raw(self.raw_rows(foreign_armed=True), errors)
        self.assertTrue(any('armed heartbeat' in e for e in errors), errors)

    def test_absolute_raw_imu_ceiling_includes_equality(self):
        errors = []
        check_raw(self.raw_rows(imu_ns=600_000_000_000), errors)
        self.assertTrue(any('absolute IMU' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()
