"""PERF-01-A odom稀疏地图；滚动窗口仅在明确启用时生效。

只融合OccupancyObservation中的observed体素；未观测、过期和不可用区域不被改写成free。
"""
import copy
import math


class SparseLocalMap:
    def __init__(self, map_id="perf01a-local", resolution=(0.5, 0.5, 0.5),
                 shape=(64, 32, 16), origin=(-16.0, -8.0, -4.0),
                 staleness_limit_ns=100_000_000, max_active_cells=10000,
                 free_threshold=None, occupied_threshold=None, rolling_enabled=False):
        if len(resolution) != 3 or len(shape) != 3 or len(origin) != 3:
            raise ValueError("map geometry must have three values")
        if any(not math.isfinite(value) for value in tuple(resolution) + tuple(origin)):
            raise ValueError("map geometry must be finite")
        if any(float(value) <= 0 for value in resolution):
            raise ValueError("resolution must be positive")
        if any(int(value) != value or int(value) <= 0 for value in shape):
            raise ValueError("shape must be positive integers")
        if max_active_cells < 1:
            raise ValueError("max_active_cells must be positive")
        if (free_threshold is None) != (occupied_threshold is None):
            raise ValueError("free and occupied thresholds must be configured together")
        if free_threshold is not None:
            free_threshold, occupied_threshold = float(free_threshold), float(occupied_threshold)
            if (not math.isfinite(free_threshold) or not math.isfinite(occupied_threshold) or
                    not 0 <= free_threshold < occupied_threshold <= 1):
                raise ValueError("occupancy thresholds must satisfy 0 <= free < occupied <= 1")
        self.map_id = map_id
        self.resolution = tuple(float(value) for value in resolution)
        self.shape = tuple(int(value) for value in shape)
        self.origin = tuple(float(value) for value in origin)
        self._anchor_origin = self.origin
        self.rolling_enabled = bool(rolling_enabled)
        self.staleness_limit_ns = int(staleness_limit_ns)
        self.max_active_cells = int(max_active_cells)
        self.free_threshold = free_threshold
        self.occupied_threshold = occupied_threshold
        self._cells = {}
        self._last_observation = None
        self._source_types = set()
        self._revision = 0
        self._latest_timestamp = None
        self._run_id = None
        self._clock_id = None

    @property
    def cells(self):
        return copy.deepcopy(self._cells)

    def update(self, observation):
        header = observation["header"]
        if self._run_id is not None and (header["run_id"], header["clock_id"]) != (
                self._run_id, self._clock_id):
            raise ValueError("map run or clock domain changed")
        if self._last_observation is not None:
            previous = self._last_observation["header"]
            if header["sample_id"] == previous["sample_id"]:
                if self._last_observation != observation:
                    raise ValueError("occupancy sample identity conflict")
                return False
            # Strict event-time ordering bounds dedup state to the most recent input.
            if header["timestamp"] <= previous["timestamp"]:
                raise ValueError("occupancy timestamp must increase")
        if header["frame_id"] != "odom":
            raise ValueError("occupancy frame must be odom")
        if (tuple(observation["resolution"]) != self.resolution or
                tuple(observation["shape"]) != self.shape or
                (not self.rolling_enabled and tuple(observation["origin"]) != self.origin)):
            raise ValueError("occupancy geometry differs from map")
        observation_origin = tuple(observation["origin"])
        if self.rolling_enabled:
            if len(observation_origin) != 3 or any(
                    not isinstance(value, (int, float)) or not math.isfinite(value)
                    for value in observation_origin):
                raise ValueError("occupancy origin must be finite XYZ")
            relative = tuple((observation_origin[axis] - self._anchor_origin[axis]) /
                             self.resolution[axis] for axis in range(3))
            if any(not math.isfinite(value) for value in relative):
                raise ValueError("occupancy origin exceeds map lattice")
            offset = tuple(round(value) for value in relative)
            if any(abs(relative[axis] - offset[axis]) > 1e-8 for axis in range(3)):
                raise ValueError("occupancy origin is not aligned to map lattice")
        context = observation["context"]
        if (context["source_frame_id"] != header["frame_id"] or
                context["mapping_frame_id"] != "odom" or
                context["reference_timestamp"] != header["timestamp"] or
                context["clock_id"] != header["clock_id"]):
            raise ValueError("occupancy context frame or time mismatch")
        pending = {}
        new_origin = self.origin
        if header["status"] == "valid":
            if (context["T_mapping_source_status"] != "available" or
                    context["T_mapping_body_status"] != "available"):
                raise ValueError("occupancy transform unavailable")
            identity = [1.0 if row == col else 0.0 for row in range(4) for col in range(4)]
            transform = context["T_mapping_source"]
            if len(transform) != 16 or any(not math.isfinite(a) or abs(a-b) > 1e-9
                                           for a, b in zip(transform, identity)):
                raise ValueError("odom occupancy requires identity source transform")
            body = context["T_mapping_body"]
            if len(body) != 16 or any(not math.isfinite(value) for value in body):
                raise ValueError("body transform must be finite")
            if any(abs(a-b) > 1e-9 for a, b in zip(body[12:], (0, 0, 0, 1))):
                raise ValueError("body transform must be homogeneous")
            if self.rolling_enabled:
                for row in range(3):
                    for col in range(3):
                        dot = sum(body[4*row+k] * body[4*col+k] for k in range(3))
                        if abs(dot - (1.0 if row == col else 0.0)) > 1e-6:
                            raise ValueError("body transform rotation must be orthonormal")
                determinant = (body[0]*(body[5]*body[10] - body[6]*body[9]) -
                               body[1]*(body[4]*body[10] - body[6]*body[8]) +
                               body[2]*(body[4]*body[9] - body[5]*body[8]))
                if abs(determinant - 1) > 1e-6:
                    raise ValueError("body transform must be a proper rotation")
                relative_body = tuple((body[4*axis+3] - self._anchor_origin[axis] -
                                       self.shape[axis]*self.resolution[axis]/2) /
                                      self.resolution[axis] for axis in range(3))
                if any(not math.isfinite(value) for value in relative_body):
                    raise ValueError("body position exceeds map lattice")
                shift = tuple(math.floor(value + .5) for value in relative_body)
                new_origin = tuple(self._anchor_origin[axis] + shift[axis]*self.resolution[axis]
                                   for axis in range(3))
                if any(not math.isfinite(value) for value in new_origin):
                    raise ValueError("rolling map origin is not finite")
        elif header["status"] not in ("degraded", "unavailable") or not header["reason"]:
            raise ValueError("invalid occupancy status")
        indices = set()
        for voxel in observation["voxels"]:
            index = tuple(voxel["index"])
            if (len(index) != 3 or any(type(value) is not int for value in index) or
                    any(index[axis] < 0 or index[axis] >= observation["shape"][axis]
                                      for axis in range(3))):
                raise ValueError("occupancy index outside map")
            if index in indices:
                raise ValueError("duplicate occupancy index")
            indices.add(index)
            probability = float(voxel["probability"])
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("invalid occupancy probability")
            if not voxel.get("observed", False) or header["status"] != "valid":
                continue
            if self.rolling_enabled:
                index = tuple(index[axis] + offset[axis] -
                              round((new_origin[axis] - self._anchor_origin[axis]) /
                                    self.resolution[axis]) for axis in range(3))
                if any(index[axis] < 0 or index[axis] >= self.shape[axis]
                       for axis in range(3)):
                    continue
            pending[index] = dict(index=list(index), probability=probability,
                                      observed=True, last_observed_timestamp=header["timestamp"],
                                      confidence=voxel.get("confidence"),
                                      uncertainty=copy.deepcopy(voxel.get("uncertainty")))
        if header["status"] == "valid" and self.rolling_enabled and new_origin != self.origin:
            previous_shift = tuple(round((new_origin[axis] - self.origin[axis]) /
                                         self.resolution[axis]) for axis in range(3))
            moved = {}
            for index, cell in self._cells.items():
                shifted = tuple(index[axis] - previous_shift[axis] for axis in range(3))
                if all(0 <= shifted[axis] < self.shape[axis] for axis in range(3)):
                    moved_cell = dict(cell, index=list(shifted))
                    moved[shifted] = moved_cell
        else:
            moved = self._cells
        self._run_id, self._clock_id = header["run_id"], header["clock_id"]
        self._last_observation = copy.deepcopy(observation)
        if header["status"] != "valid":
            return False
        self.origin = new_origin
        self._cells = dict(moved)
        self._cells.update(pending)
        self._source_types.add(header["source_type"])
        self._latest_timestamp = header["timestamp"]
        self._revision += 1
        self._roll()
        return True

    def _roll(self):
        if len(self._cells) <= self.max_active_cells:
            return
        keep = sorted(self._cells.items(), key=lambda item: item[1]["last_observed_timestamp"],
                      reverse=True)[:self.max_active_cells]
        self._cells = dict(keep)

    def snapshot(self, publish_timestamp=None):
        status = "valid" if self._latest_timestamp is not None else "unavailable"
        reason = "" if status == "valid" else "no_observation"
        timestamp = self._latest_timestamp or 0
        return dict(header=dict(schema_version="0.1", timestamp=timestamp,
                                clock_id=self._clock_id or "", run_id=self._run_id or "",
                                sample_id="mapping.snapshot:%s:%d" % (self.map_id, self._revision),
                                frame_id="odom", source_type="derived", status=status,
                                reason=reason), map_id=self.map_id, revision=self._revision,
                    cells=[copy.deepcopy(value) for value in self._cells.values()],
                    resolution=list(self.resolution), shape=list(self.shape), origin=list(self.origin),
                    coverage=[self.origin[0], self.origin[0] + self.shape[0] * self.resolution[0],
                              self.origin[1], self.origin[1] + self.shape[1] * self.resolution[1],
                              self.origin[2], self.origin[2] + self.shape[2] * self.resolution[2]],
                    source_types=sorted(self._source_types))

    def stale_cells(self, query_timestamp):
        return [index for index, cell in self._cells.items()
                if query_timestamp - cell["last_observed_timestamp"] > self.staleness_limit_ns]

    def query(self, map_id, frame_id, run_id, clock_id, query_timestamp, point,
              max_age_ns):
        if type(query_timestamp) is not int or query_timestamp < 0:
            raise ValueError("query timestamp must be a non-negative integer")
        if type(max_age_ns) is not int or max_age_ns < 0:
            raise ValueError("max age must be a non-negative integer")
        try:
            point = tuple(float(value) for value in point)
        except (TypeError, ValueError):
            raise ValueError("query point must contain three finite coordinates")
        if len(point) != 3 or any(not math.isfinite(value) for value in point):
            raise ValueError("query point must contain three finite coordinates")
        if not all(isinstance(value, str) and value for value in
                   (map_id, frame_id, run_id, clock_id)):
            raise ValueError("query identity fields must be non-empty strings")

        result = dict(map_id=self.map_id, revision=self._revision, run_id=run_id,
                      clock_id=clock_id, frame_id=frame_id,
                      query_timestamp=query_timestamp, point=list(point), index=None,
                      status="unavailable", reason="map_unavailable", probability=None,
                      confidence=None, uncertainty=None, observed=False,
                      last_observed_timestamp=None)
        if self._run_id is None or self._latest_timestamp is None:
            return result
        if map_id != self.map_id:
            result["reason"] = "map_id_mismatch"
            return result
        if frame_id != "odom":
            result["reason"] = "frame_mismatch"
            return result
        if (run_id, clock_id) != (self._run_id, self._clock_id):
            result["reason"] = "run_or_clock_mismatch"
            return result
        if query_timestamp < self._latest_timestamp:
            result["reason"] = "query_before_latest_map_time"
            return result

        if any(not self.origin[axis] <= point[axis] <
               self.origin[axis] + self.shape[axis] * self.resolution[axis]
               for axis in range(3)):
            result.update(status="unknown", reason="outside_coverage")
            return result
        index = tuple(math.floor((point[axis] - self.origin[axis]) /
                                 self.resolution[axis]) for axis in range(3))
        if any(index[axis] < 0 or index[axis] >= self.shape[axis] for axis in range(3)):
            result.update(status="unknown", reason="outside_coverage")
            return result
        result["index"] = list(index)
        cell = self._cells.get(index)
        if cell is None:
            result.update(status="unknown", reason="no_observation")
            return result

        result.update(probability=cell["probability"], confidence=cell["confidence"],
                      uncertainty=copy.deepcopy(cell["uncertainty"]), observed=True,
                      last_observed_timestamp=cell["last_observed_timestamp"])
        age_ns = query_timestamp - cell["last_observed_timestamp"]
        if age_ns > max_age_ns:
            result.update(status="stale", reason="max_age_exceeded")
        elif self.free_threshold is None:
            result.update(status="unknown", reason="classification_thresholds_unconfigured")
        elif cell["probability"] >= self.occupied_threshold:
            result.update(status="occupied", reason="")
        elif cell["probability"] <= self.free_threshold:
            result.update(status="free", reason="")
        else:
            result.update(status="unknown", reason="between_thresholds")
        return result
