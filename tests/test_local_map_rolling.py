"""Rolling Local Map contracts using only public occupancy observations."""
import copy
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for relative in ("mapping", "perception", "sensors", "ros_ws"):
    sys.path.insert(0, str(ROOT / relative))

from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.placeholder import placeholder_infer
from test_perf01a_contract import valid_bundle


def observed(stamp, body=(0.0, 0.0, 0.0), world_point=(2.25, .25, .25),
             yaw=0.0, visible=True):
    cosine, sine = math.cos(yaw), math.sin(yaw)
    dx, dy = world_point[0] - body[0], world_point[1] - body[1]
    point = (cosine * dx + sine * dy, -sine * dx + cosine * dy,
             world_point[2] - body[2])
    bundle = valid_bundle(run_id="rolling", radar_timestamp=stamp, point=point)
    bundle["header"]["sample_id"] += ":%d" % stamp
    transform = [cosine, -sine, 0., body[0],
                 sine, cosine, 0., body[1],
                 0., 0., 1., body[2],
                 0., 0., 0., 1.]
    bundle["context"]["T_mapping_body"] = list(transform)
    bundle["context"]["T_mapping_source"] = list(transform)
    if not visible:
        bundle["radar"]["points"] = []
    return placeholder_infer(bundle, rolling_grid=True)


