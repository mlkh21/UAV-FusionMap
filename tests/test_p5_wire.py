"""Generated ROS wire checks for saved P5 examples; no ROS Master or runtime model."""
import copy
import io
import math
import unittest

from p5_contract import load_pair
from p5_payloads import (canonical, check_projections, materialize, roundtrip,
                         wire_vectors)


class CombinationWireTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs,cls.expected = load_pair()
        cls.vectors = {row['id']:row for row in wire_vectors(cls.inputs)}

    def test_all_frozen_examples_use_actual_generated_serialization(self):
        self.assertEqual(set(self.vectors),set(self.expected['wire_projections']))
        for name,row in self.vectors.items():
            with self.subTest(name=name):
                before = copy.deepcopy(row['value'])
                restored,raw = roundtrip(row['kind'],row['value'])
                self.assertIsInstance(raw,bytes)
                self.assertGreater(len(raw),0)
                self.assertEqual(restored,canonical(before))
                self.assertEqual(row['value'],before)
                check_projections(restored,self.expected['wire_projections'][name])

    def test_every_materialized_sample_and_inverse_passes_wire_contract(self):
        from ufm_mapping.m4_contract import validate_fixture_observation
        from ufm_mapping.terrain_dataset import validate_dataset
        for row in materialize(self.inputs):
            validate_dataset(row['terrain_dataset'])
            for item in row['samples']:
                for key,kind in [('source_state','AircraftState'),('state','AircraftState'),
                                 ('radar','RadarFrame'),('infrared','InfraredFrame'),('bundle','SensorBundle')]:
                    if item[key] is not None:
                        restored,_ = roundtrip(kind,item[key])
                        self.assertEqual(restored,canonical(item[key]),(row['id'],item['event_id'],key))
            for item in row['observations']:
                restored,_ = roundtrip('OccupancyObservation',item['value'])
                validate_fixture_observation(restored,row['map_spec'])

    def test_generated_motion_input_matches_independent_saved_geometry(self):
        checks = {c['id']:{r['after']:r['values'] for r in c['checks']} for c in self.expected['cases']}
        for case in materialize(self.inputs):
            if not case['id'].startswith('S05.'):
                continue
            item = case['samples'][-1]
            wanted = checks[case['id']]['motion']
            if item['bundle'] is None:
                self.assertEqual(item['reason'],wanted['bundle.reason'])
                self.assertEqual(wanted['bundle.delta'],0)
                continue
            bundle,_ = roundtrip('SensorBundle',item['bundle'])
            point = [bundle['radar']['points'][0][key] for key in ('x','y','z')]+[1.]
            transform = bundle['context']['T_mapping_source']
            coordinates = [sum(transform[4*i+j]*point[j] for j in range(4)) for i in range(3)]
            if 'geometry.point' in wanted:
                for actual,expected in zip(coordinates,wanted['geometry.point']):
                    self.assertAlmostEqual(actual,expected,places=9)
            if 'geometry.index' in wanted:
                self.assertEqual([math.floor((coordinates[i]-[-16,-8,-4][i])/.5) for i in range(3)],
                                 wanted['geometry.index'])
            if 'geometry.error_m' in wanted:
                self.assertAlmostEqual(abs(coordinates[1]-4.25),wanted['geometry.error_m'],places=9)
            self.assertEqual(bundle['pose_age_ns'],wanted['bundle.pose_age_ns'])

    def test_ir_gap_is_absence_not_a_zero_image_or_empty_observation(self):
        row = next(c for c in materialize(self.inputs) if c['id'] == 'S02.ir_gap')
        gap = next(i for i in row['samples'] if i['event_id'] == 'gap')
        self.assertIsNone(gap['infrared'])
        self.assertIsNone(gap['bundle'])
        self.assertEqual(gap['reason'],'infrared_unavailable')
        self.assertEqual(len(gap['radar']['points']),1)

    def test_terrain_zero_negative_no_data_and_missing_quality_keep_flags(self):
        from ufm_terrain_contract.codec import to_ros,from_ros
        for name,height in [('terrain_zero',0.),('terrain_negative',-23.5),('terrain_no_data',None)]:
            row = self.vectors[name]['value']
            message = to_ros('TerrainQueryResult',row)
            self.assertIs(message.height_available,height is not None)
            self.assertEqual(from_ros('TerrainQueryResult',message)['height'],height)
            self.assertEqual(message.height_quality.status,0)
        message = to_ros('TerrainQueryResult',self.vectors['terrain_result']['value'])
        message.height_available = False
        with self.assertRaises(ValueError): from_ros('TerrainQueryResult',message)

    def test_bad_enum_version_identity_nonfinite_and_training_fields_are_rejected(self):
        from ufm_terrain_contract.codec import to_ros,from_ros
        for key,value in [('status','free'),('protocol_version',2),('provider_instance_id',''),
                          ('height',float('inf')),('target',[]),('observed_mask',[])]:
            row = copy.deepcopy(self.vectors['terrain_result']['value']); row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): to_ros('TerrainQueryResult',row)
        message = to_ros('TerrainQueryResult',self.vectors['terrain_result']['value'])
        message.status = 255
        stream = io.BytesIO(); message.serialize(stream)
        malformed = type(message)().deserialize(stream.getvalue())
        with self.assertRaises(ValueError): from_ros('TerrainQueryResult',malformed)

    def test_wire_quality_and_integer_time_are_not_float32_or_float_time(self):
        row = self.vectors['terrain_result']
        restored,_ = roundtrip(row['kind'],row['value'])
        self.assertEqual(restored['height_quality']['value'],[12.649999999999999,13.350000000000001])
        row = self.vectors['terrain_integer']
        restored,_ = roundtrip(row['kind'],row['value'])
        self.assertIs(type(restored['query_timestamp']),int)
        self.assertEqual(restored['query_timestamp'],2**53+1)

    def test_changed_legal_payload_cannot_pass_independent_projection(self):
        row = copy.deepcopy(self.vectors['terrain_result']['value'])
        row['height'] = 13.1
        restored,_ = roundtrip('TerrainQueryResult',row)
        with self.assertRaises(ValueError): check_projections(restored,self.expected['wire_projections']['terrain_result'])
        row = copy.deepcopy(self.vectors['occupancy']['value'])
        row['voxels'][0]['index'][1] += 1
        restored,_ = roundtrip('OccupancyObservation',row)
        with self.assertRaises(ValueError): check_projections(restored,self.expected['wire_projections']['occupancy'])

    def test_old_bundle_query_and_result_layouts_remain_compatible(self):
        from uav_fusionmap_msgs.msg import SensorBundle,MapQueryResult
        from uav_fusionmap_msgs.srv import MapQueryRequest
        self.assertEqual(list(SensorBundle.__slots__),
            ['header','radar','infrared','state','context','calibration_id','radar_ir_delta_ns','pose_age_ns'])
        self.assertEqual(list(MapQueryRequest.__slots__),
            ['map_id','frame_id','run_id','clock_id','query_timestamp','point','max_age_ns'])
        self.assertEqual(MapQueryRequest._slot_types,
            ['string','string','string','string','int64','float64[3]','int64'])
        self.assertEqual(list(MapQueryResult.__slots__),
            ['map_id','revision','run_id','clock_id','frame_id','query_timestamp','point','index','index_available',
             'status','reason','probability','probability_available','confidence','confidence_available','uncertainty',
             'observed','last_observed_timestamp','last_observed_timestamp_available'])

    def test_materialized_datasets_bind_run_without_changing_dataset_time(self):
        for row in materialize(self.inputs):
            dataset = row['terrain_dataset']
            for section in ('registration','eligibility'):
                self.assertEqual(dataset[section]['run_id'],row['run_id'])
                self.assertEqual(dataset[section]['clock_id'],row['clock_id'])
            self.assertEqual(dataset['source_time']['acquisition_ns'],10)
            self.assertEqual(dataset['source_time']['clock_id'],'dataset:m5-fixture')
        self.assertEqual(self.inputs['profiles']['C']['terrain_registered_to_scene'],False)


if __name__ == '__main__':
    unittest.main()
