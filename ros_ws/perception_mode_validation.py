"""Independent receipt checks for unavailable perception modes in an online fixture."""


def validate_unavailable_mode(run_id, mode, count, bundles, observations, events,
                              snapshots, query, graph):
    if mode not in ('disabled', 'research'):
        raise ValueError('expected unavailable perception mode')
    errors = list(graph['errors'])
    expected_clock = 'sim:' + run_id
    if len(bundles) != count or len(observations) != count:
        errors.append('bundle/occupancy count differs from source')
    if snapshots:
        errors.append('unavailable observations produced map snapshots')
    if (query.get('status') != 'unavailable' or query.get('revision') != 0 or
            query.get('probability') is not None or query.get('reason') != 'map_unavailable'):
        errors.append('unavailable observations seeded map evidence')
    if len(events) != count:
        errors.append('map refusal count differs from source')

    expected_reason = 'perception_disabled' if mode == 'disabled' else 'research_preflight_blocked:'
    expected_source = 'derived' if mode == 'disabled' else 'model'
    for index in range(count):
        expected_stamp = index * 50_000_000
        base = 'fixture.radar:%s:%d' % (run_id, index)
        bundle_id = 'sensors.bundle:' + base
        occupancy_id = 'perception.occupancy:' + bundle_id
        if index < len(bundles):
            bundle = bundles[index]
            header = bundle['header']
            if (header['run_id'], header['clock_id'], header['sample_id'],
                    header['timestamp'], header['status']) != (
                    run_id, expected_clock, bundle_id, expected_stamp, 'valid'):
                errors.append('bundle identity, timestamp or status mismatch at %d' % index)
            if any(key in bundle for key in ('lidar', 'target', 'observed_mask')):
                errors.append('online bundle carries training supervision at %d' % index)
        if index < len(observations):
            observation = observations[index]
            header = observation['header']
            reason = header['reason']
            if (header['run_id'], header['clock_id'], header['sample_id'],
                    header['timestamp'], header['status'], header['source_type']) != (
                    run_id, expected_clock, occupancy_id, expected_stamp,
                    'unavailable', expected_source):
                errors.append('occupancy identity, status or source mismatch at %d' % index)
            if not (reason == expected_reason if mode == 'disabled' else
                    reason.startswith(expected_reason) and len(reason) > len(expected_reason)):
                errors.append('perception failure reason missing at %d' % index)
            if (observation['voxels'] or
                    observation['observed_domain_source'] != 'unavailable_no_observation' or
                    observation['context']['reference_timestamp'] != expected_stamp or
                    observation['context']['clock_id'] != expected_clock):
                errors.append('unavailable occupancy has evidence or lost context at %d' % index)
        if index < len(events):
            event = events[index]
            if (event['run_id'], event['clock_id'], event['parent_sample_id'],
                    event['business_timestamp'], event['stage'], event['status'],
                    event['reason']) != (run_id, expected_clock, bundle_id,
                    expected_stamp, 'map_snapshot_publish', 'unavailable',
                    'observation_not_fused'):
                errors.append('map failure receipt mismatch at %d' % index)
    for name, rows, key in (('bundle', bundles, lambda row: row['header']['sample_id']),
                            ('occupancy', observations, lambda row: row['header']['sample_id']),
                            ('map event', events, lambda row: row['parent_sample_id'])):
        if len({key(row) for row in rows}) != len(rows):
            errors.append(name + ' contains duplicate identities')
    return list(dict.fromkeys(errors))
