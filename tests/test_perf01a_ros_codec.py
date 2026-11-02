"""真实ROS消息往返保留采样时间、质量与变换，不启动master。"""
import io
import copy
import unittest

from test_perf01a_contract import valid_bundle
from ufm_perception.placeholder import placeholder_infer
from ufm_mapping.local_map import SparseLocalMap
from ufm_ros_contract.perf01a_codec import (
    to_ros_bundle, from_ros_bundle, to_ros_infrared, from_ros_infrared,
    to_ros_occupancy, from_ros_occupancy,
    to_ros_snapshot, from_ros_snapshot)


def roundtrip(value, encode, decode):
    msg = encode(value)
    stream = io.BytesIO()
    msg.serialize(stream)
    return decode(type(msg)().deserialize(stream.getvalue()))


class CodecTest(unittest.TestCase):
    def test_unknown_transform_and_uncertainty_enums_are_rejected(self):
        observation = placeholder_infer(valid_bundle())
        for field in ('T_mapping_source_status', 'T_mapping_body_status'):
            for value in (2, 255):
                msg = to_ros_occupancy(observation)
                setattr(msg.context, field, value)
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    from_ros_occupancy(msg)
        msg = to_ros_occupancy(observation)
        msg.context.pose_uncertainty.status = 255
        with self.assertRaises(ValueError):
            from_ros_occupancy(msg)

    def test_unsupported_schema_rejected_on_both_sides(self):
        observation = placeholder_infer(valid_bundle())
        msg = to_ros_occupancy(observation)
        msg.header.schema_version = 'unsupported'
        with self.assertRaises(ValueError):
            from_ros_occupancy(msg)
        invalid = copy.deepcopy(observation)
        invalid['header']['schema_version'] = 'unsupported'
        with self.assertRaises(ValueError):
            to_ros_occupancy(invalid)

    def test_infrared_decode_borrow_is_opt_in(self):
        msg = to_ros_infrared(valid_bundle()['infrared'])
        detached = from_ros_infrared(msg)
        borrowed = from_ros_infrared(msg, borrow_image=True)
        self.assertIsNot(detached['image'], msg.image)
        self.assertIs(borrowed['image'], msg.image)
        self.assertEqual(detached, borrowed)
        prior = detached['image'][0]
        msg.image[0] = prior + 1
        self.assertEqual(detached['image'][0], prior)
        self.assertEqual(borrowed['image'][0], prior + 1)

    def test_bundle_int64_time_and_pose(self):
        source = valid_bundle(radar_timestamp=2**53 + 1)
        restored = roundtrip(source, to_ros_bundle, from_ros_bundle)
        self.assertEqual(restored, source)

    def test_occupancy_uncertainty_and_float32(self):
        source = placeholder_infer(valid_bundle())
        restored = roundtrip(source, to_ros_occupancy, from_ros_occupancy)
        self.assertEqual(restored['context'], source['context'])
        self.assertEqual(restored['header'], source['header'])
        self.assertEqual(restored['voxels'][0]['uncertainty'], source['voxels'][0]['uncertainty'])
        self.assertAlmostEqual(restored['voxels'][0]['probability'], .9, places=6)

    def test_snapshot_uncertainty(self):
        local = SparseLocalMap()
        local.update(placeholder_infer(valid_bundle()))
        source = local.snapshot()
        restored = roundtrip(source, to_ros_snapshot, from_ros_snapshot)
        self.assertEqual(restored['header'], source['header'])
        self.assertEqual(restored['cells'][0]['uncertainty'], source['cells'][0]['uncertainty'])
        self.assertEqual(restored['coverage'], source['coverage'])
