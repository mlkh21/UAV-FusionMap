"""MapQuery ROS wire contract tests; no ROS master or hardware."""
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ros_ws'))
from test_local_map_query import observation
from ufm_mapping.local_map import SparseLocalMap
from ufm_ros_contract.query_codec import (from_ros_query_request, from_ros_query_result,
                                         to_ros_query_result)
from uav_fusionmap_msgs.srv import MapQueryRequest, MapQueryResponse


def wire(message):
    buffer = io.BytesIO()
    message.serialize(buffer)
    return type(message)().deserialize(buffer.getvalue())


def request(stamp=100, **changes):
    fields = dict(map_id='perf01a-local', frame_id='odom', run_id='perf-run',
                  clock_id='sim:perf-run', query_timestamp=stamp, max_age_ns=50,
                  point=[8.0, 0.0, 0.0])
    fields.update(changes)
    return MapQueryRequest(**fields)


class MapQueryWireTest(unittest.TestCase):
    def query(self, local_map, **changes):
        result = local_map.query(**from_ros_query_request(request(**changes)))
        restored = wire(MapQueryResponse(result=to_ros_query_result(result)))
        return from_ros_query_result(restored.result)

    def test_request_retains_int64_nanoseconds_and_identity(self):
        original = request(stamp=2**53 + 1, max_age_ns=2**53 + 3)
        value = from_ros_query_request(wire(original))
        self.assertEqual(value['query_timestamp'], 2**53 + 1)
        self.assertEqual(value['max_age_ns'], 2**53 + 3)
        self.assertEqual(value['point'], [8.0, 0.0, 0.0])
        self.assertEqual(value['clock_id'], 'sim:perf-run')

    def test_all_five_statuses_roundtrip_without_unknown_becoming_free(self):
        local = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        self.assertEqual(self.query(local)['status'], 'unavailable')
        local.update(observation())
        self.assertEqual(self.query(local)['status'], 'occupied')
        self.assertEqual(self.query(local, point=[0.0, 0.0, 0.0])['status'], 'unknown')
        self.assertEqual(self.query(local, stamp=151)['status'], 'stale')
        next_observation = observation(timestamp=200, probability=0.1)
        next_observation['header']['sample_id'] += ':next'
        local.update(next_observation)
        self.assertEqual(self.query(local, stamp=200)['status'], 'free')

    def test_zero_probability_and_timestamp_are_not_missing(self):
        local = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        local.update(observation(timestamp=0, probability=0.0))
        result = self.query(local, stamp=0)
        self.assertEqual(result['status'], 'free')
        self.assertEqual(result['probability'], 0.0)
        self.assertEqual(result['last_observed_timestamp'], 0)
        self.assertIsNone(result['confidence'])

    def test_missing_numeric_slots_remain_unavailable(self):
        local = SparseLocalMap()
        result = to_ros_query_result(local.query(**from_ros_query_request(request())))
        self.assertFalse(result.probability_available)
        self.assertFalse(result.confidence_available)
        self.assertFalse(result.index_available)
        self.assertFalse(result.last_observed_timestamp_available)
        decoded = from_ros_query_result(wire(result))
        for key in ('probability', 'confidence', 'index', 'last_observed_timestamp'):
            self.assertIsNone(decoded[key])
        self.assertEqual(decoded['uncertainty']['status'], 'unavailable')
        self.assertIsNone(decoded['uncertainty']['value'])

    def test_known_quality_and_large_observation_time_are_preserved(self):
        local = SparseLocalMap(free_threshold=0.3, occupied_threshold=0.7)
        value = observation(timestamp=2**53 + 1)
        value['voxels'][0].update(confidence=0.25, uncertainty=dict(status='available',
            kind='occupancy_variance', value=[0.125], unit='dimensionless', source='fixture'))
        local.update(value)
        result = self.query(local, stamp=2**53 + 1)
        self.assertEqual(result['last_observed_timestamp'], 2**53 + 1)
        self.assertEqual(result['confidence'], 0.25)
        self.assertEqual(result['uncertainty'], value['voxels'][0]['uncertainty'])
        result['uncertainty']['value'][0] = 0.5
        self.assertEqual(local.snapshot()['cells'][0]['uncertainty']['value'], [0.125])

    def test_unknown_response_enum_is_rejected(self):
        local = SparseLocalMap()
        result = to_ros_query_result(local.query(**from_ros_query_request(request())))
        result.status = 255
        with self.assertRaises(ValueError):
            from_ros_query_result(result)


class MapQueryGraphTest(unittest.TestCase):
    def test_public_clock_allowed_but_each_sensor_or_training_path_rejected(self):
        from check_local_map_query_ros import validate_mapping_graph
        base = [[[ '/clock', ['/checker']]],
                [['/clock', ['/perf01a_mapping']],
                 ['/uav/perception/occupancy', ['/perf01a_mapping']]], []]
        self.assertEqual(validate_mapping_graph(base, '/checker'),
                         ['/clock', '/uav/perception/occupancy'])
        for topic in ('/uav/sensors/state', '/uav/localization/odom', '/uav/sensors/radar',
                      '/uav/training/lidar_supervision', '/uav/training/occupancy_target'):
            with self.subTest(topic=topic):
                altered = [base[0], base[1] + [[topic, ['/perf01a_mapping']]], []]
                with self.assertRaises(ValueError):
                    validate_mapping_graph(altered, '/checker')
        with self.assertRaises(ValueError):
            validate_mapping_graph([[['/clock', ['/checker', '/second']]], base[1], []], '/checker')


if __name__ == '__main__':
    unittest.main()
