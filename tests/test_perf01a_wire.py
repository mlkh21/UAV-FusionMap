"""探针必须保持线格式；元数据模式仍须检出消费丢失、重复和拓扑变化。"""
import copy
import io
from pathlib import Path
import tempfile
import unittest

from uav_fusionmap_msgs.msg import InfraredFrame, SensorBundle
from ufm_ros_contract.perf01a_wire import WireAudit, message_identity
from ufm_ros_contract.perf01a_codec import to_ros_bundle
from ufm_sensors.perf01a_fixture import build_sensor_bundle
from ufm_sensors.perf01a_scenarios import scenario_inputs
from ufm_sensors.state_adapter import adapt_state
from ufm_simulation.perf01a_fixture import make_fixture_state
from perf01a_wire_report import wire_report
from perf01a_resources import ResourceSampler
from perf01a_compare import candidate_decision
from ufm_ros_contract.perf01a_numpy_receive import numpy_list_receive_type


PROFILE = dict(ir_resolution=[2, 2], fault='none')


def bundle():
    state = adapt_state(make_fixture_state('r', 0, 0), {
        'odom_origin_policy': 'px4_estimator_local_origin', 'body_origin_policy': 'source_body_virtual_flu'})
    radar, infrared, states = scenario_inputs('r', 0, state, PROFILE)
    value, reason = build_sensor_bundle(radar, infrared, states)
    assert not reason
    return to_ros_bundle(value)


def audit_fixture():
    msg = bundle()
    base = message_identity(msg)
    sender = dict(base, operation='serialize:SensorBundle', start_ns=12, end_ns=16,
                  thread_cpu_ns=3, wire_bytes=100)
    receiver = dict(base, operation='deserialize:SensorBundle', start_ns=22, end_ns=25,
                    thread_cpu_ns=2, wire_bytes=100)
    audits = dict(sensor=dict(rows=[sender, dict(base, operation='publish:SensorBundle', connections=1),
        dict(message_identity(msg.infrared), operation='publish:InfraredFrame', connections=0)]),
        perception=dict(rows=[receiver, dict(base, operation='callback:SensorBundle', callback_ns=27)]),
        observer=dict(rows=[]))
    events = [dict(parent_sample_id=base['sample_id'], stage='timing.bundle_publish', monotonic_ns=19,
                   metric_value_ns=9),
              dict(parent_sample_id=base['sample_id'], stage='timing.bundle_callback', monotonic_ns=27)]
    records = dict(map=[dict(sample_id='map:1', run_id='r', timestamp=0, status=0,
        revision=1, cell_count=1, cells=[dict(observed=True, timestamp=0)])])
    return audits, events, records


