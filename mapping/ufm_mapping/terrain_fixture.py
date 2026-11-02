"""Explicit private M5 fixture layer; independent of occupancy, ROS and GIS."""
import copy
from dataclasses import dataclass, field
from fractions import Fraction
import json
import math
import struct

from .m5_contract import (LIMITS, _time, validate_request, validate_request_shape, validate_spec)


def _canonical(spec):
    parts, size = [], 0
    for part in json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(spec):
        size += len(part.encode('utf-8'))
        if size > LIMITS['max_input_bytes']:
            raise ValueError('M5 candidate input exceeds canonical JSON byte limit')
        parts.append(part)
    return ''.join(parts)


def _fraction(value):
    return Fraction(str(value))


def _float(value, direction=0):
    try:
        rounded = float(value)
    except OverflowError as exc:
        raise ValueError('M5 registered sample overflows float64') from exc
    if not math.isfinite(rounded):
        raise ValueError('M5 registered sample must remain finite')
    error = Fraction.from_float(rounded) - value
    # Python 3.8 has no math.nextafter. Expand interval endpoints by one ULP if needed.
    if direction and ((direction < 0 and error > 0) or (direction > 0 and error < 0)):
        if rounded == 0:
            rounded = struct.unpack('!d', struct.pack('!Q', 1 if direction > 0 else (1 << 63) | 1))[0]
        else:
            bits = struct.unpack('!Q', struct.pack('!d', rounded))[0]
            bits += 1 if (rounded > 0) == (direction > 0) else -1
            rounded = struct.unpack('!d', struct.pack('!Q', bits))[0]
        if not math.isfinite(rounded):
            raise ValueError('M5 outward height interval exceeds float64')
    return rounded


def _unavailable_quality(source):
    return dict(status='unavailable', kind='', value=None, unit='', source=source)


def _binding(spec):
    return dict(identity={key:value for key,value in spec['identity'].items() if key != 'dataset_version'},
                horizontal=spec['horizontal'], vertical=spec['vertical'], map_grid=spec['map_grid'],
                registration=spec['registration'], limits=spec['limits'],
                geometry={key:spec['grid'][key] for key in ('rows','columns','affine','sample_anchor')})


@dataclass(frozen=True)
class _Committed:
    revision: int = 0
    installed_timestamp: object = None
    spec: object = None
    samples: tuple = ()
    versions: dict = field(default_factory=dict)


