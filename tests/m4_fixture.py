"""Explicit M4 fixture inputs and hand-declared lifecycle tables; no Scene candidate."""
import copy
from pathlib import Path

import yaml
from m3_motion_fixture import motion_observation
from ufm_mapping.m4_contract import validate_spec


CONFIG = Path(__file__).resolve().parents[1] / 'configs/m4_fixture.yaml'
P, Q, R = (8.25, .25, .25), (48.25, .25, .25), (88.25, .25, .25)


def load_spec(path=CONFIG):
    spec = yaml.safe_load(Path(path).read_text())
    validate_spec(spec)
    return spec


def bound_spec(spec, run_id):
    result = copy.deepcopy(spec)
    result['registration'].update(run_id=run_id, clock_id='sim:' + run_id)
    return result


def version(point, stamp, probability='3/4', interval=('7/10', '4/5')):
    return dict(point=list(point), timestamp=stamp, probability=probability,
                interval=None if interval is None else list(interval))


def query(stamp, point=(40.25, .25, .25), status=None, **changes):
    return dict(timestamp=stamp, point=list(point), status=status, **changes)


def step(sequence, stamp, active, sealed, revision, evidence, *, body=0., kind='occupied',
         points=(P,), bounds='default', queries=None, outcome='fused', contract_accepts=True,
         mutate=None):
    # Observation grid follows the explicit centered fixture body in these tables.
    return dict(input=dict(sequence=sequence, timestamp=stamp, body=[body,0.,0.],
                origin=[body-16.,-8.,-4.], kind=kind, points=[list(p) for p in points], bounds=bounds),
        active=list(active), sealed=copy.deepcopy(sealed), revision=revision,
        evidence_timestamp=evidence, structure_timestamp=stamp,
        queries=queries if queries is not None else [query(stamp)], outcome=outcome,
        contract_accepts=contract_accepts, mutate=mutate)


