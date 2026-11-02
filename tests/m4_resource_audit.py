"""Test-only logical retention and live mapping-frame payload census, not RSS/PERF-01."""
import copy
import sys
from pathlib import Path


CELL_FIELDS = {'index','probability','observed','last_observed_timestamp','confidence','uncertainty'}
MAPPING = str(Path(__file__).resolve().parents[1]/'mapping/ufm_mapping')


def small_spec(spec):
    result=copy.deepcopy(spec)
    result['max_sealed_submaps']=1
    result['local_map']['arithmetic'].update(max_active_cells=2,identity_history_limit=3)
    return result


def retained_counts(candidate):
    state = candidate._state
    local = state.local
    owned = dict(state.active)
    for group in state.sealed.values():
        for index, cell in group['cells'].items():
            if index in owned:
                raise AssertionError('multiple Scene owners')
            owned[index] = cell
    if set(owned) != set(state.cells) or any(state.cells[i] is not c for i,c in owned.items()):
        raise AssertionError('ownership index copied or retained a hidden version')
    if set(local._cells) != set(local._log_odds):
        raise AssertionError('local nominal/range ledger differs from cells')
    return dict(local_cells=len(local._cells), local_ranges=len(local._log_odds),
        active_export_cells=len(state.active), sealed_submaps=len(state.sealed),
        sealed_cells=sum(len(g['cells']) for g in state.sealed.values()),
        ownership_index=len(state.cells), identity_records=len(local._seen),
        identity_voxels=sum(len(row['voxels']) for row in local._seen.values()),
        owned_payloads=len({id(c) for c in owned.values()}))


def assert_retained(candidate, max_input_voxels):
    counts = retained_counts(candidate)
    spec = candidate._spec
    n = spec['local_map']['arithmetic']['max_active_cells']
    h = spec['local_map']['arithmetic']['identity_history_limit']
    k = spec['max_sealed_submaps']
    bounds = dict(local_cells=n,local_ranges=n,active_export_cells=n,sealed_submaps=k,
        sealed_cells=k*n,ownership_index=(k+1)*n,identity_records=h,
        identity_voxels=h*max_input_voxels,owned_payloads=(k+1)*n)
    if any(counts[key]>bounds[key] for key in counts):
        raise AssertionError('M4 retained item limit exceeded: '+str(counts))
    return counts


class MappingCensus:
    """Sample reachable payloads at mapping Python line/return boundaries.

    Count distinct objects, including both committed and staged states, local
    snapshots, partial exports and returned values. Do not count test fixtures,
    saved results or caller-retained snapshots as candidate memory.
    """
    def __init__(self):
        self.peaks = dict(cell_payloads=0, voxel_payloads=0, scene_states=0,local_maps=0,
            ownership_refs=0,sealed_records=0,local_range_items=0,identity_records=0,
            temporary_owner_lookup=0,cell_lists_items=0)
        self.samples = 0

    def _trace(self, frame, event, arg):
        if not frame.f_code.co_filename.startswith(MAPPING):
            return None
        if event not in ('line','return'):
            return self._trace
        roots = [arg] if event=='return' else []
        cursor=frame
        lookup_entries=0
        while cursor:
            if cursor.f_code.co_filename.startswith(MAPPING):
                roots.extend(cursor.f_locals.values())
                lookup_entries+=len(cursor.f_locals.get('sealed_owners',{}))
            cursor=cursor.f_back
        seen=set()
        counts=dict.fromkeys(self.peaks,0)
        counts['temporary_owner_lookup']=lookup_entries
        stack=list(roots)
        while stack:
            value=stack.pop()
            if id(value) in seen:continue
            seen.add(id(value))
            if isinstance(value,dict):
                if CELL_FIELDS <= value.keys():counts['cell_payloads']+=1
                elif {'index','probability','observed','confidence','uncertainty'} <= value.keys():
                    counts['voxel_payloads']+=1
                stack.extend(value.values())
            elif isinstance(value,(list,tuple,set)):
                if isinstance(value,list) and value and all(isinstance(v,dict) and
                        CELL_FIELDS <= v.keys() for v in value):
                    counts['cell_lists_items']+=len(value)
                stack.extend(value)
            elif type(value).__module__.startswith('ufm_mapping.'):
                if type(value).__name__=='_State':
                    counts['scene_states']+=1
                    counts['ownership_refs']+=len(value.cells)
                    counts['sealed_records']+=len(value.sealed)
                if type(value).__name__=='RollingIntervalProbabilityMap':
                    counts['local_maps']+=1
                    counts['local_range_items']+=len(value._log_odds)
                    counts['identity_records']+=len(value._seen)
                stack.extend(vars(value).values())
        for key in self.peaks:self.peaks[key]=max(self.peaks[key],counts[key])
        self.samples+=1
        return self._trace

    def call(self, function, *args, **kwargs):
        previous=sys.gettrace()
        sys.settrace(self._trace)
        try:return function(*args,**kwargs)
        finally:sys.settrace(previous)

    def validate(self, n, k, h, v):
        # Conservative payload bounds from one committed state + one staged copy,
        # before/after snapshots, moving-grid and export construction; not bytes.
        bounds=dict(cell_payloads=(2*k+12)*n+2*v+4,
            voxel_payloads=2*h*v+2*v,scene_states=2,local_maps=2,
            ownership_refs=2*(k+1)*n,sealed_records=2*k+1,local_range_items=2*n,
            identity_records=2*h+1,temporary_owner_lookup=k*n,cell_lists_items=(2*k+8)*n)
        if any(self.peaks[key]>bounds[key] for key in bounds):
            raise AssertionError('mapping-frame census exceeds structural bound: '+str(self.peaks))
        return dict(peaks=self.peaks,bounds=bounds,samples=self.samples,
            scope='mapping Python line/return samples; excludes caller-held fixtures/results; not allocator peak/RSS')
