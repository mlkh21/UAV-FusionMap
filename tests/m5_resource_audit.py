"""Test-only logical terrain payload census; no claim about allocator peaks or RSS."""
import sys
from pathlib import Path


TERRAIN = str(Path(__file__).resolve().parents[1]/'mapping/ufm_mapping/terrain_fixture.py')


def retained(candidate):
    state = candidate._state
    counts = dict(active_samples=len(state.samples),
        template_samples=len(candidate._template['grid']['heights']),
        active_grid_samples=0 if state.spec is None else len(state.spec['grid']['heights']),
        identities=len(state.versions), identity_bytes=sum(len(v.encode('utf-8')) for v in state.versions.values()))
    bounds = dict(active_samples=16,template_samples=16,active_grid_samples=16,
                  identities=64,identity_bytes=64*16384)
    if any(counts[k]>bounds[k] for k in bounds):
        raise AssertionError('M5 retained payload bound exceeded: '+str(counts))
    return counts


class TerrainCensus:
    """Count unique reachable payloads at terrain Python line/return boundaries.

    Roots are candidate frame locals and its returned value, including incoming,
    committed, staged, partial sample exports and snapshot/query copies. Caller
    archives and replay receipt lists are outside this candidate-only scope.
    """
    def __init__(self):
        self.peaks = dict(states=0,grid_samples=0,sample_payloads=0,identity_refs=0,
                          canonical_bytes=0,canonical_fragment_bytes=0,encoder_current_part_bytes=0)
        self.samples = 0
        self._string_sizes = {}

    def _trace(self, frame, event, arg):
        if frame.f_code.co_filename != TERRAIN:
            return None
        if event not in ('line','return'):
            return self._trace
        if frame.f_code.co_name == '_canonical' and event != 'return':
            return self._trace
        roots = [arg] if event == 'return' else []
        cursor = frame
        fragments,current_part = 0,0
        while cursor:
            if cursor.f_code.co_filename == TERRAIN:
                roots.extend(cursor.f_locals.values())
                if cursor.f_code.co_name == '_canonical':
                    fragments += sum(len(part.encode('utf-8')) for part in cursor.f_locals.get('parts',[]))
                    current_part += len(cursor.f_locals.get('part','').encode('utf-8'))
            cursor = cursor.f_back
        counts = dict.fromkeys(self.peaks,0)
        counts['canonical_fragment_bytes'] = fragments
        counts['encoder_current_part_bytes'] = current_part
        stack,seen = roots,set()
        while stack:
            value = stack.pop()
            if id(value) in seen:
                continue
            seen.add(id(value))
            if isinstance(value,dict):
                if {'heights','no_data_mask','height_quality','affine'} <= value.keys():
                    counts['grid_samples'] += len(value['heights'])
                if {'source_index','source_xy','height','quality_contributors'} <= value.keys():
                    counts['sample_payloads'] += 1
                stack.extend(value.values())
            elif isinstance(value,(list,tuple)):
                stack.extend(value)
            elif isinstance(value,str):
                if value.startswith('{"eligibility":'):
                    if id(value) not in self._string_sizes:
                        self._string_sizes[id(value)] = (value,len(value.encode('utf-8')))
                    counts['canonical_bytes'] += self._string_sizes[id(value)][1]
            elif type(value).__module__ == 'ufm_mapping.terrain_fixture':
                if type(value).__name__ == '_Committed':
                    counts['states'] += 1
                    counts['identity_refs'] += len(value.versions)
                stack.extend(vars(value).values())
        for key in self.peaks:
            self.peaks[key] = max(self.peaks[key],counts[key])
        self.samples += 1
        return self._trace

    def call(self, function, *args):
        previous = sys.gettrace()
        sys.settrace(self._trace)
        try:
            return function(*args)
        finally:
            sys.settrace(previous)

    def report(self):
        # Template + incoming + committed + staged + returned snapshot allowance.
        # Old/new directories share immutable strings; one new canonical string
        # and its incremental encoder fragments can coexist with 64 identities.
        bounds = dict(states=2,grid_samples=5*16,sample_payloads=3*16+1,
            identity_refs=2*64,canonical_bytes=65*16384,canonical_fragment_bytes=16384,
            encoder_current_part_bytes=12*16384+2)
        if any(self.peaks[k]>bounds[k] for k in bounds):
            raise AssertionError('M5 candidate census exceeds structural bound: '+str(self.peaks))
        return dict(peaks=self.peaks,bounds=bounds,line_return_samples=self.samples,
            scope='terrain_fixture.py line/return reachable payloads; excludes caller archives, allocator internals and RSS')