def scenarios(spec):
    """All ownership transitions below are explicit expected data, not computed by a reducer."""
    # Independent tables below declare these arithmetic/geometry assumptions explicitly.
    # Refuse a custom profile that would make the saved answers contradict its inputs.
    arithmetic=spec['local_map']['arithmetic']
    assumptions=dict(prior_probability=.5,neutral_probability=.5,occupied_probability=.75,
        free_probability=.25,minimum_probability=.1,maximum_probability=.9,
        free_threshold=.3,occupied_threshold=.7,evidence_ttl_ns=100_000_000,
        resolution=[.5,.5,.5],shape=[64,32,16],origin=[-16.,-8.,-4.])
    if (any(arithmetic[k]!=v for k,v in assumptions.items()) or
            spec['local_map']['evidence_intervals']!={'occupied':[.7,.8],'free':[.2,.3]} or
            spec['scene']!=dict(map_id='m4-scene-fixture',frame_id='map',resolution=[.5,.5,.5],
                                shape=[256,64,16],origin=[0.,-16.,-4.]) or
            [spec['registration']['T_map_odom'][i] for i in (3,7,11)]!=[32.,0.,0.]):
        raise ValueError('M4 explicit scenario tables require their declared arithmetic/geometry profile')
    cases = []

    def case(name, versions, steps, **overrides):
        config = copy.deepcopy(spec)
        config.update(overrides)
        cases.append(dict(name=name, spec=config, versions=versions, steps=steps))

    a = version(P,10_000_000)
    b = version(P,30_000_000,'9/10',('49/58','9/10'))
    overlap = [step(0,10_000_000,['p'],[],1,10_000_000),
        step(1,20_000_000,['p'],[],2,10_000_000,body=.5,kind='empty'),
        step(2,30_000_000,['p2'],[],3,30_000_000,body=.5)]
    overlap[1]['queries'] += [query(10_000_000,status='unavailable')]
    overlap[2]['queries'] += [query(130_000_000,status='occupied'),query(130_000_001,status='stale'),
        query(30_000_000,point=[40.25,.25,.25],status='unavailable',identity_changes={'frame_id':'odom'}),
        query(30_000_000,point=[128.,0.,0.],status='unknown')]
    case('overlap_no_double_count',{'p':a,'p2':b},overlap)

    versions=dict(p=a,q=version(Q,20_000_000),r=version(R,30_000_000),
                  pf=version(P,40_000_000,'1/4',('1/5','3/10')))
    fifo=[step(0,10_000_000,['p'],[],1,10_000_000),
        step(1,20_000_000,['q'],[['p']],2,20_000_000,body=40.,points=(Q,)),
        step(2,30_000_000,['r'],[['q']],3,30_000_000,body=80.,points=(R,),
             queries=[query(30_000_000,status='unknown'),query(30_000_000,point=[80.25,.25,.25],status='occupied')]),
        step(3,40_000_000,['pf'],[['r']],4,40_000_000,kind='free',
             queries=[query(40_000_000,status='free'),query(40_000_000,point=[80.25,.25,.25],status='unknown')])]
    case('fifo_eviction_and_fresh_return',versions,fifo,max_sealed_submaps=1)

    versions=dict(p=a,q=version(Q,20_000_000),pm=version(P,30_000_000,interval=None),
        pm2=version(P,40_000_000,'9/10',None),pf=version(P,180_000_000,'1/4',('1/5','3/10')))
    case('missing_takeover_ttl',versions,[step(0,10_000_000,['p'],[],1,10_000_000),
        step(1,20_000_000,['q'],[['p']],2,20_000_000,body=40.,points=(Q,)),
        step(2,30_000_000,['pm'],[['q']],3,30_000_000,bounds=None),
        step(3,40_000_000,['pm2'],[['q']],4,40_000_000),
        step(4,50_000_000,[],[['q'],['pm2']],5,40_000_000,body=40.,kind='empty',
             queries=[query(140_000_000,status='occupied'),query(140_000_001,status='stale')]),
        step(5,180_000_000,['pf'],[['q']],6,180_000_000,kind='free')])

    low=copy.deepcopy(spec['local_map'])
    low['arithmetic'].update(max_active_cells=2,identity_history_limit=3)
    smallq,smallr=(9.25,.25,.25),(10.25,.25,.25)
    versions=dict(p=a,q=version(smallq,10_000_000),r=version(smallr,20_000_000),
                  qf=version(smallq,40_000_000,'1/4',('1/5','3/10')))
    case('capacity_then_seal',versions,[step(0,10_000_000,['p','q'],[],1,10_000_000,points=(P,smallq)),
        step(1,20_000_000,['p','r'],[],2,20_000_000,points=(smallr,),
             queries=[query(20_000_000,point=[41.25,.25,.25],status='unknown')]),
        step(2,30_000_000,[],[['p','r']],3,20_000_000,body=40.,kind='empty'),
        step(3,40_000_000,['qf'],[['p','r']],4,40_000_000,kind='free',points=(smallq,))],
        local_map=low,max_sealed_submaps=1)

    versions=dict(p=version(P,50_000_000),pf=version(P,170_000_000,'1/4',('1/5','3/10')))
    gap=[]
    for i,kind in enumerate(('unavailable','empty','unobserved','neutral')):
        row=step(i,(i+1)*10_000_000,[],[],0,None,kind=kind,outcome='not_fused',
                 queries=[query((i+1)*10_000_000,status='unavailable')])
        row['structure_timestamp']=-1
        gap.append(row)
    gap += [step(4,50_000_000,['p'],[],1,50_000_000),
        step(5,60_000_000,['p'],[],1,50_000_000,body=200.,kind='unavailable',
             outcome='not_fused',mutate='unavailable_transform'),
        step(6,160_000_000,['p'],[],2,50_000_000,body=.5,kind='empty',
             queries=[query(160_000_000,status='stale')]),
        step(7,170_000_000,['pf'],[],3,170_000_000,body=.5,kind='free')]
    gap[5]['structure_timestamp']=50_000_000
    case('no_evidence_and_empty_motion',versions,gap)

    versions=dict(p=a,pu=version(P,20_000_000,'1/2',('7/19','12/19')),
                  pf=version(P,30_000_000,'1/4',('7/55','36/85')))
    reject=[step(0,10_000_000,['p'],[],1,10_000_000)]
    for seq,stamp,mutation,accepts,kind,body in (
            (0,10_000_000,None,True,'occupied',0.),
            (0,10_000_000,'identity_conflict',True,'occupied',0.),
            (2,9_000_000,None,True,'occupied',0.),
            (3,900_000_000,None,False,'empty',200.),
            (4,500_000_000,'bad_last_unit',False,'occupied',0.),
            (5,15_000_000,'foreign_run',False,'occupied',0.)):
        row=step(seq,stamp,['p'],[],1,10_000_000,kind=kind,body=body,mutate=mutation,
            contract_accepts=accepts,outcome='not_fused' if mutation is None and seq==0 else 'rejected',
            queries=[query(10_000_000,status='occupied')])
        row['structure_timestamp']=10_000_000
        reject.append(row)
    reject += [step(6,20_000_000,['pu'],[],2,20_000_000,kind='free',
                    queries=[query(20_000_000,status='unknown')]),
               step(7,30_000_000,['pf'],[],3,30_000_000,kind='free')]
    case('refusal_and_recovery',versions,reject)

    case('empty_seals_do_not_evict',dict(p=a,pm=version(P,50_000_000,interval=None)),[
        step(0,10_000_000,['p'],[],1,10_000_000),
        step(1,20_000_000,[],[['p']],2,10_000_000,body=40.,kind='empty'),
        step(2,30_000_000,[],[['p']],3,10_000_000,body=80.,kind='empty'),
        step(3,40_000_000,[],[['p']],4,10_000_000,kind='empty'),
        step(4,50_000_000,['pm'],[],5,50_000_000,bounds=None)],max_sealed_submaps=1)

    case('fresh_run_and_registration_time',dict(pf=version(P,20_000_000,'1/4',('1/5','3/10'))),[
        step(0,10_000_000,[],[],0,None,kind='empty',outcome='not_fused',
             queries=[query(10_000_000,status='unavailable')]),
        step(1,20_000_000,['pf'],[],1,20_000_000,kind='free',queries=[
            query(20_000_000,status='free'),query(1_000_000_000,status='unavailable'),
            query(20_000_000,status='unavailable',identity_changes={'clock_id':'foreign'}),
            query(20_000_000,point=[-.001,0.,0.],status='unknown')])])
    cases[-1]['steps'][0]['structure_timestamp']=-1
    return cases


def observation(spec, declaration):
    item=declaration['input']
    row=motion_observation(spec['local_map'],spec['registration']['run_id'],item['sequence'],
        kind=item['kind'],bounds=item['bounds'],stamp=item['timestamp'],body=item['body'],
        points=item['points'],origin=item['origin'])
    row['header']['sample_id']='perception.occupancy:m4-fixture:%s:%d' % (
        spec['registration']['run_id'],item['sequence'])
    mutation=declaration['mutate']
    if mutation=='identity_conflict':
        row['voxels'][0]['uncertainty']['value']=[.72,.8]
    elif mutation=='bad_last_unit':
        row['voxels'].append(copy.deepcopy(row['voxels'][0]))
        row['voxels'][-1]['index']=[40,16,8]
        row['voxels'][-1]['uncertainty']['unit']='m2'
    elif mutation=='foreign_run':
        row['header']['run_id']='foreign'
    elif mutation=='unavailable_transform':
        row['context']['T_mapping_body_status']='unavailable'
        row['context']['T_mapping_body']=[0.]*16
    return row
