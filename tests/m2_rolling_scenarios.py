"""Declared motion scenarios and independent expected states for M2-SW-03."""
from m2_motion_fixture import motion_observation
from m2_oracle import expected_timed_sequence


def scenarios(spec, run_id):
    initial, shifted, distant = list(spec['origin']), [-15.5, -8., -4.], [24., -8., -4.]
    timed_kinds = ('occupied', 'empty', 'occupied', 'neutral', 'empty', 'occupied')
    stamps = (10_000_000, 20_000_000, 30_000_000, 130_000_000, 131_000_000, 140_000_000)
    references = expected_timed_sequence(timed_kinds, stamps, spec)
    timed = []
    for index, (kind, stamp, reference) in enumerate(zip(timed_kinds, stamps, references)):
        row = motion_observation(spec, run_id + ':timed', index, kind=kind,
            body=(0., 0., 0.) if index == 0 else (.5, 0., 0.),
            origin=(-15., -8., -4.) if index == 2 else None, stamp=stamp)
        timed.append(dict(observation=row, expected=dict(reference,
            origin=initial if index == 0 else shifted,
            revision=(1, 2, 3, 3, 3, 4)[index], status='stale' if index == 4 else 'occupied',
            map_timestamp=(10_000_000, 10_000_000, 30_000_000, 30_000_000, 30_000_000, 140_000_000)[index]),
            query_point=[8.25, .25, .25]))

    eviction = []
    for index, kind in enumerate(('occupied', 'occupied', 'empty', 'empty', 'occupied')):
        far = index == 2
        row = motion_observation(spec, run_id + ':eviction', index, kind=kind,
            body=(40., 0., 0.) if far else (0., 0., 0.), origin=distant if far else None)
        probability = (.75, .9, None, None, .75)[index]
        eviction.append(dict(observation=row, expected=dict(probability=probability,
            observed=probability is not None, last_observed_timestamp=(10_000_000, 20_000_000,
                None, None, 50_000_000)[index], origin=distant if far else initial,
            revision=index + 1, status='unknown' if index in (2, 3) else 'occupied',
            map_timestamp=(10_000_000, 20_000_000, 20_000_000, 20_000_000, 50_000_000)[index]),
            query_point=[40.25 if far else 8.25, .25, .25]))

    gaps = []
    for index, (kind, stamp) in enumerate(zip(('empty', 'occupied', 'unavailable', 'occupied'),
                                              (10_000_000, 20_000_000, 300_000_000, 310_000_000))):
        row = motion_observation(spec, run_id + ':gap', index, kind=kind,
            body=(40., 0., 0.) if index == 2 else (.5, 0., 0.),
            origin=distant if index == 2 else None, stamp=stamp)
        if index == 2:
            row['context']['T_mapping_body_status'] = 'unavailable'
            row['context']['T_mapping_body'] = [0.] * 16
        gaps.append(dict(observation=row, expected=dict(probability=None if index == 0 else .75,
            observed=index != 0, last_observed_timestamp=(None, 20_000_000, 20_000_000, 310_000_000)[index],
            origin=shifted, revision=(1, 2, 2, 3)[index],
            status=('unavailable', 'occupied', 'stale', 'occupied')[index],
            map_timestamp=(0, 20_000_000, 20_000_000, 310_000_000)[index]),
            query_point=[8.25, .25, .25]))
    return [dict(name='overlap_and_ttl', steps=timed), dict(name='eviction_and_return', steps=eviction),
            dict(name='unavailable_and_recovery', steps=gaps)]
