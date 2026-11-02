"""Real genpy serialization, independent struct bytes and hostile wire rejection."""
import copy
import io
import struct
import unittest

from sim_motion_fixture import ack, cases, expected, frame, independent_bytes, response, wire_object
from ufm_scene_contract.codec import deserialize, from_ros, serialize, to_ros


class MotionCodecTest(unittest.TestCase):
    def test_actual_generated_layout_matches_independently_frozen_contract(self):
        from uav_fusionmap_msgs import msg as legacy
        from uav_fusionmap_sim_scene_msgs import msg, srv
        layout = expected()['layout']
        for name, fields in layout.items():
            cls = getattr(legacy if name in ('AircraftState', 'ObservationHeader', 'Quality', 'Uncertainty')
                          else srv if name.endswith(('Request', 'Response')) else msg, name)
            pairs = [pair.split(':') for pair in fields.split()]
            wanted = []
            for _, kind in pairs:
                if kind in layout:
                    kind = ('uav_fusionmap_msgs/' if kind in ('AircraftState', 'ObservationHeader', 'Quality', 'Uncertainty')
                            else 'uav_fusionmap_sim_scene_msgs/') + kind
                wanted.append(kind)
            self.assertEqual(list(cls.__slots__), [key for key, _ in pairs])
            self.assertEqual(cls._slot_types, wanted)
        self.assertEqual(srv.SceneStep._request_class, srv.SceneStepRequest)
        self.assertEqual(srv.SceneStep._response_class, srv.SceneStepResponse)

    def test_every_saved_case_uses_actual_generated_serialization_and_independent_bytes(self):
        layout = expected()['layout']
        for row in cases():
            with self.subTest(case=row['id']):
                message, stream = to_ros(row['kind'], row['value']), io.BytesIO()
                message.serialize(stream)
                raw = stream.getvalue()
                self.assertEqual(raw, independent_bytes(row['kind'], wire_object(row['kind'], row['value'], layout), layout))
                self.assertEqual(from_ros(row['kind'], type(message)().deserialize(raw)), row['value'])
                self.assertEqual(deserialize(row['kind'], raw), row['value'])

    def test_zero_and_negative_height_are_present_and_large_ns_is_not_float(self):
        for height in (0., -2.):
            value = deserialize('SceneStepResponse', serialize('SceneStepResponse', response(height=height)))
            self.assertEqual(value['applied_frame']['state']['position'][2], height)
        value = frame(2251799814)
        self.assertEqual(deserialize('SceneFrame', serialize('SceneFrame', value))['state']['header']['timestamp'], 9007199256000000)

    def test_missing_applied_frame_is_canonical_nested_zero_and_not_valid_geometry(self):
        row = response(accepted=False, applied=False)
        message = to_ros('SceneStepResponse', row)
        self.assertFalse(message.has_applied_frame)
        self.assertEqual(from_ros('SceneStepResponse', message), row)
        message.applied_frame.state.position[0] = 1.
        with self.assertRaises(ValueError): from_ros('SceneStepResponse', message)
        message = to_ros('SceneStepResponse', row)
        message.applied_frame.state.position[0] = -0.
        with self.assertRaises(ValueError): from_ros('SceneStepResponse', message)

    def test_absence_flags_are_strict_and_dirty_numeric_slots_rejected(self):
        message = to_ros('SceneStepResponse', response(1))
        message.radar_timestamp = 1
        with self.assertRaises(ValueError): from_ros('SceneStepResponse', message)
        for key in ('accepted', 'has_applied_frame', 'radar_captured', 'infrared_captured'):
            message = to_ros('SceneStepResponse', response())
            setattr(message, key, 1)
            with self.assertRaises(ValueError): from_ros('SceneStepResponse', message)

    def test_zero_capture_stamp_on_failure_is_present_not_absent(self):
        row = response(accepted=False)
        row['radar_timestamp'] = 0
        message = to_ros('SceneStepResponse', row)
        self.assertTrue(message.radar_captured)
        self.assertEqual(deserialize('SceneStepResponse', serialize('SceneStepResponse', row)), row)

    def test_legacy_nested_confidence_slots_enums_and_array_types_are_checked(self):
        for bad in (1., -0., float('nan')):
            message = to_ros('SceneFrame', frame())
            message.state.quality.confidence = bad
            with self.assertRaises(ValueError): from_ros('SceneFrame', message)
        for key, bad in [('state_source', True), ('state_source', 99), ('position', [0., 0.])]:
            message = to_ros('SceneFrame', frame())
            setattr(message.state, key, bad)
            with self.assertRaises(ValueError): from_ros('SceneFrame', message)
        message = to_ros('SceneFrame', frame())
        message.state.header.source_type = True
        with self.assertRaises(ValueError): from_ros('SceneFrame', message)

    def test_noncanonical_bool_bytes_truncation_tails_and_size_fail(self):
        for row in cases():
            raw = serialize(row['kind'], row['value'])
            for invalid in (b'', raw[:-1], raw + b'\0', b'\0' * 4097):
                with self.assertRaises(ValueError): deserialize(row['kind'], invalid)
        raw = serialize('SceneStepResponse', response(accepted=False, applied=False))
        with self.assertRaisesRegex(ValueError, 'boolean_byte'):
            deserialize('SceneStepResponse', b'\2' + raw[1:])

    def test_hostile_string_or_variable_array_lengths_rejected_before_genpy(self):
        raw = serialize('SceneFrame', frame())
        # Frame version precedes AircraftState.header.schema_version's string length.
        with self.assertRaisesRegex(ValueError, 'text_length'):
            deserialize('SceneFrame', raw[:1] + struct.pack('<I', 2**32 - 1) + raw[5:])
        layout = expected()['layout']
        wire = wire_object('SceneFrame', frame(), layout)
        wire['state']['quality']['uncertainty']['value'] = [0.]
        with self.assertRaisesRegex(ValueError, 'variable_array'):
            deserialize('SceneFrame', independent_bytes('SceneFrame', wire, layout))

    def test_mutated_wire_version_enums_nonfinite_and_identity_fail(self):
        for key, bad in [('protocol_version', 9), ('sensor_kind', 0), ('measurement_timestamp', -1),
                         ('clock_id', 'sim:foreign'), ('reason', 'fake_success')]:
            message = to_ros('SceneCaptureAck', ack())
            setattr(message, key, bad)
            stream = io.BytesIO()
            message.serialize(stream)
            with self.assertRaises(ValueError): deserialize('SceneCaptureAck', stream.getvalue())
        message = to_ros('SceneFrame', frame())
        message.angular_velocity_flu[0] = float('inf')
        stream = io.BytesIO()
        message.serialize(stream)
        with self.assertRaises(ValueError): deserialize('SceneFrame', stream.getvalue())

    def test_response_and_ack_binding_checks_survive_actual_wire(self):
        raw = serialize('SceneStepResponse', response())
        self.assertEqual(deserialize('SceneStepResponse', raw, request=dict(frame=frame())), response())
        with self.assertRaises(ValueError): deserialize('SceneStepResponse', raw, request=dict(frame=frame(50)))
        raw = serialize('SceneCaptureAck', ack())
        with self.assertRaises(ValueError): deserialize('SceneCaptureAck', raw, frame=frame(50))

    def test_wire_type_and_text_encoding_are_not_duck_typed(self):
        with self.assertRaises(ValueError): from_ros('SceneFrame', to_ros('SceneStepRequest', dict(frame=frame())))
        row = ack()
        row['run_id'] = '\ud800'
        with self.assertRaises(ValueError): to_ros('SceneCaptureAck', row)
        with self.assertRaises(ValueError): to_ros('unknown', {})


if __name__ == '__main__':
    unittest.main()
