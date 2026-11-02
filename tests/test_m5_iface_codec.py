"""Public M5 contracts against independent bytes and actual generated ROS types."""
import copy
from fractions import Fraction as F
import io
import math
from pathlib import Path
import struct
import subprocess
import sys
import unittest

from m5_iface_fixture import (LAYOUT, ROOT, expected, independent_bytes, quality,
                             request, result, status, unavailable, wire_object)
from ufm_terrain_contract.codec import (deserialize, from_ros, from_ros_response,
                                      serialize, to_ros, to_ros_response)
from ufm_terrain_contract.contract import (validate_context, validate_request, validate_result,
                                         validate_status)


class TerrainPublicCodecTest(unittest.TestCase):
    def roundtrip(self, name, row):
        message = to_ros(name, row)
        stream = io.BytesIO()
        message.serialize(stream)
        raw = stream.getvalue()
        self.assertEqual(raw, independent_bytes(name, wire_object(name, row)))
        self.assertEqual(deserialize(name, raw), row)
        self.assertEqual(from_ros(name, type(message)().deserialize(raw)), row)
        return raw

    def test_generated_field_layout_is_the_independent_approved_layout(self):
        from uav_fusionmap_terrain_msgs import msg, srv
        for name, layout in LAYOUT.items():
            cls = getattr(srv if name.startswith('TerrainQuery') and name.endswith(('Request', 'Response')) else msg, name)
            pairs = [p.split(':') for p in layout.split()]
            self.assertEqual(list(cls.__slots__), [p[0] for p in pairs])
            self.assertEqual(cls._slot_types, ['uav_fusionmap_terrain_msgs/' + t if t in LAYOUT else t for _, t in pairs])
        self.assertEqual(srv.TerrainQuery._request_class, srv.TerrainQueryRequest)
        self.assertEqual(srv.TerrainQuery._response_class, srv.TerrainQueryResponse)

    def test_all_four_messages_and_request_response_use_actual_genpy_bytes(self):
        self.roundtrip('TerrainHeightQuality', quality([9.75, 10.25]))
        self.roundtrip('TerrainContext', expected()['context'])
        self.roundtrip('TerrainQueryRequest', request())
        self.roundtrip('TerrainStatus', status())
        for i in range(4):
            self.roundtrip('TerrainQueryResult', result(i))
        row, stream = result(), io.BytesIO()
        message = to_ros_response(row)
        message.serialize(stream)
        self.assertEqual(stream.getvalue(), independent_bytes('TerrainQueryResponse', {'result': wire_object('TerrainQueryResult', row)}))
        decoded = type(message)().deserialize(stream.getvalue())
        self.assertEqual(from_ros_response(decoded, request=request(), provider_instance_id='terrain-instance-a'), row)

    def test_saved_quality_bounds_are_outward_exact_rational_intervals(self):
        for row in expected()['samples']:
            if row['height'] is None:
                continue
            for i, bound in enumerate(row['map_interval']):
                exact = F(str(row['sample_interval'][i])) + F(str([2.9, 3.1][i]))
                self.assertTrue(F.from_float(bound) <= exact if i == 0 else F.from_float(bound) >= exact)
        self.assertEqual(self.roundtrip('TerrainQueryResult', result()), serialize('TerrainQueryResult', result()))

    def test_zero_negative_heights_and_missing_quality_remain_present(self):
        for height in (0., -23.5):
            row = result()
            row.update(height=height, height_quality=quality(), sample_quality=quality())
            raw = self.roundtrip('TerrainQueryResult', row)
            self.assertIsNotNone(deserialize('TerrainQueryResult', raw)['height'])
            self.assertTrue(to_ros('TerrainQueryResult', row).height_available)
        row = result()
        row['context']['registration_quality'] = quality(kind='height_offset_interval')
        row['height_quality'] = quality()
        self.roundtrip('TerrainQueryResult', row)

    def test_no_data_outside_stale_and_unavailable_keep_distinct_payloads(self):
        self.roundtrip('TerrainQueryResult', result(2))
        outside = result(2)
        outside.update(point_xy=[115., 179.], reason='outside_coverage', source_index=None, source_xy=None)
        self.roundtrip('TerrainQueryResult', outside)
        for row in (result(), result(2), outside):
            row.update(status='stale', reason='terrain_expired', evaluation_timestamp=200)
            self.roundtrip('TerrainQueryResult', row)
        self.roundtrip('TerrainQueryResult', unavailable())
        for name in ('disabled', 'waiting_clock', 'empty', 'unavailable', 'locked'):
            row = status()
            row.update(state=name, context=None, evaluation_timestamp=None if name == 'waiting_clock' else 100)
            self.roundtrip('TerrainStatus', row)

    def test_every_quality_enum_and_status_outcome_survives_wire(self):
        self.roundtrip('TerrainHeightQuality', quality())
        self.roundtrip('TerrainHeightQuality', quality([2.9, 3.1], kind='height_offset_interval'))
        row = status()
        row.update(state='expired', evaluation_timestamp=200)
        self.roundtrip('TerrainStatus', row)
        for outcome in ('none', 'installed', 'idempotent', 'rejected'):
            row = status()
            row.update(last_install_outcome=outcome, last_attempt_id=0 if outcome == 'none' else 1,
                       last_install_reason='candidate_rejected' if outcome == 'rejected' else '')
            self.roundtrip('TerrainStatus', row)

    def test_integer_time_and_uint64_do_not_round_through_float(self):
        probe = expected()['integer_probe']
        req = request()
        req.update(query_timestamp=probe, expected_terrain_revision=2**64 - 1)
        self.roundtrip('TerrainQueryRequest', req)
        row = unavailable()
        row.update(query_timestamp=2**63 - 1, evaluation_timestamp=probe, terrain_revision=2**64 - 1)
        self.roundtrip('TerrainQueryResult', row)
        row = status()
        row.update(state='locked', context=None, evaluation_timestamp=probe, status_sequence=2**64 - 1,
                   last_attempt_id=2**64 - 1, terrain_revision=2**64 - 1)
        self.roundtrip('TerrainStatus', row)
        for stamp in (True, 1., -1, 2**63):
            req = request()
            req['query_timestamp'] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                to_ros('TerrainQueryRequest', req)

    def test_bad_enums_versions_identity_and_quality_roles_are_rejected(self):
        for key, value in (('status', 'free'), ('protocol_version', 2), ('protocol_version', True),
                ('provider_instance_id', ''), ('terrain_revision', 0), ('frame_id', 'odom'),
                ('run_id', 'other'), ('context', None), ('height', math.inf), ('point_xy', [math.nan, 179.])):
            row = result()
            row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                to_ros('TerrainQueryResult', row)
        for field in ('height_quality', 'sample_quality'):
            row = result()
            row[field]['kind'] = 'height_offset_interval'
            with self.assertRaises(ValueError): to_ros('TerrainQueryResult', row)
        row = result()
        row['context']['registration_quality']['kind'] = 'height_interval'
        with self.assertRaises(ValueError): to_ros('TerrainQueryResult', row)
        for field in ('status', 'height_quality'):
            message = to_ros('TerrainQueryResult', result())
            if field == 'status': message.status = 255
            else: message.height_quality.status = 2
            with self.assertRaises(ValueError): from_ros('TerrainQueryResult', message)
        message = to_ros('TerrainStatus', status())
        for field in ('state', 'last_install_outcome'):
            bad = copy.deepcopy(message)
            setattr(bad, field, 99)
            with self.assertRaises(ValueError): from_ros('TerrainStatus', bad)

    def test_binding_checks_echo_pin_and_provider_instance(self):
        row, req = result(), request()
        validate_result(row, req, 'terrain-instance-a')
        for key, value in (('point_xy', [113., 179.]), ('query_timestamp', 99),
                           ('expected_provider_instance_id', 'restarted'), ('expected_terrain_revision', 2)):
            bad = dict(req, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError): validate_result(row, bad)
        with self.assertRaises(ValueError): validate_result(row, req, 'restarted')
        error = unavailable()
        validate_result(error, dict(req, expected_provider_instance_id='restarted'))
        req.update(pin_version=False, expected_provider_instance_id='', expected_terrain_revision=0)
        self.roundtrip('TerrainQueryRequest', req)
        req['expected_provider_instance_id'] = 'leftover'
        with self.assertRaises(ValueError): validate_request(req)

    def test_temporal_context_and_sample_consistency_are_strict(self):
        for changes in (dict(evaluation_timestamp=99), dict(evaluation_timestamp=300),
                        dict(evaluation_timestamp=200), dict(query_timestamp=101),
                        dict(source_index=[1, 0]), dict(source_xy=[100., 199.]),
                        dict(point_xy=[111.1, 179.]), dict(height_quality=quality()),
                        dict(reason='arbitrary full text')):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_result(dict(result(), **changes))
        for key, value in (('installed_timestamp', 200), ('source_axis_order', ['y', 'x']),
                           ('required_grids', ['missing']), ('precision_ns', 0), ('rows', 5)):
            context = expected()['context']
            context[key] = value
            with self.assertRaises(ValueError): validate_context(context)
        row = status()
        row['evaluation_timestamp'] = 200
        with self.assertRaises(ValueError): validate_status(row)
        row = result()
        row['sample_quality']['value'] = [100., 101.]
        row['height_quality']['value'] = [-1000., 1000.]
        with self.assertRaises(ValueError): validate_result(row)

    def test_missing_flags_cannot_hide_nonzero_nan_or_old_context_slots(self):
        for field, value in (('height', 1.), ('height', math.nan), ('source_xy', [1., 0.]),
                             ('source_index', [1, 0]), ('evaluation_timestamp', 1)):
            message = to_ros('TerrainQueryResult', unavailable())
            setattr(message, field, value)
            with self.subTest(field=field), self.assertRaises(ValueError): from_ros('TerrainQueryResult', message)
        message = to_ros('TerrainQueryResult', unavailable())
        message.context.terrain_id = 'cached'
        with self.assertRaises(ValueError): from_ros('TerrainQueryResult', message)
        message = to_ros('TerrainQueryResult', unavailable())
        message.height_quality.value = [0., 1.]
        with self.assertRaises(ValueError): from_ros('TerrainQueryResult', message)
        message = to_ros('TerrainQueryResult', result())
        message.height_available = 1
        with self.assertRaises(ValueError): from_ros('TerrainQueryResult', message)
        del message.height_available
        with self.assertRaises(ValueError): from_ros('TerrainQueryResult', message)

    def test_bad_wire_trailing_truncation_bool_and_wrong_ros_type_are_rejected(self):
        raw = serialize('TerrainQueryRequest', request())
        # pin flag immediately precedes a string length, instance bytes and uint64 revision.
        pin_offset = len(raw) - (1 + 4 + len('terrain-instance-a') + 8)
        for payload in (raw[:-1], raw + b'\0', raw[:pin_offset] + b'\x02' + raw[pin_offset + 1:], b''):
            with self.assertRaises(ValueError): deserialize('TerrainQueryRequest', payload)
        from uav_fusionmap_msgs.srv import MapQueryRequest
        with self.assertRaises(ValueError): from_ros('TerrainQueryRequest', MapQueryRequest())
        with self.assertRaises(ValueError): deserialize('TerrainQueryResult', b'x' * 65537)

    def test_text_bytes_and_total_request_result_limits_are_independent(self):
        for value in ('x' * 16385, '\u4e2d' * 5462, '\ud800'):
            req = request()
            req['terrain_id'] = value
            with self.assertRaises(ValueError): to_ros('TerrainQueryRequest', req)
        req = request()
        req.update(terrain_id='x' * 9000, run_id='y' * 9000)
        with self.assertRaises(ValueError): to_ros('TerrainQueryRequest', req)
        row = unavailable()
        row['reason'] = 'x' * 129
        with self.assertRaises(ValueError): to_ros('TerrainQueryResult', row)
        row = unavailable()
        for key in ('terrain_id', 'run_id', 'clock_id', 'frame_id'):
            row[key] = 'x' * 16000
        row['provider_instance_id'] = 'p' * 16000
        with self.assertRaises(ValueError): to_ros('TerrainQueryResult', row)

    def test_extra_training_fields_never_enter_public_objects(self):
        for make, name in ((request, 'TerrainQueryRequest'), (result, 'TerrainQueryResult'), (status, 'TerrainStatus')):
            for field in ('lidar', 'target', 'observed_mask'):
                row = make()
                row[field] = []
                with self.assertRaises(ValueError): to_ros(name, row)
        row = result()
        row['context']['target'] = []
        with self.assertRaises(ValueError): to_ros('TerrainQueryResult', row)

    def test_old_generated_interfaces_and_real_map_codec_keep_their_contract(self):
        from uav_fusionmap_msgs.msg import SensorBundle, MapQueryResult
        from uav_fusionmap_msgs.srv import MapQueryRequest
        from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result
        frozen = expected()
        self.assertEqual(MapQueryRequest.__slots__, frozen['old_query_fields'])
        self.assertEqual(MapQueryRequest._slot_types, frozen['old_query_types'])
        self.assertEqual(MapQueryResult.__slots__, frozen['old_result_fields'])
        self.assertEqual(SensorBundle.__slots__, frozen['old_bundle_fields'])
        old = dict(map_id='old-map', revision=1, run_id='old', clock_id='sim:old', frame_id='odom',
            query_timestamp=1, reason='', observed=False, status='unknown', point=[0., 0., 0.], index=None,
            uncertainty=dict(status='unavailable', kind='', value=None, unit='', source='old'),
            probability=None, confidence=None, last_observed_timestamp=None)
        message, stream = to_ros_query_result(old), io.BytesIO()
        message.serialize(stream)
        self.assertEqual(from_ros_query_result(type(message)().deserialize(stream.getvalue())), old)

    def test_default_map_imports_do_not_import_new_package_or_terrain(self):
        code = ('import sys; from ufm_mapping.factory import create_map; '
                'assert not any(k.startswith(("ufm_terrain_contract", "uav_fusionmap_terrain_msgs", '
                '"ufm_mapping.terrain", "ufm_mapping.m5")) for k in sys.modules)')
        subprocess.run([sys.executable, '-B', '-c', code], check=True)


if __name__ == '__main__':
    unittest.main()
