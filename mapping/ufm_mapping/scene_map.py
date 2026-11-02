"""Opt-in M4 synthetic Scene view; local estimates are owned, never fused a second time."""
from collections import OrderedDict
import copy
from dataclasses import dataclass, field
from fractions import Fraction
import math

from .m3_contract import validate_interval_quality
from .m4_contract import validate_fixture_observation, validate_registration_time, validate_spec
from .rolling_interval_probability_map import RollingIntervalProbabilityMap


@dataclass
class _State:
    local: RollingIntervalProbabilityMap
    active: dict = field(default_factory=dict)
    sealed: OrderedDict = field(default_factory=OrderedDict)
    cells: dict = field(default_factory=dict)
    sequence: int = 0
    revision: int = 0
    structure_timestamp: int = -1


class SceneMap:
    """One run, fixed registered Scene lattice, bounded FIFO of sealed local views.

    Methods are synchronous; a ROS wrapper must serialize query/update as it does
    for Local Map. A staged state is published by one reference assignment.
    """
    def __init__(self, spec, run_id, clock_id):
        validate_spec(spec)
        validate_registration_time(spec, spec['registration']['valid_from_ns'], run_id, clock_id)
        self._spec = copy.deepcopy(spec)
        self._run_id, self._clock_id = run_id, clock_id
        self._state = _State(RollingIntervalProbabilityMap(spec['local_map'], run_id, clock_id))

    def _scene_cells(self, local_snapshot):
        scene = self._spec['scene']
        translation = [self._spec['registration']['T_map_odom'][i] for i in (3, 7, 11)]
        offsets = [(Fraction(str(o)) + Fraction(str(t)) - Fraction(str(s))) / Fraction(str(r))
                   for o, t, s, r in zip(local_snapshot['origin'], translation,
                                         scene['origin'], scene['resolution'])]
        if any(value.denominator != 1 for value in offsets):
            raise ValueError('M4 local snapshot not aligned to Scene lattice')
        result = {}
        for cell in local_snapshot['cells']:
            index = tuple(cell['index'][axis] + int(offsets[axis]) for axis in range(3))
            if any(not 0 <= index[axis] < scene['shape'][axis] for axis in range(3)):
                raise ValueError('M4 local cell outside Scene envelope')
            if index in result:
                raise ValueError('M4 duplicate Scene cell')
            result[index] = dict(copy.deepcopy(cell), index=list(index))
        return result

    def _prepare_scene(self, staged, before, after):
        """Construct the complete new ownership directory in the transaction copy."""
        active = self._scene_cells(after)
        sealed_owners = {index: key for key, group in staged.sealed.items() for index in group['cells']}
        for index, cell in active.items():
            owner = sealed_owners.get(index)
            if owner is None:
                continue
            previous = staged.sealed[owner]['cells'][index]
            stamp, old_stamp = cell['last_observed_timestamp'], previous['last_observed_timestamp']
            if stamp < old_stamp or stamp == old_stamp and cell != previous:
                raise ValueError('M4 conflicting or older Scene ownership version')
            del staged.sealed[owner]['cells'][index]
        staged.sealed = OrderedDict((key, group) for key, group in staged.sealed.items() if group['cells'])
        if before['origin'] != after['origin']:
            remaining = {index: cell for index, cell in staged.active.items() if index not in active}
            if remaining:
                key = staged.sequence
                staged.sequence += 1
                staged.sealed[key] = dict(origin=list(before['origin']), cells=remaining)
        while len(staged.sealed) > self._spec['max_sealed_submaps']:
            staged.sealed.popitem(last=False)
        staged.active = active
        # The index references the owned payloads; it does not keep older copies.
        staged.cells = dict(active)
        for group in staged.sealed.values():
            for index, cell in group['cells'].items():
                if index in staged.cells:
                    raise ValueError('M4 Scene cell has multiple owners')
                staged.cells[index] = cell
        self._validate_scene(staged)

    def _validate_scene(self, staged):
        limit = self._spec['local_map']['arithmetic']['max_active_cells']
        if len(staged.active) > limit or any(len(g['cells']) > limit for g in staged.sealed.values()):
            raise ValueError('M4 submap exceeds configured capacity')
        for cell in staged.cells.values():
            if cell['observed'] is not True or cell['confidence'] is not None:
                raise ValueError('M4 requires observed M3 cell estimates')
            validate_interval_quality(cell['probability'], cell['uncertainty'],
                                      self._spec['local_map'], output=True)

    def update(self, observation):
        validate_fixture_observation(observation, self._spec)
        # Include M3 identity/watermark and all Scene ownership in the same transaction.
        staged = copy.deepcopy(self._state)
        before = staged.local.snapshot()
        changed = staged.local.update(observation)
        if changed:
            after = staged.local.snapshot()
            self._prepare_scene(staged, before, after)
            staged.revision += 1
            staged.structure_timestamp = observation['header']['timestamp']
        self._state = staged
        return changed

    def snapshot(self, publish_timestamp=None):
        state = self._state
        local = state.local.snapshot()
        scene = self._spec['scene']
        header = dict(local['header'], frame_id='map',
            sample_id='mapping.snapshot:%s:%d' % (scene['map_id'], state.revision))
        return dict(header=header, map_id=scene['map_id'], revision=state.revision,
            resolution=list(scene['resolution']), shape=list(scene['shape']), origin=list(scene['origin']),
            coverage=[scene['origin'][axis] + side * scene['shape'][axis] * scene['resolution'][axis]
                      for axis in range(3) for side in (0, 1)],
            cells=[copy.deepcopy(state.cells[index]) for index in sorted(state.cells)],
            source_types=list(local['source_types']))

    def query(self, map_id, frame_id, run_id, clock_id, query_timestamp, point, max_age_ns):
        for value in (query_timestamp, max_age_ns):
            if type(value) is not int or not 0 <= value < 2**63:
                raise ValueError('M4 query times must be nonnegative int64 nanoseconds')
        if any(not isinstance(v, str) or not v.strip() for v in (map_id, frame_id, run_id, clock_id)):
            raise ValueError('M4 query requires explicit identity')
        if not isinstance(point, (list, tuple)) or len(point) != 3 or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in point):
            raise ValueError('M4 query point must be finite XYZ')
        state, scene = self._state, self._spec['scene']
        result = dict(map_id=scene['map_id'], revision=state.revision, frame_id=frame_id,
            run_id=run_id, clock_id=clock_id, query_timestamp=query_timestamp, point=list(point),
            index=None, status='unavailable', reason='map_unavailable', probability=None,
            confidence=None, uncertainty=None, observed=False, last_observed_timestamp=None)
        if map_id != scene['map_id']:
            result['reason'] = 'map_id_mismatch'
        elif frame_id != 'map':
            result['reason'] = 'frame_mismatch'
        elif (run_id, clock_id) != (self._run_id, self._clock_id):
            result['reason'] = 'run_or_clock_mismatch'
        else:
            try:
                validate_registration_time(self._spec, query_timestamp, run_id, clock_id)
            except ValueError:
                result['reason'] = 'registration_unavailable'
                return result
            snapshot = state.local.snapshot()
            if snapshot['header']['status'] == 'unavailable':
                return result
            if query_timestamp < max(snapshot['header']['timestamp'], state.structure_timestamp):
                result['reason'] = 'query_before_latest_map_time'
                return result
            index = tuple(math.floor((Fraction(str(p)) - Fraction(str(o))) / Fraction(str(r)))
                          for p, o, r in zip(point, scene['origin'], scene['resolution']))
            if any(not 0 <= index[axis] < scene['shape'][axis] for axis in range(3)):
                result.update(status='unknown', reason='outside_coverage')
                return result
            result.update(index=list(index), status='unknown', reason='no_observation')
            cell = state.cells.get(index)
            if cell is None:
                return result
            result.update(copy.deepcopy(cell))
            local = self._spec['local_map']['arithmetic']
            if query_timestamp - cell['last_observed_timestamp'] > min(max_age_ns, local['evidence_ttl_ns']):
                result.update(status='stale', reason='max_age_exceeded')
            elif cell['probability'] >= local['occupied_threshold']:
                result.update(status='occupied', reason='')
            elif cell['probability'] <= local['free_threshold']:
                result.update(status='free', reason='')
            else:
                result.update(status='unknown', reason='between_thresholds')
        return result