class RollingLocalMapTest(unittest.TestCase):
    def new_map(self, **kwargs):
        return SparseLocalMap(rolling_enabled=True, free_threshold=.3,
                              occupied_threshold=.7, **kwargs)

    def query(self, local_map, point=(2.25, .25, .25), stamp=100, **kwargs):
        return local_map.query(map_id="perf01a-local", frame_id="odom", run_id="rolling",
                               clock_id="sim:rolling", query_timestamp=stamp,
                               point=point, max_age_ns=100, **kwargs)

    def test_positive_and_negative_subcell_shifts_keep_world_cell(self):
        for shift, expected_origin, expected_index in ((.24, -16., [36, 16, 8]),
                                                       (.26, -15.5, [35, 16, 8]),
                                                       (-.26, -16.5, [37, 16, 8])):
            with self.subTest(shift=shift):
                local_map = self.new_map()
                self.assertTrue(local_map.update(observed(100)))
                self.assertTrue(local_map.update(observed(110, body=(shift, 0., 0.), visible=False)))
                snapshot = local_map.snapshot()
                self.assertEqual(snapshot["origin"][0], expected_origin)
                self.assertEqual(snapshot["revision"], 2)
                self.assertEqual(self.query(local_map, stamp=110)["index"], expected_index)
                self.assertEqual(self.query(local_map, stamp=110)["last_observed_timestamp"], 100)
                self.assertEqual(snapshot["cells"][0]["index"], expected_index)

    def test_turn_keeps_odom_window_axis_aligned_and_updates_same_world_cell(self):
        local_map = self.new_map()
        local_map.update(observed(100))
        turn = observed(110, body=(.5, 0., 0.), yaw=math.pi / 2)
        self.assertEqual(turn["header"]["frame_id"], "odom")
        self.assertEqual(turn["voxels"][0]["index"], [35, 16, 8])
        local_map.update(turn)
        self.assertEqual(self.query(local_map, stamp=110)["status"], "occupied")
        self.assertEqual(self.query(local_map, stamp=110)["last_observed_timestamp"], 110)

    def test_partially_overlapping_observation_grid_maps_world_indices(self):
        local_map = self.new_map()
        first = observed(100)
        local_map.update(first)
        shifted = observed(110, body=(.5, 0., 0.))
        shifted["origin"][0] += .5
        shifted["voxels"][0]["index"][0] -= 1
        local_map.update(shifted)
        self.assertEqual(self.query(local_map, stamp=110)["index"], [35, 16, 8])
        self.assertEqual(self.query(local_map, stamp=110)["last_observed_timestamp"], 110)

    def test_outside_cells_evict_and_entering_cells_remain_unknown(self):
        local_map = self.new_map()
        local_map.update(observed(100, world_point=(-15.75, .25, .25)))
        local_map.update(observed(110, body=(.5, 0., 0.), visible=False))
        self.assertEqual(local_map.snapshot()["cells"], [])
        self.assertEqual(self.query(local_map, point=(-15.75, .25, .25), stamp=110)["reason"],
                         "outside_coverage")
        entering = self.query(local_map, point=(16.25, .25, .25), stamp=110)
        self.assertEqual((entering["status"], entering["reason"], entering["observed"]),
                         ("unknown", "no_observation", False))

    def test_large_displacement_clears_even_with_empty_valid_observation(self):
        local_map = self.new_map()
        local_map.update(observed(100))
        local_map.update(observed(110, body=(40., 0., 0.), visible=False))
        snapshot = local_map.snapshot()
        self.assertEqual(snapshot["origin"][0], 24.)
        self.assertEqual(snapshot["coverage"][:2], [24., 56.])
        self.assertEqual(snapshot["cells"], [])
        self.assertEqual(self.query(local_map, point=(40.25, .25, .25), stamp=110)["status"],
                         "unknown")

    def test_boundaries_and_unequal_half_cell_ties(self):
        local_map = self.new_map()
        local_map.update(observed(100))
        local_map.update(observed(110, body=(.25, -.25, 0.), visible=False))
        snapshot = local_map.snapshot()
        self.assertEqual(snapshot["origin"], [-15.5, -8., -4.])
        self.assertEqual(self.query(local_map, point=(-15.5, -8., -4.), stamp=110)["reason"],
                         "no_observation")
        self.assertEqual(self.query(local_map, point=(16.5, -8., -4.), stamp=110)["reason"],
                         "outside_coverage")

    def test_rejected_observations_cannot_shift_or_partially_modify_window(self):
        local_map = self.new_map()
        local_map.update(observed(100))
        before = local_map.snapshot()
        for bad in (lambda row: row["origin"].__setitem__(0, row["origin"][0] + .1),
                    lambda row: row["context"].__setitem__("T_mapping_body_status", "unavailable"),
                    lambda row: row["context"]["T_mapping_body"].__setitem__(12, 1.),
                    lambda row: row["context"]["T_mapping_body"].__setitem__(0, -1.),
                    lambda row: row["context"]["T_mapping_body"].__setitem__(3, 1e308),
                    lambda row: row["voxels"].append(dict(index=[999, 0, 0], probability=.9,
                                                           observed=True))):
            row = observed(110, body=(2., 0., 0.))
            bad(row)
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                local_map.update(row)
            self.assertEqual(local_map.snapshot(), before)

    def test_unavailable_gap_stales_without_motion_then_recovers(self):
        local_map = self.new_map()
        local_map.update(observed(100))
        gap = observed(160, body=(1., 0., 0.), visible=False)
        gap["header"].update(status="unavailable", reason="fixture_gap")
        self.assertFalse(local_map.update(gap))
        self.assertEqual(local_map.snapshot()["origin"][0], -16.)
        self.assertEqual(self.query(local_map, stamp=200)["status"], "occupied")
        self.assertEqual(self.query(local_map, stamp=201)["status"], "stale")
        local_map.update(observed(210, body=(1., 0., 0.)))
        self.assertEqual(self.query(local_map, stamp=210)["last_observed_timestamp"], 210)

    def test_duplicate_old_run_and_clock_rejected_without_mutation(self):
        local_map = self.new_map()
        first = observed(100)
        local_map.update(first)
        self.assertFalse(local_map.update(copy.deepcopy(first)))
        before = local_map.snapshot()
        for mutation in (lambda row: row["header"].__setitem__("run_id", "other"),
                         lambda row: row["header"].__setitem__("clock_id", "other"),
                         lambda row: row["header"].__setitem__("timestamp", 99)):
            row = observed(110, body=(.5, 0., 0.))
            mutation(row)
            with self.assertRaises(ValueError):
                local_map.update(row)
            self.assertEqual(local_map.snapshot(), before)

    def test_capacity_limit_bounded_after_many_shifts(self):
        local_map = self.new_map(max_active_cells=2)
        for stamp in range(100, 300):
            local_map.update(observed(stamp, body=(stamp * .5, 0., 0.),
                                      world_point=(stamp * .5 + 1.25, .25, .25)))
            snapshot = local_map.snapshot()
            self.assertLessEqual(len(snapshot["cells"]), 2)
            self.assertEqual(snapshot["coverage"][0], snapshot["origin"][0])


if __name__ == "__main__":
    unittest.main()