class WireTest(unittest.TestCase):
    def test_candidate_needs_repeatable_gain_and_functional_closure(self):
        rows = [dict(mode='full', pair=i, backend=backend, p99_ms=value,
                     exit=0, summary={'passed': True})
                for i in range(3) for backend, value in [('standard', 30.), ('numpy', 24.)]]
        self.assertTrue(candidate_decision(rows)['accepted'])
        rows[-1]['p99_ms'] = 31.
        self.assertFalse(candidate_decision(rows)['accepted'])
        rows[-1]['p99_ms'] = 24.
        rows[-1]['summary']['passed'] = False
        self.assertFalse(candidate_decision(rows)['accepted'])

    def test_numpy_candidate_preserves_wire_bytes_and_python_contract(self):
        from ufm_ros_contract.perf01a_codec import from_ros_bundle
        msg = bundle()
        msg.infrared.image = [-1.25, .1, 2., 0.]
        wire = io.BytesIO()
        msg.serialize(wire)
        standard = SensorBundle().deserialize(wire.getvalue())
        candidate_type = numpy_list_receive_type(SensorBundle)
        candidate = candidate_type().deserialize(wire.getvalue())
        encoded = io.BytesIO()
        candidate.serialize(encoded)
        self.assertEqual(encoded.getvalue(), wire.getvalue())
        self.assertEqual(from_ros_bundle(candidate), from_ros_bundle(standard))
        self.assertIsInstance(candidate.infrared.image, list)
        self.assertIs(type(candidate.infrared.image[0]), float)
        self.assertEqual(candidate._md5sum, standard._md5sum)

    def test_numpy_candidate_full_image_and_empty_quality_arrays(self):
        msg = bundle()
        msg.infrared.width, msg.infrared.height = 640, 512
        msg.infrared.image = [.5] * (640 * 512)
        wire = io.BytesIO()
        msg.serialize(wire)
        candidate = numpy_list_receive_type(SensorBundle)().deserialize(wire.getvalue())
        self.assertEqual(candidate.infrared.image, msg.infrared.image)
        self.assertEqual(candidate.infrared.quality.uncertainty.value, [])
        encoded = io.BytesIO()
        candidate.serialize(encoded)
        self.assertEqual(encoded.getvalue(), wire.getvalue())

    def test_probe_preserves_actual_serialization_bytes_and_identity(self):
        msg = bundle()
        before = io.BytesIO()
        msg.serialize(before)
        with tempfile.TemporaryDirectory() as directory:
            audit = WireAudit(Path(directory) / 'wire.json')
            audit.install(SensorBundle, 'serialize')
            audit.install(SensorBundle, 'deserialize')
            try:
                after = io.BytesIO()
                msg.serialize(after)
                received = SensorBundle().deserialize(after.getvalue())
                self.assertEqual(before.getvalue(), after.getvalue())
                self.assertEqual(message_identity(msg), message_identity(received))
                self.assertEqual([r['operation'] for r in audit.rows],
                                 ['serialize:SensorBundle', 'deserialize:SensorBundle'])
                self.assertEqual(audit.rows[0]['wire_bytes'], len(before.getvalue()))
                self.assertGreater(audit.rows[1]['end_ns'], audit.rows[1]['start_ns'])
                audit.save()
                with self.assertRaises(FileExistsError):
                    audit.save()
            finally:
                audit.restore()

    def test_metadata_audit_closes_and_wire_parts_sum(self):
        audit, events, records = audit_fixture()
        result = wire_report(audit, events, records, 1, PROFILE, 'r', 50_000_000, 'metadata')
        self.assertEqual(result['errors'], [])
        self.assertEqual(sum(result['samples'][0]['parts'].values()), 17)
        self.assertEqual(result['samples'][0]['parts']['queue_transport_schedule_ns'], 6)
        self.assertEqual(result['operations']['observer.deserialize:SensorBundle']['count'], 0)

    def test_metadata_audit_detects_missing_duplicate_wrong_size_and_peers(self):
        for mutation in ('missing', 'duplicate', 'bytes', 'peers', 'clock', 'negative'):
            audit, events, records = audit_fixture()
            rows = audit['perception']['rows']
            if mutation == 'missing':
                rows.pop()
            elif mutation == 'duplicate':
                rows.append(copy.deepcopy(rows[0]))
            elif mutation == 'bytes':
                rows[0]['wire_bytes'] += 4
            elif mutation == 'peers':
                audit['sensor']['rows'][1]['connections'] = 2
            elif mutation == 'clock':
                rows[0]['clock_id'] = 'sim:wrong'
            else:
                rows[0]['start_ns'] = 1
            with self.subTest(mutation=mutation):
                self.assertTrue(wire_report(audit, events, records, 1, PROFILE, 'r',
                                           50_000_000, 'metadata')['errors'])

    def test_resource_cpu_is_one_core_percent_and_missing_roles_are_visible(self):
        sampler = ResourceSampler()
        sampler.rows = [dict(monotonic_ns=stamp, sampling_wall_ns=10, sampling_thread_cpu_ns=5,
            processes=[dict(pid=123, created=1, role='observer', cpu_s=cpu, rss_bytes=4096)])
            for stamp, cpu in [(1_000_000_000, 2.), (2_000_000_000, 2.5)]]
        result = sampler.report()
        self.assertEqual(result['processes'][0]['cpu_percent_one_core']['p50'], 50.)
        self.assertIn('perf01a_sensor', result['missing_roles'])
