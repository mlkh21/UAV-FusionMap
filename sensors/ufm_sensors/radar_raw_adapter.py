"""Explicit zero-duration fixture Radar adaptation, with no device assumptions."""
import math


def _semantics(profile):
    required = ('mode', 'frame_id', 'x_field', 'y_field', 'z_field',
                'position_unit', 'doppler_field', 'doppler_unit', 'doppler_positive',
                'doppler_reference', 'power_field', 'power_quantity', 'power_unit',
                'scan_reference')
    if not isinstance(profile, dict) or any(k not in profile for k in required):
        raise ValueError('explicit Radar fixture field semantics required')
    if (profile['mode'] != 'fixture_only' or profile['scan_reference'] != 'midpoint'
            or profile['position_unit'] != 'm'
            or not isinstance(profile['frame_id'], str) or not profile['frame_id'].strip()
            or any(not isinstance(profile[k], str) or not profile[k].strip()
                   for k in ('x_field', 'y_field', 'z_field'))
            or len({profile[k] for k in ('x_field', 'y_field', 'z_field')}) != 3):
        raise ValueError('unsupported fixture geometry or scan semantics')
    fields = [profile[k] for k in ('x_field', 'y_field', 'z_field',
                                    'doppler_field', 'power_field') if profile[k] is not None]
    if any(not isinstance(field, str) or not field.strip() for field in fields) or len(set(fields)) != len(fields):
        raise ValueError('Radar field mapping must be unique and named')
    if profile['doppler_reference'] != 'sensor_relative':
        raise ValueError('ego compensated Doppler provenance not available')
    if profile['doppler_field'] is None:
        if (profile['doppler_unit'], profile['doppler_positive']) != ('unavailable', 'unavailable'):
            raise ValueError('unavailable Doppler must be declared')
    elif (profile['doppler_unit'] != 'm/s'
          or profile['doppler_positive'] not in ('away', 'toward')):
        raise ValueError('Doppler unit and positive direction required')
    if profile['power_field'] is None:
        if (profile['power_quantity'], profile['power_unit']) != ('unavailable', 'unavailable'):
            raise ValueError('unavailable power must be declared')
    elif ((profile['power_quantity'], profile['power_unit']) not in (
            ('signal_to_noise_ratio', 'dB'), ('uncalibrated_intensity', 'arbitrary'))):
        raise ValueError('unsupported fixture power semantics')
    return fields


def adapt_radar_rows(rows, profile, identity):
    """Adapt decoded fixture rows; never invent device clock mappings or per-point time."""
    fields = _semantics(profile)
    if not isinstance(identity, dict):
        raise ValueError('Radar acquisition identity required')
    run_id = identity.get('run_id')
    sample_id = identity.get('sample_id')
    timestamp = identity.get('timestamp_ns')
    if (not isinstance(run_id, str) or not run_id.strip()
            or not isinstance(sample_id, str) or not sample_id.strip()
            or identity.get('clock_id') != 'sim:'+run_id
            or type(timestamp) is not int or not 0 <= timestamp < 2**63
            or type(identity.get('scan_start_ns')) is not int
            or type(identity.get('scan_end_ns')) is not int
            or identity['scan_start_ns'] != timestamp
            or identity['scan_end_ns'] != timestamp):
        raise ValueError('fixture run/clock or zero-duration scan mismatch')
    points = []
    for row in rows:
        if any(k not in row or isinstance(row[k], bool)
               or not isinstance(row[k], (int, float)) or not math.isfinite(row[k])
               for k in fields):
            raise ValueError('Radar point has missing or nonfinite mapped field')
        position = [float(row[profile[axis+'_field']]) for axis in ('x', 'y', 'z')]
        doppler = (float(row[profile['doppler_field']]) if profile['doppler_field'] is not None else 0.0)
        if profile['doppler_positive'] == 'toward':
            doppler = -doppler
        power = (float(row[profile['power_field']]) if profile['power_field'] is not None else 0.0)
        points.append(dict(x=position[0], y=position[1], z=position[2],
                           doppler=doppler, power=power,
                           doppler_available=profile['doppler_field'] is not None,
                           power_available=profile['power_field'] is not None))
    return dict(header=dict(schema_version='0.1', timestamp=timestamp,
                            run_id=run_id, clock_id=identity['clock_id'],
                            sample_id=sample_id, frame_id=profile['frame_id'],
                            source_type='fixture', status='valid', reason=''),
                points=points, scan_start=timestamp, scan_end=timestamp,
                power_quantity=profile['power_quantity'], power_unit=profile['power_unit'],
                doppler_reference=profile['doppler_reference'],
                quality=dict(confidence=None, uncertainty=dict(status='unavailable', kind='',
                    value=None, unit='', source='fixture; measurement uncertainty unavailable')))
