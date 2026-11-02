"""Test-only resource and rollback probes for M4; candidate inputs stay public occupancy."""
import copy
from unittest.mock import patch

from m4_fixture import P, Q, R, bound_spec, observation, step
from m4_resource_audit import MappingCensus, assert_retained, small_spec
from ufm_mapping.scene_map import SceneMap


def make_scene(spec, run='m4-probe'):
    spec=bound_spec(small_spec(spec),run)
    return SceneMap(spec,run,'sim:'+run),spec


def row(spec, seq, *, body=0., kind='occupied', points=(P,), stamp=None, bounds='default'):
    return observation(spec,step(seq,(seq+1)*10_000_000 if stamp is None else stamp,[],[],0,None,
        body=body,kind=kind,points=points,bounds=bounds))


def fingerprint(scene):
    """Capture private correctness state, not a hash; raw equality detects partial commits."""
    state=scene._state
    local=state.local
    return copy.deepcopy(dict(snapshot=scene.snapshot(),active=state.active,sealed=state.sealed,
        cells=state.cells,sequence=state.sequence,structure=state.structure_timestamp,
        local_snapshot=local.snapshot(),local_ranges=local._log_odds,seen=local._seen,
        last_observation=local._last_observation,
        input_time=local._input_timestamp,geometry_time=local._geometry_timestamp))


def atomic_probes(spec):
    results=[]
    for mode in ('export_after_local','takeover_after_delete','after_fifo','after_validation'):
        scene,config=make_scene(spec,'m4-atomic:'+mode)
        scene.update(row(config,0))
        scene.update(row(config,1,body=40.,points=(Q,)))
        if mode=='takeover_after_delete':
            attempt=row(config,2,bounds=None)
        else:
            attempt=row(config,2,body=80.,points=(R,))
        before=fingerprint(scene)
        marker=[]
        if mode=='export_after_local':
            method='_scene_cells'
            original=scene._scene_cells
            def fail(value):
                original(value)
                marker.append('local_updated')
                raise ValueError('injected export failure')
        elif mode=='takeover_after_delete':
            method='_validate_scene'
            def fail(staged):
                # P was removed from its old sealed record before validation.
                if (80,32,8) not in staged.active or any((80,32,8) in g['cells'] for g in staged.sealed.values()):
                    raise AssertionError('failure injection did not reach takeover')
                marker.append('old_owner_deleted')
                raise ValueError('injected ownership failure')
        elif mode=='after_fifo':
            method='_validate_scene'
            def fail(staged):
                if (80,32,8) in staged.cells or (160,32,8) not in staged.cells:
                    raise AssertionError('failure injection did not reach FIFO')
                marker.append('fifo_applied')
                raise ValueError('injected FIFO failure')
        else:
            method='_prepare_scene'
            original=scene._prepare_scene
            def fail(staged,before,after):
                original(staged,before,after)
                marker.append('scene_validated')
                raise ValueError('injected final prepare failure')
        with patch.object(scene,method,side_effect=fail):
            try:scene.update(attempt)
            except ValueError:pass
            else:raise AssertionError('injected failure was swallowed')
        if not marker or before!=fingerprint(scene):
            raise AssertionError('failed transaction modified local/Scene state: '+mode)
        if not scene.update(attempt):
            raise AssertionError('same identity/time could not recover after failure')
        once=fingerprint(scene)
        if scene.update(attempt) or fingerprint(scene)!=once:
            raise AssertionError('retry was fused twice')
        counts=assert_retained(scene,1)
        results.append(dict(mode=mode,checkpoint=marker,rollback_equal=True,same_identity_retry=True,
                            duplicate_fused=False,retained=counts))
    return results


def census_probes(spec):
    scene,config=make_scene(spec,'m4-census')
    census=MappingCensus()
    rows=[row(config,0,points=(P,(9.25,.25,.25))),
        row(config,1,points=((10.25,.25,.25),)), # N=2 update temporarily has N+V cells before eviction.
        row(config,2,body=.5,kind='empty'),
        row(config,3,body=40.,points=(Q,(49.25,.25,.25)),bounds=None),
        row(config,4,body=80.,points=(R,(89.25,.25,.25))),
        row(config,5,kind='free')]
    retained=[]
    outputs=[]
    for value in rows:
        census.call(scene.update,value)
        retained.append(assert_retained(scene,2))
        snapshot=census.call(scene.snapshot)
        outputs.append(dict(snapshot_cells=len(snapshot['cells'])))
        if snapshot['cells']:
            cell=snapshot['cells'][0]
            point=[config['scene']['origin'][i]+(cell['index'][i]+.5)*.5 for i in range(3)]
            result=census.call(scene.query,map_id='m4-scene-fixture',frame_id='map',
                run_id=config['registration']['run_id'],clock_id=config['registration']['clock_id'],
                query_timestamp=value['header']['timestamp'],point=point,max_age_ns=100_000_000)
            outputs[-1]['query_cell_payloads']=int(result['observed'])
    result=census.validate(2,1,3,2)
    result.update(retained=retained,output_counts=outputs,
        note='V=2 fixture max input voxels; H bound is on records, retained voxel payloads are H*V')
    return result


def domain_probes(spec):
    scene,config=make_scene(spec,'m4-domain-old')
    scene.update(row(config,0))
    before=fingerprint(scene)
    errors=[]
    for key in ('run_id','clock_id'):
        value=row(config,1)
        value['header'][key]='foreign'
        try:scene.update(value)
        except ValueError:errors.append(key)
        else:raise AssertionError('foreign domain accepted')
    expired=row(config,2,stamp=1_000_000_000)
    try:scene.update(expired)
    except ValueError:errors.append('registration_expired')
    else:raise AssertionError('expired registration accepted')
    if fingerprint(scene)!=before:raise AssertionError('foreign input modified old run')
    fresh,new_spec=make_scene(spec,'m4-domain-new')
    if fresh.snapshot()['cells']:raise AssertionError('new run inherited cells')
    fresh.update(row(new_spec,0,kind='free'))
    value=fresh.snapshot()['cells'][0]
    if abs(value['probability']-.25)>1e-12:raise AssertionError('new run inherited probability')
    return dict(rejected=errors,old_state_equal=True,new_run_probability=value['probability'])
