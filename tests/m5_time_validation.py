"""Execute saved M5 expectations and bounded fault/resource probes."""
import copy
import inspect
import math
import sys

from m5_resource_audit import TerrainCensus, retained
from ufm_mapping.terrain_fixture import TerrainFixture
from ufm_mapping.terrain_replay import replay_terrain


def compare(actual, expected, path='receipt'):
    """Check declared fields recursively; only outward interval rounding has tolerance."""
    if isinstance(expected,dict):
        for key,value in expected.items():
            compare(actual[key],value,path+'.'+key)
    elif isinstance(expected,list):
        if len(actual) != len(expected):
            raise AssertionError(path+' length mismatch')
        for index,(a,b) in enumerate(zip(actual,expected)):
            compare(a,b,path+'['+str(index)+']')
    elif isinstance(expected,float) and '.height_quality.value[' in path:
        if not math.isclose(actual,expected,rel_tol=0.,abs_tol=1e-12):
            raise AssertionError(path+': '+str(actual)+' != '+str(expected))
    elif actual != expected:
        raise AssertionError(path+': '+str(actual)+' != '+str(expected))


def execute_case(case):
    events,expected = case['events'],case['expected']
    if not events or len(events) != len(expected):
        raise ValueError('M5 saved sequence/expectations incomplete')
    result = replay_terrain(case['spec'],copy.deepcopy(events))
    if result != replay_terrain(case['spec'],copy.deepcopy(events)):
        raise AssertionError('M5 private replay differs on identical saved inputs')
    for row,want in zip(result['receipts'],expected):
        compare(row,want,case['name']+'.'+str(row['sequence']))
        if row['outcome'] == 'rejected' and not row['reason']:
            raise AssertionError('M5 rejection lacks reason')
        if 'result' in row and row['result']['status'] not in ('valid','unknown','stale','unavailable'):
            raise AssertionError('M5 terrain returned an occupancy state')
    return result


def make_layer(spec):
    reg = spec['registration']
    return TerrainFixture(spec,reg['run_id'],reg['clock_id'])


FAULTS = (
    ('after_staged_grid_copy', 'install', 'samples = self._prepare_samples(staged_spec)', None),
    ('after_eight_samples', '_prepare_samples', 'mapped = _float(_fraction(height)+dz)', 8),
    ('after_sample_preparation', 'install', 'versions = dict(state.versions)', None),
    ('after_identity_staging', 'install', 'staged = _Committed(', None),
    ('immediately_before_commit', 'install', 'self._state = staged', None),
)


def inject_install(layer, spec, stamp, fault, census=None):
    name,method,needle,index = fault
    function = getattr(TerrainFixture,method)
    lines,start = inspect.getsourcelines(function)
    matches = [start+i for i,line in enumerate(lines) if needle in line]
    if len(matches) != 1:
        raise AssertionError('fault site no longer unique: '+name)
    reached = []

    def trace(frame,event,arg):
        counted = census._trace(frame,event,arg) if census else None
        if frame.f_code is not function.__code__:
            return trace if counted else None
        if event == 'line' and frame.f_lineno == matches[0] and (index is None or frame.f_locals.get('index') == index):
            reached.append(name)
            raise ValueError('injected M5 fault: '+name)
        return trace

    previous = sys.gettrace()
    sys.settrace(trace)
    try:
        try:
            layer.install(spec,stamp)
        except ValueError as exc:
            if str(exc) != 'injected M5 fault: '+name:
                raise
        else:
            raise AssertionError('fault injection did not interrupt installation')
    finally:
        sys.settrace(previous)
    if reached != [name]:
        raise AssertionError('fault site not reached: '+name)


def resource_probe(spec):
    """64 successful installs plus failed 64th retries and saturation operations.

    Direct method stress, not an event replay exceeding the 64-receipt contract.
    """
    census = TerrainCensus()
    layer = census.call(make_layer,spec)
    rows = []
    for index in range(64):
        payload = copy.deepcopy(spec)
        payload['identity']['dataset_version'] = 'budget-v'+format(index,'02d')
        payload['source_time'].update(acquisition_ns=10+index,publication_ns=20+index)
        stamp = 100+index
        layer.observe_clock(stamp)
        if index == 63:
            before = layer.snapshot()
            for fault in FAULTS:
                inject_install(layer,payload,stamp,fault,census)
                if before != layer.snapshot() or len(layer._state.versions) != 63:
                    raise AssertionError('failed 64th install spent identity/state: '+fault[0])
        if not census.call(layer.install,payload,stamp):
            raise AssertionError('fresh identity did not install')
        rows.append(retained(layer))
    before = census.call(layer.snapshot)
    ledger = dict(layer._state.versions)
    if census.call(layer.install,payload,163) is not False:
        raise AssertionError('identical active version at capacity must be idempotent')
    failures = []
    too_many = copy.deepcopy(payload)
    too_many['identity']['dataset_version'] = 'budget-v64'
    conflicting = copy.deepcopy(payload)
    conflicting['grid']['heights'][0] = 1.
    too_large = copy.deepcopy(payload)
    too_large['identity']['dataset_version'] = 'x'*16384
    escaped = copy.deepcopy(payload)
    escaped['identity']['dataset_version'] = '\U0001f600'*16384
    retired = copy.deepcopy(spec)
    for name,value,reason in (('65th',too_many,'identity limit'),('conflict',conflicting,'conflicting'),
                              ('oversize',too_large,'byte limit'),('escaped_oversize',escaped,'byte limit'),
                              ('retired',retired,'retired')):
        try:
            census.call(layer.install,value,163)
        except ValueError as exc:
            if reason not in str(exc):
                raise
            failures.append(dict(name=name,reason=str(exc)))
        else:
            raise AssertionError('M5 saturation case accepted: '+name)
        if before != layer.snapshot() or layer._state.versions != ledger:
            raise AssertionError('saturation failure mutated state/identity')
    request = dict(run_id=spec['registration']['run_id'],clock_id=spec['registration']['clock_id'],
                   frame_id='map',query_timestamp=163,point_xy=[111.,179.])
    result = census.call(layer.query,request)
    compare(result,dict(status='valid',height=3.,dataset_version='budget-v63',terrain_revision=64,
                       installed_timestamp=163,source_time=payload['source_time']))
    # A future query does not move the observed clock or prevent an earlier query.
    request['query_timestamp'] = 10000
    compare(census.call(layer.query,request),dict(status='unavailable',reason='registration_unavailable',height=None))
    request['query_timestamp'] = 162
    compare(census.call(layer.query,request),dict(status='unavailable',reason='query_before_terrain_activation',height=None))
    if layer.snapshot() != before:
        raise AssertionError('future/historical queries mutated observed clock/state')
    layer.observe_clock(162)
    request['query_timestamp'] = 163
    compare(census.call(layer.query,request),dict(status='unavailable',reason='clock_reset_new_run_required',height=None))
    try:
        census.call(layer.install,payload,162)
    except ValueError:
        pass
    else:
        raise AssertionError('capacity/clock reset allowed a duplicate install')
    layer.disable()
    compare(census.call(layer.query,request),dict(status='unavailable',reason='terrain_disabled',height=None))
    if layer._state.versions != ledger or layer._state.revision != 64:
        raise AssertionError('terminal reset/disable changed committed identity/version')
    return dict(retained=rows[-1],retained_history=rows,census=census.report(),
                fault_sites=[f[0] for f in FAULTS],rejections=failures,
                successful_versions=64,saturation_idempotent=True,queries_nonmutating=True,
                terminal_reset_disable_unavailable=True)