class TerrainFixture:
    """One immutable registration/run; call observe_clock explicitly, query never moves it.

    This class is single-threaded. Wrappers must serialize calls if used concurrently.
    Replacing the committed state is the only installation commit operation.
    """
    def __init__(self, spec, run_id, clock_id):
        validate_spec(spec)
        _canonical(spec)
        if (run_id, clock_id) != (spec['registration']['run_id'], spec['registration']['clock_id']):
            raise ValueError('M5 constructor run/clock differs from registration')
        self._template = copy.deepcopy(spec)
        self._binding = copy.deepcopy(_binding(spec))
        self._state = _Committed()
        self._clock = None
        self._locked = False
        self._enabled = True

    def observe_clock(self, timestamp):
        _time(timestamp, 'observed clock')
        if self._clock is not None and timestamp < self._clock:
            self._locked = True
        self._clock = timestamp

    def disable(self):
        """Terminal opt-out for this instance; re-enable requires a fresh instance/run."""
        self._enabled = False

    def _prepare_samples(self, spec):
        grid, registration = spec['grid'], spec['registration']
        affine = [_fraction(v) for v in grid['affine']]
        dx,dy,dz = [_fraction(registration['T_map_terrain'][i]) for i in (3,7,11)]
        samples = []
        for index, height in enumerate(grid['heights']):
            row,col = divmod(index, grid['columns'])
            source_xy = [affine[0]+(col+Fraction(1,2))*affine[1],
                         affine[3]+(row+Fraction(1,2))*affine[5]]
            # Check rendered float64 XY still identifies exactly the source sample center.
            map_xy = [_float(source_xy[0]+dx),_float(source_xy[1]+dy)]
            if any(_fraction(out) != exact for out,exact in zip(map_xy,(source_xy[0]+dx,source_xy[1]+dy))):
                raise ValueError('M5 map sample center loses float64 lattice precision')
            quality = _unavailable_quality('m5_fixture_no_data_v1')
            mapped = None
            if height is not None:
                mapped = _float(_fraction(height)+dz)
                original,offset = grid['height_quality'][index],registration['height_quality']
                quality = _unavailable_quality('m5_fixture_height_quality_missing_v1')
                if original['status'] == offset['status'] == 'available':
                    bounds = [_fraction(a)+_fraction(b) for a,b in zip(original['value'],offset['value'])]
                    quality = dict(status='available', kind='height_interval', unit='m',
                        value=[_float(bounds[0],-1),_float(bounds[1],1)], source='m5_fixture_height_interval_sum_v1')
            samples.append(dict(source_index=[row,col], source_xy=[_float(v) for v in source_xy],
                map_xy=map_xy, height=mapped, height_quality=quality,
                quality_contributors=dict(sample=copy.deepcopy(grid['height_quality'][index]),
                                          registration=copy.deepcopy(registration['height_quality']))))
        return tuple(samples)

    def install(self, spec, timestamp):
        """Return True for a new committed version, False for an identical active version."""
        _time(timestamp, 'install time')
        if not self._enabled or self._locked or self._clock is None or timestamp != self._clock:
            raise ValueError('M5 installation requires enabled, unlocked, current run clock')
        validate_spec(spec)
        encoded = _canonical(spec)
        if _binding(spec) != self._binding:
            raise ValueError('M5 registration/geometry/identity changed; new instance required')
        state = self._state
        version = spec['identity']['dataset_version']
        if version in state.versions:
            if encoded != state.versions[version]:
                raise ValueError('M5 conflicting content for existing dataset version')
            if state.spec['identity']['dataset_version'] != version:
                raise ValueError('M5 retired dataset version cannot be reactivated')
            return False
        if len(state.versions) >= LIMITS['max_receipt_events']:
            raise ValueError('M5 version identity limit exceeded; no identity eviction')
        for interval in (spec['registration']['valid_interval_ns'],spec['eligibility']['valid_interval_ns']):
            if not interval[0] <= timestamp < interval[1]:
                raise ValueError('M5 new version installation outside registration/eligibility')
        if state.spec is not None and any(spec['source_time'][key] < state.spec['source_time'][key]
                                          for key in ('acquisition_ns','publication_ns')):
            raise ValueError('M5 replacement source times move backwards')
        staged_spec = copy.deepcopy(spec)
        samples = self._prepare_samples(staged_spec)
        versions = dict(state.versions)
        versions[version] = encoded
        staged = _Committed(state.revision+1,timestamp,staged_spec,samples,versions)
        self._state = staged
        return True

    def snapshot(self):
        """Private diagnostic copy, not MapSnapshot or a public terrain protocol."""
        state = self._state
        return copy.deepcopy(dict(terrain_revision=state.revision, installed_timestamp=state.installed_timestamp,
            spec=state.spec, samples=list(state.samples), version_ids=list(state.versions),
            enabled=self._enabled, locked=self._locked, clock=self._clock))

    def query(self, request):
        validate_request_shape(request)
        state = self._state
        result = dict(request, schema_version='m5_terrain_result.v1', terrain_revision=state.revision,
            terrain_id=self._template['identity']['terrain_id'], dataset_version=None, registration_id=None,
            status='unavailable', reason='', height=None, source_index=None, source_xy=None,
            height_quality=_unavailable_quality('m5_fixture_unavailable_v1'), quality_contributors=None,
            source_time=None, eligibility=None, registration_validity=None, installed_timestamp=None,
            source_kind='fixture', product_kind='DTM')
        registration = self._template['registration']
        if (request['run_id'],request['clock_id'],request['frame_id']) != (
                registration['run_id'],registration['clock_id'],'map'):
            result['reason'] = 'run_clock_or_frame_mismatch'
            return copy.deepcopy(result)
        validate_request(self._template,request)
        reason = ('terrain_disabled' if not self._enabled else 'clock_reset_new_run_required' if self._locked
                  else 'clock_unavailable' if self._clock is None else 'terrain_unavailable' if state.spec is None else '')
        if reason:
            result['reason'] = reason
            return copy.deepcopy(result)
        stamp = request['query_timestamp']
        start,end = registration['valid_interval_ns']
        if not start <= stamp < end:
            result['reason'] = 'registration_unavailable'
            return copy.deepcopy(result)
        eligibility = state.spec['eligibility']
        if stamp < max(state.installed_timestamp,eligibility['valid_interval_ns'][0]):
            result['reason'] = 'query_before_terrain_activation'
            return copy.deepcopy(result)
        spec = state.spec
        result.update(dataset_version=spec['identity']['dataset_version'],
            registration_id=registration['registration_id'], installed_timestamp=state.installed_timestamp,
            source_time=spec['source_time'], eligibility=eligibility, registration_validity=[start,end])
        matrix,gt = registration['T_map_terrain'],spec['grid']['affine']
        x,y = map(_fraction,request['point_xy'])
        col = (x-_fraction(matrix[3])-_fraction(gt[0]))/_fraction(gt[1])-Fraction(1,2)
        row = (y-_fraction(matrix[7])-_fraction(gt[3]))/_fraction(gt[5])-Fraction(1,2)
        if row.denominator != 1 or col.denominator != 1:
            raise ValueError('M5 point is not a direct source sample center')
        stale = stamp >= eligibility['valid_interval_ns'][1]
        if not 0 <= row < spec['grid']['rows'] or not 0 <= col < spec['grid']['columns']:
            result.update(status='stale' if stale else 'unknown', reason='terrain_expired' if stale else 'outside_coverage')
            return copy.deepcopy(result)
        sample = state.samples[int(row)*spec['grid']['columns']+int(col)]
        if stale:
            result.update(status='stale',reason='terrain_expired')
        elif sample['height'] is None:
            result.update(status='unknown',reason='no_data')
        else:
            result.update(status='valid',reason='')
        result.update({key:sample[key] for key in ('height','height_quality','source_index','source_xy','quality_contributors')})
        return copy.deepcopy(result)
