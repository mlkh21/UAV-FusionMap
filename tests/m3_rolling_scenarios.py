"""Declared motion/coverage expectations with independent scalar interval arithmetic."""
import copy
import math

from m3_fixture import interval_quality
from m3_motion_fixture import event, motion_observation
from m3_oracle import expected_sequence


def _unknown(status='unknown'):
    return dict(probability=None, interval=None, quality_available=False, observed=False,
                last_observed_timestamp=None, status=status)


def _step(row, origin, revision, map_time, cells, reference, *, changed=True, point=(8.25, .25, .25)):
    return dict(observation=row, expected=dict(origin=list(origin), revision=revision,
        map_timestamp=map_time, cell_count=cells, changed=changed), queries=[dict(point=list(point),
        timestamp=row['header']['timestamp'], expected=dict(reference, revision=revision))])


def scenarios(spec, run_id):
    initial, shifted, distant = list(spec['arithmetic']['origin']), [-15.5, -8., -4.], [24., -8., -4.]
    kinds = ('occupied', 'occupied', 'free', 'occupied', 'neutral', 'empty', 'free')
    stamps = (10_000_000, 20_000_000, 30_000_000, 40_000_000, 140_000_000, 140_000_001, 150_000_000)
    events = [event(spec, i, kind, None if i == 2 else 'default', stamp)
              for i, (kind, stamp) in enumerate(zip(kinds, stamps))]
    references = expected_sequence(events, spec['arithmetic'])
    overlap = []
    for i, (kind, stamp, reference) in enumerate(zip(kinds, stamps, references)):
        body = ((0., 0., 0.), (.5, 0., 0.), (1., 0., 0.), (-.5, 0., 0.),
                (.5, 0., 0.), (.5, 0., 0.), (.5, 0., 0.))[i]
        origin = (initial, shifted, [-15., -8., -4.], [-16.5, -8., -4.], shifted, shifted, shifted)[i]
        row = motion_observation(spec, run_id + ':overlap', i, kind,
            bounds=None if i == 2 else 'default', stamp=stamp, body=body,
            yaw=math.pi/2 if i == 1 else 0., origin=(-15., -8., -4.) if i == 1 else None)
        step = _step(row, origin, (1, 2, 3, 4, 5, 5, 6)[i],
                     (10_000_000, 20_000_000, 30_000_000, 40_000_000, 40_000_000, 40_000_000, 150_000_000)[i],
                     1, reference, changed=i != 5)
        if i == 4:
            step['queries'].append(dict(point=[8.25, .25, .25], timestamp=100_000_000,
                expected=dict(_unknown('unavailable'), revision=5, reason='query_before_latest_map_time')))
        overlap.append(step)

    eviction = []
    for i, kind in enumerate(('occupied', 'occupied', 'empty', 'empty', 'occupied')):
        far = i == 2
        row = motion_observation(spec, run_id + ':eviction', i, kind,
            bounds=None if i == 0 else 'default', body=(40., 0., 0.) if far else (.5 if i == 1 else 0., 0., 0.),
            origin=distant if far else None)
        reference = _unknown() if i in (2, 3) else dict(probability=.9 if i == 1 else .75,
            interval=[.7, .8] if i == 4 else None, quality_available=i == 4, observed=True,
            last_observed_timestamp=(i + 1) * 10_000_000, status='occupied')
        eviction.append(_step(row, distant if far else shifted if i == 1 else initial, i + 1,
            (10_000_000, 20_000_000, 20_000_000, 20_000_000, 50_000_000)[i],
            0 if i in (2, 3) else 1, reference, point=(40.25 if far else 8.25, .25, .25)))

    kinds, stamps = ('empty', 'occupied', 'unavailable', 'occupied'), (10_000_000, 20_000_000, 300_000_000, 310_000_000)
    references = expected_sequence([event(spec, i, kind, stamp=stamp)
        for i, (kind, stamp) in enumerate(zip(kinds, stamps))], spec['arithmetic'])
    gaps = []
    for i, (kind, stamp, reference) in enumerate(zip(kinds, stamps, references)):
        row = motion_observation(spec, run_id + ':gap', i, kind, stamp=stamp,
            body=(40., 0., 0.) if i == 2 else (.5, 0., 0.), origin=distant if i == 2 else None)
        if i == 2:
            row['context']['T_mapping_body_status'] = 'unavailable'
            row['context']['T_mapping_body'] = [0.] * 16
        gaps.append(_step(row, shifted, (1, 2, 2, 3)[i], (0, 20_000_000, 20_000_000, 310_000_000)[i],
                          0 if i == 0 else 1, reference, changed=i != 2))

    bounded_spec = copy.deepcopy(spec)
    bounded_spec['arithmetic'].update(max_active_cells=2, identity_history_limit=3)
    first_events = [event(spec, i) for i in range(80)]
    second_events = [event(spec, i, bounds=None if i % 4 == 0 else 'default') for i in range(80)]
    first_expected = expected_sequence(first_events, spec['arithmetic'])
    second_expected = expected_sequence(second_events, spec['arithmetic'])
    bounded = []
    for i in range(80):
        row = motion_observation(spec, run_id + ':bounded', i, body=(.5 * (i % 2), 0., 0.),
            points=((8.25, .25, .25), (9.25, .25, .25), (10.25, .25, .25)))
        if i % 4 == 0:
            row['voxels'][1]['uncertainty'] = interval_quality(spec, None)
        step = _step(row, shifted if i % 2 else initial, i + 1, row['header']['timestamp'], 2, first_expected[i])
        step['queries'].extend([dict(point=[9.25, .25, .25], timestamp=row['header']['timestamp'],
                                    expected=dict(second_expected[i], revision=i + 1)),
                               dict(point=[10.25, .25, .25], timestamp=row['header']['timestamp'],
                                    expected=dict(_unknown(), revision=i + 1))])
        bounded.append(step)
    recent = copy.deepcopy(bounded[-1]['observation'])
    conflict = copy.deepcopy(recent)
    conflict['voxels'][0]['uncertainty']['value'][0] = .6
    foreign = copy.deepcopy(recent)
    foreign['header']['run_id'] = 'foreign'
    probes = [dict(observation=recent, outcome='not_fused'), dict(observation=conflict, outcome='rejected'),
              dict(observation=bounded[0]['observation'], outcome='rejected'),
              dict(observation=foreign, outcome='rejected')]
    return [dict(name='overlap_missing_ttl', spec=spec, steps=overlap, probes=[]),
            dict(name='eviction_return', spec=spec, steps=eviction, probes=[]),
            dict(name='invalid_transform_gap', spec=spec, steps=gaps, probes=[]),
            dict(name='bounded_mixed_80', spec=bounded_spec, steps=bounded, probes=probes)]
