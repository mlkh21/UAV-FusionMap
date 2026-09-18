"""ROS 跨话题到达顺序的纯接收门控测试，不启动节点。"""
import copy
import unittest

from ufm_sensors.clock_gate import StateClockGate


def state(ns=10, sample_id=None, terminal=None):
    return {"header": {
        "schema_version": "0.1", "run_id": "run", "clock_id": "sim:run",
        "timestamp": ns, "sample_id": sample_id or "sensors.state:%d" % ns,
        "source_type": "derived", "frame_id": "odom",
        "status": "unavailable" if terminal else "valid",
        "reason": "terminal:" + terminal if terminal else ""},
        "body_frame_id": "base_link", "velocity_frame_id": "base_link",
        "position": [0., 0., 0.], "orientation_xyzw": [0., 0., 0., 1.]}


class ClockGateTest(unittest.TestCase):
    def test_state_before_clock_and_clock_before_state(self):
        gate = StateClockGate("run")
        self.assertEqual(gate.consume_state(state(), 0.), [])
        self.assertEqual(gate.consume_clock(9, .1), [])
        self.assertEqual(gate.consume_clock(10, .2), [state()])
        gate.consume_clock(20, .3)
        self.assertEqual(gate.consume_state(state(20), .4), [state(20)])

    def test_reordered_pending_release_sorted(self):
        gate = StateClockGate("run")
        gate.consume_state(state(30), 0.)
        gate.consume_state(state(10), .01)
        gate.consume_state(state(20), .02)
        self.assertEqual(gate.consume_clock(30, .1), [state(10), state(20), state(30)])
        self.assertEqual(gate.consume_state(state(15), .2), [])
        self.assertEqual(gate.counters["old_state"], 1)

    def test_timeout_at_boundary_even_when_clock_arrives(self):
        gate = StateClockGate("run", pending_timeout_wall_s=.5)
        gate.consume_state(state(), 0.)
        self.assertEqual(gate.consume_clock(10, .5), [])
        self.assertEqual(gate.counters["pending_timeout"], 1)
        self.assertEqual(gate.pending_count, 0)

    def test_poll_timeout_and_overflow_drop_newest(self):
        gate = StateClockGate("run", pending_limit=1)
        gate.consume_state(state(10), 0.)
        self.assertEqual(gate.consume_state(state(20), .1), [])
        self.assertEqual(gate.counters["pending_overflow"], 1)
        self.assertEqual(gate.pending_count, 1)
        self.assertEqual(gate.poll_timeout(.5), [])
        self.assertEqual(gate.pending_count, 0)

    def test_duplicate_and_conflict_before_and_after_release(self):
        gate = StateClockGate("run")
        gate.consume_state(state(), 0.)
        self.assertEqual(gate.consume_state(state(), .01), [])
        conflicting = state()
        conflicting["position"][0] = 1.
        with self.assertRaises(ValueError):
            gate.consume_state(conflicting, .02)
        self.assertEqual(gate.consume_clock(10, .03), [state()])
        self.assertEqual(gate.consume_state(state(), .04), [])
        with self.assertRaises(ValueError):
            gate.consume_state(conflicting, .05)

    def test_terminal_bypasses_watermark_and_clock_clears_and_locks(self):
        gate = StateClockGate("run")
        gate.consume_clock(100, 0.)
        gate.consume_state(state(100), .01)
        gate.consume_state(state(200), .02)
        terminal = state(1, "terminal:a", "reset")
        terminal["position"] = [float("nan")]*3
        terminal["orientation_xyzw"] = [0.]*4
        result = gate.consume_state(terminal, .03)
        self.assertEqual(result[0]["header"], terminal["header"])
        self.assertTrue(gate.locked)
        self.assertEqual(gate.pending_count, 0)
        self.assertEqual(gate.consume_clock(500, .04), [])
        self.assertEqual(gate.consume_state(state(500), .05), [])
        repeated = copy.deepcopy(terminal)
        repeated["position"] = [float("nan")]*3
        self.assertEqual(gate.consume_state(repeated, .06), [])
        self.assertEqual(gate.consume_state(state(2, "terminal:b", "timeout"), .07), [])
        self.assertEqual(gate.terminal_state["header"]["reason"], "terminal:reset")

    def test_terminal_before_any_clock(self):
        gate = StateClockGate("run")
        self.assertEqual(gate.consume_state(state(0, "terminal:a", "startup"), 0.),
                         [state(0, "terminal:a", "startup")])

    def test_wrong_run_domain_and_header_rejected_even_terminal(self):
        for key, value in (("run_id", "other"), ("clock_id", "sim:other"),
                           ("sample_id", ""), ("timestamp", -1),
                           ("timestamp", True), ("schema_version", "unknown")):
            gate = StateClockGate("run")
            invalid = state(0, "terminal:a", "reset")
            invalid["header"][key] = value
            with self.assertRaises(ValueError):
                gate.consume_state(invalid, 0.)
            self.assertFalse(gate.locked)

    def test_clock_regression_locks_before_raising(self):
        gate = StateClockGate("run")
        gate.consume_clock(20, 0.)
        gate.consume_state(state(30), .01)
        with self.assertRaises(ValueError):
            gate.consume_clock(10, .02)
        self.assertTrue(gate.locked)
        self.assertEqual(gate.pending_count, 0)
        self.assertEqual(gate.consume_state(state(40), .03), [])
        self.assertEqual(len(gate.consume_state(state(10, "terminal:a", "regression"), .04)), 1)

    def test_equal_clock_does_not_advance_and_degraded_is_preserved(self):
        gate = StateClockGate("run")
        gate.consume_clock(10, 0.)
        self.assertEqual(gate.consume_clock(10, .01), [])
        degraded = state(10)
        degraded["header"].update(status="degraded", reason="source_degraded")
        self.assertEqual(gate.consume_state(degraded, .02), [degraded])
        self.assertEqual(gate.counters["duplicate_clock"], 1)

    def test_invalid_config_clock_and_monotonic(self):
        for kwargs in ({"run_id": ""}, {"run_id": "run", "pending_limit": 0},
                       {"run_id": "run", "pending_timeout_wall_s": float("inf")}):
            with self.assertRaises(ValueError):
                StateClockGate(**kwargs)
        gate = StateClockGate("run")
        for ns in (-1, True, 2**63, 1.5):
            with self.assertRaises(ValueError):
                gate.consume_clock(ns, 0.)
        gate.poll_timeout(1.)
        with self.assertRaises(ValueError):
            gate.poll_timeout(.9)

    def test_inputs_and_outputs_are_detached(self):
        gate = StateClockGate("run")
        source = state()
        gate.consume_state(source, 0.)
        source["position"][0] = 99
        result = gate.consume_clock(10, .1)
        self.assertEqual(result, [state()])
        result[0]["position"][0] = 100
        self.assertEqual(gate.consume_state(state(), .2), [])


if __name__ == "__main__":
    unittest.main()
