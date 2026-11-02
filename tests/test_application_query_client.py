"""Application consumes only the public query contract and preserves all five states."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'application'))
from ufm_application import MapQueryClient, QueryTransportError
from test_local_map_query import observation
from ufm_mapping.local_map import SparseLocalMap
from ufm_ros_contract.perf01a_codec import to_ros_occupancy, from_ros_occupancy
from ufm_ros_contract.query_codec import to_ros_query_result, from_ros_query_result


def request(**changes):
    result = dict(map_id='perf01a-local', frame_id='odom', run_id='perf-run',
                  clock_id='sim:perf-run', query_timestamp=100, point=[8., 0., 0.], max_age_ns=50)
    result.update(changes)
    return result


class ApplicationClientTest(unittest.TestCase):
    def test_five_statuses_geometry_time_and_quality_are_preserved(self):
        for probability, query, expected in ((.9, request(), 'occupied'),
                (.1, request(), 'free'), (.9, request(point=[0., 0., 0.]), 'unknown'),
                (.9, request(point=[16., 0., 0.]), 'unknown'),
                (.9, request(query_timestamp=151), 'stale'),
                (.9, request(clock_id='foreign'), 'unavailable')):
            local_map = SparseLocalMap(free_threshold=.3, occupied_threshold=.7)
            value = observation(probability=probability)
            value['voxels'][0]['confidence'] = .25
            local_map.update(from_ros_occupancy(to_ros_occupancy(value)))
            def transport(fields):
                return from_ros_query_result(to_ros_query_result(local_map.query(**fields)))
            raw = transport(query)
            result = MapQueryClient(transport).query(**query)
            self.assertEqual(result, raw)
            self.assertEqual(result['status'], expected)

    def test_service_loss_never_creates_free_evidence(self):
        def failed(fields):
            raise QueryTransportError('service stopped')
        result = MapQueryClient(failed).query(**request())
        self.assertEqual(result['status'], 'unavailable')
        self.assertFalse(result['observed'])
        self.assertIsNone(result['probability'])
        self.assertIsNone(result['last_observed_timestamp'])

    def test_foreign_or_malformed_response_is_unavailable(self):
        local_map = SparseLocalMap(free_threshold=.3, occupied_threshold=.7)
        local_map.update(observation())
        base = local_map.query(**request())
        for change in (dict(run_id='foreign'), dict(query_timestamp=99),
                       dict(point=[0., 0., 0.]), dict(status='free', observed=False),
                       dict(status='unknown', reason=''), dict(status='bad'),
                       dict(probability=float('nan')), dict(probability=-.1),
                       dict(last_observed_timestamp=101), dict(observed=1)):
            candidate = dict(base, **change)
            result = MapQueryClient(lambda fields: candidate).query(**request())
            self.assertEqual(result['status'], 'unavailable')
            self.assertIsNone(result['probability'])

    def test_invalid_request_is_rejected_and_input_is_not_modified(self):
        fields = request()
        before = copy.deepcopy(fields)
        def transport(value):
            value['point'][0] = 999.
            raise QueryTransportError('lost')
        MapQueryClient(transport).query(**fields)
        self.assertEqual(fields, before)
        for change in (dict(query_timestamp=-1), dict(max_age_ns=True),
                       dict(point=[float('nan'), 0., 0.]), dict(frame_id='')):
            with self.assertRaises(ValueError):
                MapQueryClient(transport).query(**dict(fields, **change))

    def test_invalid_quality_never_becomes_free_or_retains_payload(self):
        local_map = SparseLocalMap(free_threshold=.3, occupied_threshold=.7)
        local_map.update(observation())
        base = local_map.query(**request())
        quality = dict(status='available', kind='occupancy_probability_interval',
                       value=[.8, 1.], unit='dimensionless', source='declared')
        bad_quality = [dict(quality, **change) for change in (
            dict(status='bad'), dict(value=[]), dict(value=[.95, .99]),
            dict(value=[.9, .8]), dict(value=[True, 1.]), dict(value=[float('nan'), 1.]),
            dict(value=[-.1, 1.]), dict(unit='m2'), dict(source=''), dict(source=1),
            dict(kind='occupancy_variance', value=[-.1]),
            dict(status='unavailable', value=[]))]
        for changes in ([dict(confidence=v) for v in (True, float('nan'), -.1, 1.1)] +
                        [dict(uncertainty=q) for q in bad_quality]):
            result = MapQueryClient(lambda fields: dict(base, **changes)).query(**request())
            self.assertEqual(result['status'], 'unavailable', changes)
            self.assertIsNone(result['probability'])
            self.assertIsNone(result['uncertainty']['value'])

    def test_wire_interval_and_generic_quality_are_preserved(self):
        import struct
        local_map = SparseLocalMap(free_threshold=.3, occupied_threshold=.7)
        local_map.update(observation())
        base = local_map.query(**request())
        probability = struct.unpack('!f', struct.pack('!f', .9))[0]
        interval = dict(status='available', kind='occupancy_probability_interval',
                        value=[.9, .9], unit='dimensionless', source='declared')
        for quality in (None, dict(status='unavailable', kind='', value=None, unit='', source=''),
                interval, dict(status='available', kind='future_quality', value=[-2., 3.],
                               unit='custom', source='custom')):
            candidate = dict(base, probability=probability, uncertainty=quality)
            self.assertEqual(MapQueryClient(lambda fields: candidate).query(**request()), candidate)
        # Adjacent float32 outside the rounding image must be rejected, with no epsilon.
        candidate = dict(base, probability=struct.unpack('!f', bytes.fromhex('3f666665'))[0],
                         uncertainty=interval)
        self.assertEqual(MapQueryClient(lambda fields: candidate).query(**request())['status'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
