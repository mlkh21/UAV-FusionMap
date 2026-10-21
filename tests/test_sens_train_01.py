"""SENS-TRAIN-01 的场景、外参和仅训练监督合同。"""
import copy
import math
from pathlib import Path
import sys
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sensors"))
sys.path.insert(0, str(ROOT / "simulation"))

from ufm_simulation.perf01a_fixture import make_motion_state, make_scan_motion_state
from ufm_sensors.state_adapter import adapt_state
from ufm_sensors.training_supervision import (
    _state_pose_at, build_training_sample, validate_training_sample,
)


def fixture():
    with (ROOT / "configs/sens_train_01_fixture.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def multiray_fixture():
    with (ROOT / "configs/sens_train_01_multiray_fixture.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def motion_fixture():
    with (ROOT / "configs/sens_train_01_motion_fixture.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def state(run="train-a", stamp=100_000_000, speed=0):
    return adapt_state(make_motion_state(run, stamp // 1_000_000, stamp, speed), {
        "odom_origin_policy": "px4_estimator_local_origin",
        "body_origin_policy": "source_body_virtual_flu",
    })


class TrainingSupervisionTest(unittest.TestCase):
    def test_same_world_hit_does_not_split_at_float_voxel_boundary(self):
        cfg = motion_fixture()
        cfg['lidar']['rays_lidar'] = [[1., 0., 0.]] * 3
        history = [adapt_state(make_scan_motion_state('boundary', index, stamp,
                                                       1_000_000_000, 35., 0.), {
            'odom_origin_policy': 'px4_estimator_local_origin',
            'body_origin_policy': 'source_body_virtual_flu',
        }) for index, stamp in enumerate((900_000_000, 1_000_000_000, 1_100_000_000))]
        for displacement, expected_y in ((0., 4), (-1e-9, 4), (1e-9, 3)):
            shifted = copy.deepcopy(cfg)
            shifted['lidar']['grid_origin_m'][1] += displacement
            sample = build_training_sample(history[1], shifted, state_history=history)
            self.assertEqual(len(sample['lidar']['points']), 2)
            occupied = [i for i, label in enumerate(sample['supervision']['target']) if label == 'occupied']
            with self.subTest(displacement=displacement):
                self.assertEqual(occupied, [(10 * 10 + expected_y) * 8 + 4])

    def test_nonzero_scan_deskews_points_to_scan_midpoint(self):
        cfg = motion_fixture()
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        sample = build_training_sample(history[1], cfg, state_history=history)
        self.assertEqual(sample["schema_version"], "0.2")
        self.assertEqual(sample["lidar"]["scan_start"], 900_000_000)
        self.assertEqual(sample["lidar"]["scan_end"], 1_100_000_000)
        self.assertEqual(sample["lidar"]["coordinate_frame_timestamp_ns"], 1_000_000_000)
        self.assertEqual(sample["lidar"]["motion_compensation_method"],
                         "linear_position_shortest_arc_slerp_to_scan_midpoint")
        self.assertEqual([point["point_time_ns"] for point in sample["lidar"]["points"]],
                         [900_000_000, 1_100_000_000])
        self.assertEqual([point["time_offset_ns"] for point in sample["lidar"]["points"]],
                         [0, 200_000_000])
        self.assertEqual(sample["lidar"]["ray_time_offsets_ns"],
                         [0, 100_000_000, 200_000_000])
        self.assertAlmostEqual(sample["lidar"]["points"][0]["x"], 4.25)
        self.assertAlmostEqual(sample["lidar"]["points"][1]["x"], 4.30)
        self.assertNotEqual(sample["lidar"]["points"][0]["raw_xyz"],
                            [sample["lidar"]["points"][0][axis] for axis in ("x", "y", "z")])
        occupied = [index for index, value in enumerate(sample["supervision"]["target"])
                    if value == "occupied"]
        self.assertEqual(occupied, [676, 684])
        self.assertEqual(len(sample["lidar"]["points"]), 2)
        self.assertFalse(any(sample["supervision"]["observed_mask"][index]
                             for index, value in enumerate(sample["supervision"]["target"])
                             if value == "unknown" and index not in occupied))
        self.assertTrue(validate_training_sample(sample, cfg))

    def test_nonzero_scan_no_return_remains_unknown(self):
        cfg = motion_fixture()
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        sample = build_training_sample(history[1], cfg, state_history=history)
        # The third configured ray is valid, but sees no obstacle. No echo means
        # no free-space certification for that ray.
        self.assertEqual(len(sample["lidar"]["points"]), 2)
        self.assertEqual([point["ray_index"] for point in sample["lidar"]["points"]], [0, 2])
        self.assertEqual(sample["supervision"]["target"][676], "occupied")
        self.assertEqual(sample["supervision"]["target"][684], "occupied")
        baseline = copy.deepcopy(cfg)
        baseline["lidar"]["ray_time_offsets_ns"] = [0, 200_000_000]
        baseline["lidar"]["rays_lidar"] = [
            cfg["lidar"]["rays_lidar"][0], cfg["lidar"]["rays_lidar"][2]]
        without_no_return = build_training_sample(history[1], baseline, state_history=history)
        self.assertEqual(sample["supervision"]["target"],
                         without_no_return["supervision"]["target"])
        self.assertEqual(sample["supervision"]["observed_mask"],
                         without_no_return["supervision"]["observed_mask"])

    def test_nonzero_scan_occlusion_keeps_behind_voxel_unknown(self):
        cfg = motion_fixture()
        cfg["scene"]["obstacles_odom"].append({
            "obstacle_id": "behind_forward_box",
            "center_m": [0.0, 7.0, 0.2],
            "size_m": [0.5, 0.5, 0.5],
            "ir_pixel": [2, 1],
        })
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        sample = build_training_sample(history[1], cfg, state_history=history)

        def cell(x, y=4, z=4):
            return (x * cfg["lidar"]["grid_shape"][1] + y) * cfg["lidar"]["grid_shape"][2] + z

        self.assertEqual(len(sample["lidar"]["points"]), 2)
        self.assertEqual(sample["supervision"]["target"][cell(8)], "occupied")
        self.assertFalse(sample["supervision"]["observed_mask"][cell(11)])
        self.assertEqual(sample["supervision"]["target"][cell(11)], "unknown")

    def test_nonzero_scan_range_cutoff_does_not_create_free_space(self):
        cfg = motion_fixture()
        cfg["lidar"]["max_range_m"] = 4.0
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        sample = build_training_sample(history[1], cfg, state_history=history)
        self.assertEqual(sample["lidar"]["points"], [])
        self.assertEqual(set(sample["supervision"]["target"]), {"unknown"})
        self.assertFalse(any(sample["supervision"]["observed_mask"]))

    def test_nonzero_scan_all_no_return_keeps_every_time_slot_unknown(self):
        cfg = motion_fixture()
        cfg["scene"]["obstacles_odom"] = []
        history = [state(run="empty-motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        sample = build_training_sample(history[1], cfg, state_history=history)
        self.assertEqual(sample["lidar"]["ray_time_offsets_ns"],
                         [0, 100_000_000, 200_000_000])
        self.assertEqual(sample["lidar"]["points"], [])
        self.assertEqual(set(sample["supervision"]["target"]), {"unknown"})
        self.assertFalse(any(sample["supervision"]["observed_mask"]))
        self.assertTrue(validate_training_sample(sample, cfg))

    def test_nonzero_scan_ray_outside_declared_fov_is_rejected(self):
        cfg = motion_fixture()
        angle = math.radians(20.0)
        cfg["lidar"]["rays_lidar"][1] = [math.cos(angle), math.sin(angle), 0.0]
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        with self.assertRaises(ValueError):
            build_training_sample(history[1], cfg, state_history=history)

    def test_fixture_scene_matrix_preserves_label_contract(self):
        cases = [
            (fixture(), state(), 1),
            (multiray_fixture(), state(), 2),
        ]
        motion_cfg = motion_fixture()
        motion_history = [state(run="motion", stamp=stamp, speed=1)
                          for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        cases.append((motion_cfg, motion_history[1], 2))
        for cfg, reference, expected_returns in cases:
            with self.subTest(scene=cfg["scene"]["scene_id"]):
                kwargs = {} if cfg["lidar"]["scan_duration_ns"] == 0 else {
                    "state_history": motion_history,
                }
                sample = build_training_sample(reference, cfg, **kwargs)
                self.assertEqual(len(sample["lidar"]["points"]), expected_returns)
                self.assertTrue(set(sample["supervision"]["target"])
                                .issubset({"free", "occupied", "unknown"}))
                self.assertTrue(validate_training_sample(sample, cfg))

    def test_nonzero_scan_is_rejected_by_v01_record(self):
        cfg = motion_fixture()
        cfg["schema_version"] = "0.1"
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        with self.assertRaises(ValueError):
            build_training_sample(history[1], cfg, state_history=history)

    def test_record_validator_rejects_missing_ray_timing_and_duplicate_returns(self):
        cfg = motion_fixture()
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        sample = build_training_sample(history[1], cfg, state_history=history)
        missing = copy.deepcopy(sample)
        del missing["lidar"]["ray_time_offsets_ns"]
        with self.assertRaises(ValueError):
            validate_training_sample(missing, cfg)
        duplicate = copy.deepcopy(sample)
        duplicate["lidar"]["points"].append(copy.deepcopy(duplicate["lidar"]["points"][0]))
        with self.assertRaises(ValueError):
            validate_training_sample(duplicate, cfg)
        malformed = copy.deepcopy(sample)
        malformed["lidar"]["points"][0] = ["not", "a", "mapping"]
        with self.assertRaises(ValueError):
            validate_training_sample(malformed, cfg)
        missing_section = copy.deepcopy(sample)
        del missing_section["lidar"]
        with self.assertRaises(ValueError):
            validate_training_sample(missing_section, cfg)
        missing_identity = copy.deepcopy(sample)
        del missing_identity["mode"]
        with self.assertRaises(ValueError):
            validate_training_sample(missing_identity, cfg)
        missing_field = copy.deepcopy(sample)
        del missing_field["lidar"]["scan_end"]
        with self.assertRaises(ValueError):
            validate_training_sample(missing_field, cfg)

    def test_observed_mask_rejects_numeric_surrogates_for_boolean_values(self):
        cfg = fixture()
        sample = build_training_sample(state(), cfg)
        index = sample['supervision']['target'].index('occupied')
        sample['supervision']['observed_mask'][index] = 1
        with self.assertRaises(ValueError):
            validate_training_sample(sample, cfg)

    def test_pose_history_uses_shortest_arc_quaternion_interpolation(self):
        start = state(run="rotation", stamp=900_000_000)
        end = state(run="rotation", stamp=1_100_000_000)
        start["orientation_xyzw"] = [0.0, 0.0, 0.0, 1.0]
        end["orientation_xyzw"] = [0.0, 0.0, 1.0, 0.0]
        pose, source_ids = _state_pose_at(
            [start, end], 1_000_000_000, "rotation", "sim:rotation")
        self.assertEqual(source_ids, [start["header"]["sample_id"], end["header"]["sample_id"]])
        self.assertAlmostEqual(pose[0], 0.0, places=6)
        self.assertAlmostEqual(pose[1], -1.0, places=6)
        self.assertAlmostEqual(pose[4], 1.0, places=6)
        self.assertAlmostEqual(pose[5], 0.0, places=6)

    def test_nonzero_scan_requires_complete_ordered_pose_history(self):
        cfg = motion_fixture()
        history = [state(run="motion", stamp=stamp, speed=1)
                   for stamp in (900_000_000, 1_000_000_000, 1_100_000_000)]
        with self.assertRaises(ValueError):
            build_training_sample(history[1], cfg)
        with self.assertRaises(ValueError):
            build_training_sample(history[1], cfg, state_history=history[:2])
        with self.assertRaises(ValueError):
            build_training_sample(history[1], cfg,
                                  state_history=[history[1], history[0], history[2]])
        duplicate_ids = copy.deepcopy(history)
        duplicate_ids[2]["header"]["sample_id"] = duplicate_ids[1]["header"]["sample_id"]
        with self.assertRaises(ValueError):
            build_training_sample(history[1], cfg, state_history=duplicate_ids)
        bad_offsets = copy.deepcopy(cfg)
        bad_offsets["lidar"]["ray_time_offsets_ns"] = [50_000_000, 150_000_000]
        with self.assertRaises(ValueError):
            build_training_sample(history[1], bad_offsets, state_history=history)

    def test_a_later_ray_cannot_erase_a_prior_occupied_voxel(self):
        cfg = fixture()
        cfg["scene"]["obstacles_odom"][0]["size_m"][0] = 0.1
        cfg["scene"]["obstacles_odom"].append({
            "obstacle_id": "far", "center_m": [-0.16, 5.0, 0.2],
            "size_m": [0.5, 0.4, 0.5], "ir_pixel": [2, 1],
        })
        cfg["lidar"]["rays_lidar"].append([0.9995003746877732, 0.0316069770620507, 0.0])
        sample = build_training_sample(state(), cfg)
        self.assertEqual(len(sample["lidar"]["points"]), 2)
        first_hit_voxel = (6 * 8 + 4) * 8 + 4
        self.assertEqual(sample["supervision"]["target"][first_hit_voxel], "occupied")
        self.assertTrue(sample["supervision"]["observed_mask"][first_hit_voxel])

    def test_two_rays_separate_obstacles_and_occlusion(self):
        cfg = multiray_fixture()
        sample = build_training_sample(state(), cfg)
        self.assertTrue(validate_training_sample(sample, cfg))
        self.assertEqual(len(sample["radar"]["points"]), 2)
        self.assertEqual(len(sample["lidar"]["points"]), 2)
        self.assertEqual(sample["infrared"]["image"][6], 0.9)
        self.assertEqual(sample["infrared"]["image"][7], 0.9)
        def label(x, y):
            return (x * 8 + y) * 8 + 4
        self.assertEqual(sample["supervision"]["target"][label(6, 4)], "occupied")
        self.assertEqual(sample["supervision"]["target"][label(6, 5)], "occupied")
        self.assertEqual(sample["supervision"]["target"][label(7, 5)], "unknown")
        self.assertFalse(sample["supervision"]["observed_mask"][label(7, 5)])
        behind = copy.deepcopy(cfg)
        behind["scene"]["obstacles_odom"].append({
            "obstacle_id": "behind", "center_m": [-1.0, 5.0, 0.2],
            "size_m": [0.4, 0.4, 0.4], "ir_pixel": [1, 1],
        })
        hidden = build_training_sample(state(), behind)
        self.assertEqual(len(hidden["lidar"]["points"]), 2)
        self.assertEqual(hidden["supervision"]["target"][label(9, 5)], "unknown")
        self.assertFalse(hidden["supervision"]["observed_mask"][label(9, 5)])

    def test_same_obstacle_radar_ir_and_lidar_supervision(self):
        cfg = fixture()
        sample = build_training_sample(state(), cfg)
        self.assertTrue(validate_training_sample(sample, cfg))
        self.assertEqual(sample["scene_id"], cfg["scene"]["scene_id"])
        self.assertEqual(len(sample["radar"]["points"]), 1)
        self.assertEqual(sample["infrared"]["image"][1 * 5 + 2], 0.9)
        self.assertEqual(sample["lidar"]["header"]["frame_id"], "training_lidar")
        self.assertEqual(sample["radar"]["header"]["source_type"], "fixture")
        self.assertEqual(sample["lidar"]["scan_start"], sample["lidar"]["scan_end"])
        self.assertEqual(len(sample["lidar"]["points"]), 1)
        self.assertNotEqual(cfg["calibration"]["T_body_training_lidar"],
                            cfg["calibration"]["T_body_radar"])
        self.assertNotIn("lidar", sample["radar"])
        self.assertNotIn("lidar", sample["infrared"])

        labels = sample["supervision"]
        def cell(x, y=4, z=4):
            return (x * 8 + y) * 8 + z
        self.assertEqual(labels["target"][cell(5)], "free")
        self.assertTrue(labels["observed_mask"][cell(5)])
        self.assertEqual(labels["target"][cell(6)], "occupied")
        self.assertTrue(labels["observed_mask"][cell(6)])
        self.assertEqual(labels["target"][cell(7)], "unknown")
        self.assertFalse(labels["observed_mask"][cell(7)])
        self.assertEqual(labels["target"][cell(6, 5)], "unknown")

    def test_motion_and_nonidentity_extrinsics_reproject_to_same_world(self):
        cfg = fixture()
        a = build_training_sample(state(), cfg)
        b = build_training_sample(state(stamp=1_100_000_000, speed=1), cfg)
        # Same physical obstacle, first-hit surface in the same odom position.
        for actual, expected in zip(a["lidar"]["first_hit_odom"],
                                    b["lidar"]["first_hit_odom"]):
            self.assertAlmostEqual(actual, expected)
        self.assertNotEqual(a["lidar"]["points"], b["lidar"]["points"])
        self.assertAlmostEqual(a["radar"]["points"][0]["x"] -
                               b["radar"]["points"][0]["x"], 1.1)

    def test_no_echo_is_not_free_and_occluded_second_hit_is_unknown(self):
        cfg = fixture()
        empty = copy.deepcopy(cfg)
        empty["scene"]["obstacles_odom"] = []
        sample = build_training_sample(state(), empty)
        self.assertEqual(sample["lidar"]["points"], [])
        self.assertFalse(any(sample["supervision"]["observed_mask"]))
        self.assertEqual(set(sample["supervision"]["target"]), {"unknown"})
        occluded = copy.deepcopy(cfg)
        occluded["scene"]["obstacles_odom"].append({
            "obstacle_id": "behind", "center_m": [0, 5, 0.2],
            "size_m": [0.5, 0.5, 0.5], "ir_pixel": [2, 1]})
        sample = build_training_sample(state(), occluded)
        self.assertEqual(len(sample["lidar"]["points"]), 1)
        after_hit = (8 * 8 + 4) * 8 + 4
        self.assertFalse(sample["supervision"]["observed_mask"][after_hit])

    def test_boundary_only_contact_does_not_certify_an_echo(self):
        cfg = fixture()
        # In odom, the forward LiDAR ray lies on this box's x=0 boundary.
        cfg["scene"]["obstacles_odom"][0]["center_m"] = [-0.25, 4.0, 0.2]
        sample = build_training_sample(state(), cfg)
        self.assertEqual(sample["lidar"]["points"], [])
        self.assertEqual(set(sample["supervision"]["target"]), {"unknown"})
        self.assertFalse(any(sample["supervision"]["observed_mask"]))

    def test_out_of_fov_range_and_mismatched_identity_fail_closed(self):
        cfg = fixture()
        outside = copy.deepcopy(cfg)
        outside["scene"]["obstacles_odom"][0]["center_m"] = [5, 4, 0.2]
        with self.assertRaises(ValueError):
            build_training_sample(state(), outside)  # configured IR correspondence invalid
        far = copy.deepcopy(cfg)
        far["lidar"]["max_range_m"] = 2.0
        sample = build_training_sample(state(), far)
        self.assertFalse(any(sample["supervision"]["observed_mask"]))
        with self.assertRaises(ValueError):
            build_training_sample(state(), cfg, lidar_timestamp_ns=106_000_000)
        with self.assertRaises(ValueError):
            build_training_sample(state(), cfg, infrared_timestamp_ns=106_000_000)
        with self.assertRaises(ValueError):
            build_training_sample(state(stamp=80_000_000), cfg,
                                  radar_timestamp_ns=100_000_000)
        for key, value in (("scene_id", "other"), ("calibration_id", "other")):
            damaged = build_training_sample(state(), cfg)
            damaged[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_training_sample(damaged, cfg)
        damaged = build_training_sample(state(), cfg)
        damaged["lidar"]["header"]["run_id"] = "other"
        with self.assertRaises(ValueError):
            validate_training_sample(damaged, cfg)
        damaged = build_training_sample(state(), cfg)
        damaged["supervision"]["grid_origin_m"] = [1, -2, -2]
        with self.assertRaises(ValueError):
            validate_training_sample(damaged, cfg)
        invalid_state = state()
        invalid_state["orientation_xyzw"] = [0, 0, 0, 0]
        with self.assertRaises(ValueError):
            build_training_sample(invalid_state, cfg)


if __name__ == "__main__":
    unittest.main()
