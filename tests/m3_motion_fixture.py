"""Test-only explicit M3 world-point observations, independent of map geometry code."""
from fractions import Fraction

from m2_motion_fixture import motion_observation as arithmetic_motion
from m3_fixture import interval_quality


def event(spec, sequence, kind='occupied', bounds='default', stamp=None):
    arithmetic = spec['arithmetic']
    if kind in ('occupied', 'free'):
        probability = str(Fraction(str(arithmetic[kind + '_probability'])))
        if bounds == 'default':
            bounds = [str(Fraction(str(value))) for value in spec['evidence_intervals'][kind]]
    elif kind in ('neutral', 'unobserved'):
        probability = '1/2'
        if bounds == 'default':
            bounds = ['1/2', '1/2'] if kind == 'neutral' else None
    else:
        probability = None
        if bounds == 'default':
            bounds = None
    return dict(kind=kind, probability=probability, bounds=bounds,
                timestamp=(sequence + 1) * arithmetic['sample_period_ns'] if stamp is None else stamp)


def motion_observation(spec, run_id, sequence, kind='occupied', bounds='default', stamp=None,
                       body=(0., 0., 0.), points=((8.25, .25, .25),), yaw=0., origin=None):
    descriptor = event(spec, sequence, kind, bounds, stamp)
    row = arithmetic_motion(spec['arithmetic'], run_id, sequence, kind, body=body, points=points,
                            yaw=yaw, origin=origin, stamp=descriptor['timestamp'])
    row['header']['sample_id'] = 'perception.occupancy:m3-motion:%s:%d' % (run_id, sequence)
    for voxel in row['voxels']:
        voxel['uncertainty'] = interval_quality(spec, descriptor['bounds'])
    return row
