"""高速运动时空一致性基线的纯业务回归。"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for relative in ("mapping", "perception", "sensors", "simulation", "ros_ws"):
    sys.path.insert(0, str(ROOT / relative))

from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.placeholder import placeholder_infer
from ufm_sensors.perf01a_fixture import (build_sensor_bundle, make_fake_infrared,
                                          make_fake_radar, make_motion_radar)
from ufm_sensors.state_adapter import adapt_state
from ufm_simulation.perf01a_fixture import make_motion_state
from perf01a_async_report import validate_motion

FRAMES = {"odom_origin_policy": "px4_estimator_local_origin",
          "body_origin_policy": "source_body_virtual_flu"}
MS = 1_000_000


def adapted_motion(run_id, sequence, timestamp_ns, speed_mps):
    return adapt_state(make_motion_state(run_id, sequence, timestamp_ns, speed_mps), FRAMES)


def make_motion_bundle(speed_mps, radar_time_ns, state_time_ns, world_point=(1.25, 4.25, .25)):
    radar = make_motion_radar("motion", radar_time_ns, radar_time_ns, speed_mps, [world_point])
    infrared = make_fake_infrared("motion", radar_time_ns, radar_time_ns)
    state = adapted_motion("motion", state_time_ns // (10 * MS), state_time_ns, speed_mps)
    bundle, reason = build_sensor_bundle(radar, infrared, [state], max_pose_age_ns=10 * MS)
    if bundle is None:
        raise AssertionError(reason)
    return bundle


def transformed_point(bundle):
    point = bundle["radar"]["points"][0]
    transform = bundle["context"]["T_mapping_source"]
    return [sum(transform[4 * axis + col] * (point['xyz'[col]] if col < 3 else 1.0)
                for col in range(4)) for axis in range(3)]


class MotionConsistencyTest(unittest.TestCase):
    def test_source_position_velocity_and_rotation_agree(self):
        for speed in (35., 50., 70.):
            source = make_motion_state('motion', 1, 1_000 * MS, speed)
            self.assertEqual(source['position'], [speed, 0., 0.])
            self.assertEqual(source['linear_velocity'], [speed, 0., 0.])
            state = adapted_motion('motion', 1, 1_000 * MS, speed)
            self.assertEqual(state['position'], [0., speed, 0.])
            self.assertNotEqual(state['orientation_xyzw'], [0., 0., 0., 1.])

    def test_exact_historical_pose_keeps_fixed_world_obstacle(self):
        for speed in (35.0, 50.0, 70.0):
            with self.subTest(speed=speed):
                for time_ns in (0, 10 * MS, 20 * MS, 30 * MS):
                    bundle = make_motion_bundle(speed, time_ns, time_ns)
                    for actual, expected in zip(transformed_point(bundle), (1.25, 4.25, .25)):
                        self.assertAlmostEqual(actual, expected, places=9)
                    self.assertEqual(placeholder_infer(bundle)['voxels'][0]['index'], [34, 24, 8])
                    self.assertEqual(bundle["pose_age_ns"], 0)

    def test_recent_history_pose_has_explicit_speed_error_budget(self):
        for speed in (35.0, 50.0, 70.0):
            with self.subTest(speed=speed):
                bundle = make_motion_bundle(speed, 15 * MS, 10 * MS)
                error = abs(transformed_point(bundle)[1] - 4.25)
                self.assertAlmostEqual(error, speed * 0.005, places=9)
                self.assertLessEqual(error, speed * 0.010)
                self.assertEqual(bundle["pose_age_ns"], 5 * MS)

    def test_grid_boundary_uses_carried_transform_not_ideal_world_cell(self):
        speed = 50.
        point = (1.25, 4.25, .25)
        bundle = make_motion_bundle(speed, 15 * MS, 10 * MS, point)
        observation = placeholder_infer(bundle)
        local_map = SparseLocalMap()
        self.assertTrue(local_map.update(observation))
        record = dict(timestamp=15 * MS, state_timestamp=10 * MS, pose_age_ns=5 * MS,
            state_position=bundle['state']['position'], state_velocity=bundle['state']['linear_velocity'],
            radar_to_odom=bundle['context']['T_mapping_source'],
            radar_points=[[p[k] for k in ('x', 'y', 'z')] for p in bundle['radar']['points']])
        cells = [dict(index=c['index'], timestamp=c['last_observed_timestamp'],
            probability=c['probability'], observed=c['observed']) for c in local_map.snapshot()['cells']]
        records = dict(bundle=[record], occupancy=[dict(timestamp=15 * MS,
            voxels=[v['index'] for v in observation['voxels']])],
            map=[dict(timestamp=15 * MS, cells=cells)])
        aging = dict(staleness_limit_ns=100 * MS,
                     rows=[dict(query_timestamp=20 * MS, cells=cells, stale=[])])
        decisions = [dict(reason='', timestamp=15 * MS)]
        profile = dict(speed_mps=speed, obstacles_odom=[point])
        self.assertEqual(validate_motion(records, decisions, profile, aging)['errors'], [])
        corrupted = copy.deepcopy(records)
        corrupted['occupancy'][0]['voxels'][0][1] += 1
        self.assertIn('motion: occupancy quantization differs from carried transform',
                      validate_motion(corrupted, decisions, profile, aging)['errors'])

    def test_pose_older_than_ten_ms_is_rejected(self):
        speed = 70.0
        radar = make_motion_radar("motion", 1, 20 * MS, speed, [(1.25, 4.25, .25)])
        infrared = make_fake_infrared("motion", 1, 20 * MS)
        state = adapted_motion("motion", 0, 0, speed)
        bundle, reason = build_sensor_bundle(radar, infrared, [state], max_pose_age_ns=10 * MS)
        self.assertIsNone(bundle)
        self.assertEqual(reason, "pose_age_exceeded")

    def test_map_ages_during_gap_and_accepts_new_observation_after_recovery(self):
        observation = placeholder_infer(make_motion_bundle(50.0, 0, 0))
        local_map = SparseLocalMap(staleness_limit_ns=50 * MS)
        self.assertTrue(local_map.update(observation))
        self.assertEqual(local_map.stale_cells(49 * MS), [])
        self.assertEqual(local_map.stale_cells(51 * MS), [(34, 24, 8)])

        unavailable = copy.deepcopy(observation)
        unavailable["header"].update(timestamp=60 * MS, sample_id="perception.occupancy:gap")
        unavailable["context"]["reference_timestamp"] = 60 * MS
        unavailable["header"].update(status="unavailable", reason="radar_ir_timeout")
        unavailable["voxels"] = []
        self.assertFalse(local_map.update(unavailable))
        self.assertEqual(local_map.stale_cells(60 * MS), [(34, 24, 8)])

        recovered = placeholder_infer(make_motion_bundle(50.0, 70 * MS, 70 * MS))
        self.assertTrue(local_map.update(recovered))
        self.assertEqual(local_map.stale_cells(70 * MS), [])
        self.assertEqual(local_map.snapshot()["revision"], 2)

    def test_received_motion_and_map_oracle_rejects_changed_point_and_cell(self):
        speed = 50.
        bundle = make_motion_bundle(speed, 15 * MS, 10 * MS)
        obs = placeholder_infer(bundle)
        local_map = SparseLocalMap()
        self.assertTrue(local_map.update(obs))
        records = dict(bundle=[dict(timestamp=15 * MS, state_timestamp=10 * MS,
            pose_age_ns=5 * MS, state_position=bundle['state']['position'],
            state_velocity=bundle['state']['linear_velocity'],
            radar_to_odom=bundle['context']['T_mapping_source'],
            radar_points=[[p[k] for k in ('x', 'y', 'z')] for p in bundle['radar']['points']])],
            occupancy=[dict(timestamp=15 * MS, voxels=[v['index'] for v in obs['voxels']])],
            map=[dict(timestamp=15 * MS, cells=[dict(index=c['index'],
                timestamp=c['last_observed_timestamp'], probability=c['probability'],
                observed=c['observed']) for c in local_map.snapshot()['cells']])])
        aging = dict(staleness_limit_ns=100 * MS, rows=[dict(query_timestamp=20 * MS,
            cells=records['map'][0]['cells'], stale=[])])
        decision = [dict(reason='', timestamp=15 * MS)]
        profile = dict(speed_mps=speed, obstacles_odom=[[1.25, 4.25, .25]])
        self.assertEqual(validate_motion(records, decision, profile, aging)['errors'], [])
        altered = copy.deepcopy(records)
        altered['bundle'][0]['radar_points'][0][0] += .4
        self.assertIn('motion: radar point differs from sampling-time world scene',
                      validate_motion(altered, decision, profile, aging)['errors'])
        altered = copy.deepcopy(records)
        altered['bundle'][0]['state_velocity'] = [0., 0., 0.]
        self.assertIn('motion: state position or radar-to-odom transform differs',
                      validate_motion(altered, decision, profile, aging)['errors'])
        altered = copy.deepcopy(records)
        altered['map'][0]['cells'][0]['index'] = [0, 0, 0]
        self.assertIn('motion: map cells/unknown or observation timestamps differ',
                      validate_motion(altered, decision, profile, aging)['errors'])
        aging['rows'][0]['stale'] = [[34, 24, 8]]
        self.assertIn('motion: map clock-aging result differs from last observation',
                      validate_motion(records, decision, profile, aging)['errors'])


if __name__ == "__main__":
    unittest.main()
