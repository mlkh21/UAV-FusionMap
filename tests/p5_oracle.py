"""Independent arithmetic checks for saved declarations; imports no builders or business code."""
from fractions import Fraction as F


def _checks(expected, case_id):
    case = next(c for c in expected['cases'] if c['id'] == case_id)
    return {row['after']:row['values'] for row in case['checks']}


def verify_seeds(inputs, expected):
    grid = inputs['profiles']['A']
    for case in inputs['cases']:
        if not case['id'].startswith('S05.'):
            continue
        event = next(e for e in case['events'] if isinstance(e,list) and e[0] == 'motion')
        args = event[4]
        check = _checks(expected,case['id'])['motion']
        age, speed = args.get('pose_age_ns',0), args.get('speed_mps',0)
        point = [F(str(v)) for v in grid['world_point']]
        error = F(str(speed))*age/1_000_000_000
        point[1] -= error
        index = [int((p-F(str(o))) // F(str(r))) for p,o,r in zip(point,grid['origin'],grid['resolution'])]
        for key, wanted in (('geometry.point',list(map(float,point))),('geometry.index',index),
                            ('geometry.error_m',float(error)),('bundle.pose_age_ns',age)):
            if key in check and check[key] != wanted:
                raise ValueError('P5 independent motion arithmetic: '+case['id']+' '+key)
        accepted = age <= 10_000_000 and args.get('ir_delta_ns',0) <= 5_000_000
        if 'bundle.delta' in check and check['bundle.delta'] != int(accepted):
            raise ValueError('P5 independent synchronization boundary')

    odds, lo, hi = F(1), F(1), F(1)
    arithmetic = _checks(expected,'S06.arithmetic')
    for name, evidence, bounds in [('p1',F(3,4),(F(7,10),F(4,5))),
                                  ('p2',F(3,4),(F(7,10),F(4,5))),
                                  ('free',F(1,4),(F(1,5),F(3,10)))]:
        odds = max(F(1,9),min(F(9),odds*evidence/(1-evidence)))
        lo = max(F(1,9),min(F(9),lo*bounds[0]/(1-bounds[0])))
        hi = max(F(1,9),min(F(9),hi*bounds[1]/(1-bounds[1])))
        wanted = dict(probability=float(odds/(1+odds)),interval=[str(lo/(1+lo)),str(hi/(1+hi))])
        if (arithmetic[name]['map.probability'] != wanted['probability'] or
                arithmetic[name]['map.interval'] != wanted['interval']):
            raise ValueError('P5 independent bounded odds arithmetic: '+name)
    wire = expected['wire_projections']
    terrain = wire['terrain_result']
    lower, upper = terrain['height_quality.value']
    if not F.from_float(lower) <= F('9.75')+F('2.9') <= F.from_float(upper):
        raise ValueError('P5 lower terrain bound')
    if F.from_float(upper) < F('10.25')+F('3.1'):
        raise ValueError('P5 upper terrain bound')
    for stamp, name, status in [(250_000_000,'edge','occupied'),(250_000_001,'stale','stale')]:
        check = _checks(expected,'S02.ir_gap')[name]
        aged = stamp-150_000_000 > grid['max_age_ns']
        if check['map.state'] != ('stale' if aged else status):
            raise ValueError('P5 independent TTL boundary')
