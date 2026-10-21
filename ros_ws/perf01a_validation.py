"""固定场景的独立接收校验，不依据生产者声明降低预期样本数。"""


def expected_sequences(count, profile):
    window = set(range(profile.get('start_sequence', 0), profile.get('stop_sequence', 0)))
    rejected = window if profile.get('expected_rejection') else set()
    accepted = [i for i in range(count) if i not in rejected]
    infrared = [i for i in range(count) if not (profile['fault'] == 'ir_missing' and i in window)]
    return dict(state=list(range(count)), radar=list(range(count)), infrared=infrared,
                bundle=accepted, occupancy=accepted, map=accepted)


def validate_receipts(records, count, profile, run_id, period_ns, observer_mode='full'):
    if observer_mode not in ('full', 'light'):
        raise ValueError('unknown observer mode')
    errors = []
    sequences = expected_sequences(count, profile)
    width, height = profile['ir_resolution']
    for key, rows in records.items():
        expected = sequences[key]
        if len(rows) != len(expected) or len({r['sample_id'] for r in rows}) != len(expected):
            errors.append(key + ': count or identity mismatch')
        if any(r['run_id'] != run_id or r['status'] != 0 for r in rows):
            errors.append(key + ': invalid run/status')
        stamps = []
        for sequence in expected:
            stamp = sequence * period_ns
            if (key == 'infrared' and profile['fault'] == 'ir_offset' and
                    profile['start_sequence'] <= sequence < profile['stop_sequence']):
                stamp += profile['ir_offset_ns']
            stamps.append(stamp)
        if [r['timestamp'] for r in rows] != stamps:
            errors.append(key + ': timestamps differ')
        for row, sequence in zip(rows, expected):
            base = 'fixture.radar:%s:%d' % (run_id, sequence)
            bundle = 'sensors.bundle:' + base
            identity = {'state': 'fixture.state:%s:%d' % (run_id, sequence), 'radar': base,
                        'infrared': 'fixture.infrared:%s:%d' % (run_id, sequence),
                        'bundle': bundle, 'occupancy': 'perception.occupancy:' + bundle}
            if key != 'map' and row['sample_id'] != identity[key]:
                errors.append(key + ': unexpected identity')
            if key in ('infrared', 'bundle'):
                if row['image_shape'] != [width, height] or row['pixel_count'] != width * height:
                    errors.append(key + ': image dimensions differ')
                if observer_mode == 'full' and (row.get('pixel_min') != .5 or row.get('pixel_max') != .5):
                    errors.append(key + ': image payload differs')
            if key == 'bundle':
                if row['radar_id'] != base or row['infrared_id'] != identity['infrared']:
                    errors.append('bundle: input identity differs')
                delta = abs(profile['ir_offset_ns']) if (profile['fault'] == 'ir_offset' and
                    profile['start_sequence'] <= sequence < profile['stop_sequence']) else 0
                if row['radar_ir_delta_ns'] != delta or row['pose_age_ns'] != 0:
                    errors.append('bundle: synchronization metrics differ')
            if key == 'map':
                if (row['cell_count'] != 1 or not row['cells'][0]['observed'] or
                        row['cells'][0]['timestamp'] != row['timestamp']):
                    errors.append('map: incorrect observed evidence')
    if [r['revision'] for r in records['map']] != list(range(1, len(sequences['map']) + 1)):
        errors.append('map revision sequence differs')
    return list(dict.fromkeys(errors))
