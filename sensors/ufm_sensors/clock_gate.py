"""接收端 /clock 覆盖门控；不生成时钟、不依赖 ROS 或 simulation 实现。"""
import copy
import math
from collections import Counter
from numbers import Real


def _same(a, b):
    # 终止消息允许 NaN 槽位；相同 NaN 占位重传仍是同一身份。
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    return a == b


def _timestamp(ns):
    if type(ns) is not int or not 0 <= ns < 2**63:
        raise ValueError("invalid_timestamp_ns")


class StateClockGate:
    """每个 run 独立实例，方法返回可发布状态列表，counters 提供诊断计数。

    pending 超限丢弃新到状态；超时阈值包含等号。身份账本覆盖整个有限 run，
    保证已丢弃或已发布身份重传不复活；新 run 必须创建新实例。
    """
    def __init__(self, run_id, pending_limit=100, pending_timeout_wall_s=.5):
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id_required")
        if type(pending_limit) is not int or pending_limit < 1:
            raise ValueError("invalid_pending_limit")
        if (isinstance(pending_timeout_wall_s, bool)
                or not isinstance(pending_timeout_wall_s, Real)
                or not math.isfinite(pending_timeout_wall_s) or pending_timeout_wall_s <= 0):
            raise ValueError("invalid_pending_timeout")
        self.run_id = run_id
        self.clock_id = "sim:" + run_id
        self.pending_limit = pending_limit
        self.pending_timeout_wall_s = pending_timeout_wall_s
        self.last_clock_ns = None
        self.locked = False
        self.terminal_state = None
        self.counters = Counter()
        self._wall = self._published_ns = None
        self._pending = []
        self._seen = {}

    @property
    def pending_count(self):
        return len(self._pending)

    def _touch(self, now):
        if (isinstance(now, bool) or not isinstance(now, Real) or not math.isfinite(now)
                or (self._wall is not None and now < self._wall)):
            raise ValueError("invalid_receive_monotonic")
        self._wall = now

    def _header(self, state):
        if not isinstance(state, dict) or not isinstance(state.get("header"), dict):
            raise ValueError("state_header_required")
        h = state["header"]
        if h.get("run_id") != self.run_id or h.get("clock_id") != self.clock_id:
            raise ValueError("run_or_clock_domain_mismatch")
        if not isinstance(h.get("sample_id"), str) or not h["sample_id"].strip():
            raise ValueError("sample_id_required")
        _timestamp(h.get("timestamp"))
        if h.get("schema_version") != "0.1" or h.get("source_type") != "derived":
            raise ValueError("unsupported_state_schema_or_source")
        if h.get("status") not in ("valid", "degraded", "unavailable"):
            raise ValueError("invalid_state_status")
        if not isinstance(h.get("reason"), str) or (h["status"] != "valid" and not h["reason"].strip()):
            raise ValueError("invalid_state_reason")
        return h

    def _remember(self, state):
        key = state["header"]["sample_id"]
        if key in self._seen:
            if not _same(self._seen[key], state):
                self.counters["sample_identity_conflict"] += 1
                raise ValueError("sample_identity_conflict")
            self.counters["duplicate_state"] += 1
            return False
        self._seen[key] = copy.deepcopy(state)
        return True

    def _release(self):
        if self.locked or self.last_clock_ns is None:
            return []
        ready = sorted((e for e in self._pending if e[0] <= self.last_clock_ns), key=lambda e: e[0])
        self._pending = [e for e in self._pending if e[0] > self.last_clock_ns]
        output = []
        for ns, _, state in ready:
            if self._published_ns is not None and ns <= self._published_ns:
                self.counters["old_state"] += 1
                continue
            self._published_ns = ns
            self.counters["published_states"] += 1
            output.append(copy.deepcopy(state))
        return output

    def poll_timeout(self, now):
        """丢弃等待过期状态；不补发状态或推进 /clock，返回空列表。"""
        self._touch(now)
        keep = []
        for entry in self._pending:
            if now - entry[1] >= self.pending_timeout_wall_s:
                self.counters["pending_timeout"] += 1
            else:
                keep.append(entry)
        self._pending = keep
        return []

    def consume_state(self, state, receive_monotonic):
        h = self._header(state)
        self._touch(receive_monotonic)
        terminal = h["status"] == "unavailable" and h["reason"].startswith("terminal:")
        if terminal:
            if not self._remember(state):
                return []
            if self.terminal_state is not None:
                self.counters["subsequent_terminal"] += 1
                return []
            self.counters["terminal_cleared_pending"] += len(self._pending)
            self._pending.clear()
            self.locked = True
            self.terminal_state = copy.deepcopy(state)
            self.counters["published_terminal"] += 1
            return [copy.deepcopy(state)]
        self.poll_timeout(receive_monotonic)
        if self.locked:
            self.counters["locked_state"] += 1
            return []
        if (h["status"] == "unavailable" or h.get("frame_id") != "odom"
                or state.get("body_frame_id") != "base_link"
                or state.get("velocity_frame_id") != "base_link"):
            raise ValueError("adapted_geometric_state_required")
        if not self._remember(state):
            return []
        ns = h["timestamp"]
        if self._published_ns is not None and ns <= self._published_ns:
            self.counters["old_state"] += 1
            return []
        if len(self._pending) >= self.pending_limit:
            self.counters["pending_overflow"] += 1
            return []
        self._pending.append((ns, receive_monotonic, copy.deepcopy(state)))
        self.counters["accepted_states"] += 1
        return self._release()

    def consume_clock(self, timestamp_ns, receive_monotonic):
        _timestamp(timestamp_ns)
        self.poll_timeout(receive_monotonic)
        if self.locked:
            self.counters["locked_clock"] += 1
            return []
        if self.last_clock_ns is not None and timestamp_ns < self.last_clock_ns:
            self.locked = True
            self._pending.clear()
            self.counters["clock_regression"] += 1
            raise ValueError("clock_regression")
        if timestamp_ns == self.last_clock_ns:
            self.counters["duplicate_clock"] += 1
        else:
            self.last_clock_ns = timestamp_ns
            self.counters["accepted_clock"] += 1
        return self._release()
