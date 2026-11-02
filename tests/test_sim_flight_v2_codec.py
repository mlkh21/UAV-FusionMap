"""Real generated ROS messages and independent bytes, including hostile wire inputs."""
import io
import struct
import unittest

from sim_flight_v2_fixture import ack, cases, frame, packed, replace, response
from sim_motion_fixture import cases as legacy_cases, wire_object, expected as old_expected, independent_bytes
from ufm_flight_contract.codec import deserialize, from_ros, serialize, to_ros
from ufm_scene_contract.codec import deserialize as old_deserialize, serialize as old_serialize


def raw(message):
    stream = io.BytesIO()
    message.serialize(stream)
    return stream.getvalue()


class FlightV2CodecTest(unittest.TestCase):
    def test_all_independent_bytes_with_actual_genpy_roundtrips(self):
        from uav_fusionmap_sim_scene_msgs import msg, srv
        types = dict(SceneFrame=msg.SceneFrame, SceneCaptureAck=msg.SceneCaptureAck,
                     SceneStepRequest=srv.SceneStepRequest, SceneStepResponse=srv.SceneStepResponse)
        self.assertIs(srv.SceneStep._request_class, srv.SceneStepRequest)
        self.assertIs(srv.SceneStep._response_class, srv.SceneStepResponse)
        for row in cases():
            kind, value = row['kind'], row['value']
            with self.subTest(kind=kind, step=value.get('step_index')):
                generated = to_ros(kind, value)
                self.assertIs(type(generated), types[kind])
                wire = raw(generated)
                self.assertEqual(wire, packed(kind, value))
                self.assertEqual(wire, serialize(kind, value))
                self.assertEqual(from_ros(kind, types[kind]().deserialize(wire)), value)
                self.assertEqual(deserialize(kind, wire), value)

    def test_every_v2_wire_rejected_by_v1(self):
        for row in cases():
            with self.assertRaises(ValueError): old_deserialize(row['kind'], packed(row['kind'], row['value']))

    def test_every_v1_wire_keeps_old_bytes_and_is_rejected_by_v2(self):
        for row in legacy_cases():
            wire = packed(row['kind'], row['value'])
            self.assertEqual(old_serialize(row['kind'], row['value']), wire)
            self.assertEqual(old_deserialize(row['kind'], wire), row['value'])
            with self.assertRaises(ValueError): deserialize(row['kind'], wire)

    def test_false_applied_flag_cannot_create_an_unversioned_failure_channel(self):
        message = to_ros('SceneStepResponse', response(1, False))
        message.has_applied_frame = False
        with self.assertRaises(ValueError): from_ros('SceneStepResponse', message)
        with self.assertRaises(ValueError): deserialize('SceneStepResponse', raw(message))

    def test_bool_bytes_truncations_tails_encoding_and_oversize(self):
        for kind, value in (('SceneFrame', frame()), ('SceneCaptureAck', ack()),
                            ('SceneStepRequest', dict(frame=frame())), ('SceneStepResponse', response())):
            wire = serialize(kind, value)
            for invalid in (b'', wire[:-1], wire + b'\0', b'\0' * 4097, bytearray(wire)):
                with self.assertRaises(ValueError): deserialize(kind, invalid)
        wire = serialize('SceneStepResponse', response())
        with self.assertRaisesRegex(ValueError, 'boolean_byte'):
            deserialize('SceneStepResponse', b'\2' + wire[1:])
        wire = serialize('SceneFrame', frame())
        with self.assertRaisesRegex(ValueError, 'text_length'):
            deserialize('SceneFrame', wire[:1] + struct.pack('<I', 2**32 - 1) + wire[5:])
        with self.assertRaises(ValueError):
            deserialize('SceneFrame', wire[:5] + b'\xff' + wire[6:])

    def test_nonzero_uncertainty_array_rejected_before_genpy(self):
        layout = old_expected()['layout']
        value = wire_object('SceneFrame', frame(), layout)
        value['state']['quality']['uncertainty']['value'] = [0.]
        with self.assertRaisesRegex(ValueError, 'variable_array'):
            deserialize('SceneFrame', independent_bytes('SceneFrame', value, layout))

    def test_hidden_numeric_slots_and_dirty_false_capture_flags(self):
        for bad in (1., -0., float('nan'), float('inf')):
            message = to_ros('SceneFrame', frame())
            message.state.quality.confidence = bad
            with self.assertRaises(ValueError): from_ros('SceneFrame', message)
            with self.assertRaises(ValueError): deserialize('SceneFrame', raw(message))
        for prefix in ('radar', 'infrared'):
            message = to_ros('SceneStepResponse', response())
            setattr(message, prefix + '_timestamp', 1)
            with self.assertRaises(ValueError): from_ros('SceneStepResponse', message)
            with self.assertRaises(ValueError): deserialize('SceneStepResponse', raw(message))

    def test_exact_classes_enums_booleans_and_fixed_array_shapes(self):
        with self.assertRaises(ValueError): from_ros('SceneFrame', to_ros('SceneStepRequest', dict(frame=frame())))
        with self.assertRaises(ValueError): from_ros('unknown', to_ros('SceneFrame', frame()))
        for field, bad in (('protocol_version', True), ('step_index', True),
                           ('angular_velocity_flu', [0., 0.])):
            message = to_ros('SceneFrame', frame())
            setattr(message, field, bad)
            with self.assertRaises(ValueError): from_ros('SceneFrame', message)
        for field, bad in (('state_source', True), ('state_source', 9), ('position', [0., 0.])):
            message = to_ros('SceneFrame', frame())
            setattr(message.state, field, bad)
            with self.assertRaises(ValueError): from_ros('SceneFrame', message)
        for field in ('accepted', 'has_applied_frame', 'radar_captured', 'infrared_captured'):
            message = to_ros('SceneStepResponse', response())
            setattr(message, field, 1)
            with self.assertRaises(ValueError): from_ros('SceneStepResponse', message)

    def test_generated_wire_mutations_cannot_bypass_semantics(self):
        for field, bad in (('protocol_version', 1), ('protocol_version', 9), ('sensor_kind', 0),
                           ('clock_id', 'sim:foreign'), ('step_index', 7500),
                           ('measurement_timestamp', -1), ('measurement_timestamp', 100000000)):
            message = to_ros('SceneCaptureAck', ack())
            setattr(message, field, bad)
            with self.assertRaises(ValueError): deserialize('SceneCaptureAck', raw(message))
        for bad in (float('nan'), float('inf'), -float('inf')):
            message = to_ros('SceneFrame', frame())
            message.state.linear_velocity[0] = bad
            with self.assertRaises(ValueError): deserialize('SceneFrame', raw(message))

    def test_bound_ack_and_response_after_real_wire(self):
        wire = serialize('SceneCaptureAck', ack())
        self.assertEqual(deserialize('SceneCaptureAck', wire, frame=frame(7525)), ack())
        with self.assertRaises(ValueError): deserialize('SceneCaptureAck', wire, frame=frame(7550))
        wire = serialize('SceneStepResponse', response(7525))
        self.assertEqual(deserialize('SceneStepResponse', wire, request=dict(frame=frame(7525))), response(7525))
        with self.assertRaises(ValueError): deserialize('SceneStepResponse', wire, request=dict(frame=frame(7550)))
        wanted = replace(frame(7525), 'state.position', [1., 0., .5])
        with self.assertRaises(ValueError): deserialize('SceneStepResponse', wire, request=dict(frame=wanted))


if __name__ == '__main__':
    unittest.main()
