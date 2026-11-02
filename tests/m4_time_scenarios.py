"""Explicit M4 time/FIFO tables and periodic bounded trajectories, independent of Scene code."""
import copy

from m4_fixture import P, Q, R, bound_spec, query, step, version
from m4_fixture import observation as build_observation
from m4_oracle import expected_step
from m4_resource_audit import small_spec


def frozen_cases(spec):
    """Independent explicit states, including time gaps and empty-window ownership changes."""
    cases = []

    def add(name, versions, declarations, config=None):
        config = bound_spec(config or small_spec(spec), 'm4-time:' + name)
        cases.append(dict(name=name, spec=config, versions=versions, steps=[dict(
            observation=build_observation(config, declaration), declaration=declaration,
            expected=expected_step(config, versions, declaration)) for declaration in declarations]))

    versions = dict(p=version(P,10_000_000), q=version(Q,20_000_000),
        pm=version(P,130_000_001,interval=None),
        pm2=version(P,140_000_001,'9/10',None),
        pf=version(P,250_000_002,'1/4',('1/5','3/10')))
    rows = [step(0,10_000_000,['p'],[],1,10_000_000),
        step(1,20_000_000,['q'],[['p']],2,20_000_000,body=40.,points=(Q,),queries=[
            query(110_000_000,status='occupied'),query(110_000_001,status='stale'),
            query(110_000_001,point=[80.25,.25,.25],status='occupied')]),
        step(2,120_000_001,[],[['p'],['q']],3,20_000_000,kind='empty',queries=[
            query(120_000_000,status='unavailable'),query(120_000_001,status='stale')]),
        step(3,130_000_001,['pm'],[['q']],4,130_000_001,bounds=None),
        step(4,140_000_001,['pm2'],[['q']],5,140_000_001),
        step(5,150_000_001,[],[['q'],['pm2']],6,140_000_001,body=40.,kind='empty',queries=[
            query(240_000_001,status='occupied'),query(240_000_002,status='stale')]),
        step(6,250_000_002,['pf'],[['q']],7,250_000_002,kind='free',queries=[
            query(250_000_002,status='free'),query(250_000_002,point=[80.25,.25,.25],status='stale')])]
    config=small_spec(spec)
    config['max_sealed_submaps']=2
    add('different_cell_ages_and_missing_restart',versions,rows,config)

    # Empty sealed groups must be removed before applying FIFO, not count against K.
    versions = dict(p=version(P,10_000_000),q=version(Q,20_000_000),
        pf=version(P,50_000_000,'1/4',('1/5','3/10')),r=version(R,70_000_000))
    rows=[step(0,10_000_000,['p'],[],1,10_000_000),
        step(1,20_000_000,['q'],[['p']],2,20_000_000,body=40.,points=(Q,)),
        step(2,30_000_000,[],[['q']],3,20_000_000,body=80.,kind='empty'),
        step(3,40_000_000,[],[['q']],4,20_000_000,kind='empty'),
        step(4,50_000_000,['pf'],[['q']],5,50_000_000,kind='free'),
        step(5,60_000_000,[],[['pf']],6,50_000_000,body=40.,kind='empty'),
        step(6,70_000_000,['r'],[['pf']],7,70_000_000,body=80.,points=(R,))]
    add('no_stale_owner_resurrection',versions,rows)

    versions = dict(p=version(P,10_000_000),q=version(Q,20_000_000))
    rows=[step(0,10_000_000,['p'],[],1,10_000_000)]
    for seq,stamp,kind,body,mutation in (
            (1,800_000_000,'empty',200.,None),
            (2,700_000_000,'occupied',0.,'bad_last_unit'),
            (3,600_000_000,'occupied',0.,'foreign_run'),
            (4,5_000_000,'occupied',0.,None)):
        declaration=step(seq,stamp,['p'],[],1,10_000_000,kind=kind,body=body,mutate=mutation,
            outcome='rejected',contract_accepts=mutation is None and body==0.,
            queries=[query(10_000_000,status='occupied')])
        declaration['structure_timestamp']=10_000_000
        rows.append(declaration)
    rows.append(step(5,20_000_000,['q'],[['p']],2,20_000_000,body=40.,points=(Q,)))
    add('rejected_future_does_not_poison_time',versions,rows)
    return cases


def periodic_fixture(spec, cycles=20):
    """Three disjoint explicit windows repeat; every visit starts a fresh local prior.

    Answers are a closed-form schedule (current visit and preceding visit), not
    a second implementation of Scene's ownership/eviction algorithm.
    """
    spec = bound_spec(small_spec(spec), 'm4-bounded-periodic')
    versions, declarations = {}, []
    visits = [(0.,P),(40.,Q),(80.,R)]
    previous = []
    for visit in range(cycles*3):
        body, point = visits[visit%3]
        second = (point[0]+1.,point[1],point[2])
        start = (visit*2+1)*4_000_000
        names = ['v%d:p'%visit,'v%d:q'%visit]
        missing = visit%2 == 1
        versions[names[0]] = version(point,start,interval=None if missing else ('7/10','4/5'))
        versions[names[1]] = version(second,start,interval=None if missing else ('7/10','4/5'))
        queries=[query(start,point=[point[0]+32.,.25,.25],status='occupied'),
                 query(start,point=[point[0]+33.,.25,.25],status='occupied')]
        declarations.append(step(visit*2,start,names,[previous] if previous else [],visit*2+1,start,
            body=body,points=(point,second),bounds=None if missing else 'default',queries=queries))
        updated = 'v%d:p2'%visit
        versions[updated] = version(point,start+4_000_000,'1/2',None if missing else ('7/19','12/19'))
        current = [updated,names[1]]
        queries=[query(start+4_000_000,point=[point[0]+32.,.25,.25],status='unknown'),
                 query(start+4_000_000,point=[point[0]+33.,.25,.25],status='occupied')]
        if visit>=2:
            old = visits[(visit-2)%3][1]
            queries.append(query(start+4_000_000,point=[old[0]+32.,.25,.25],status='unknown'))
        declarations.append(step(visit*2+1,start+4_000_000,current,[previous] if previous else [],
            visit*2+2,start+4_000_000,body=body,kind='free',points=(point,),queries=queries))
        previous = current
    return dict(name='periodic_%d_steps'%len(declarations),spec=spec,versions=versions,
        steps=[dict(observation=build_observation(spec,d),declaration=d,
                    expected=expected_step(spec,versions,d)) for d in declarations])
