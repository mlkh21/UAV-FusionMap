"""Independent literals, analytic expectations and struct layout, without ROS imports."""
import copy
from fractions import Fraction as F
import json
import math
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]


def expected():
    return json.loads((ROOT / 'tests/fixtures/sim_motion_expectations.json').read_text())


def frame(index=25, height=8., run_id='motion-fixture'):
    return dict(protocol_version=1, step_index=index, registration_id='jsbsim_cg_to_scene_enu_v1',
        angular_velocity_flu=[0., 0., 1.], state=dict(
        header=dict(schema_version='0.1', timestamp=index * 4_000_000, run_id=run_id,
            clock_id='sim:' + run_id, sample_id='scene.frame:%s:%d' % (run_id, index),
            frame_id='scene_world', source_type='simulation', status='valid', reason=''),
        position=[10., 20., height], orientation_xyzw=[0., 0., 0., 1.], linear_velocity=[5., 0., 0.],
        body_frame_id='base_link', velocity_frame_id='base_link', state_source='ground_truth',
        quality=dict(confidence=None, uncertainty=dict(status='unavailable', kind='', value=None,
            unit='', source='jsbsim_scene_truth_no_covariance_v1'))))


def ack(index=25, sensor=1, published=True):
    return dict(protocol_version=1, run_id='motion-fixture', clock_id='sim:motion-fixture',
        step_index=index, measurement_timestamp=index * 4_000_000, sensor_kind=sensor,
        published=published, reason='' if published else 'scene_capture_time_mismatch')


def response(index=25, accepted=True, applied=True, height=8.):
    value = dict(accepted=accepted, reason='' if accepted else 'scene_ir_timeout',
        applied_frame=frame(index, height) if applied else None, radar_timestamp=None, infrared_timestamp=None)
    if applied and index > 0 and index % 25 == 0:
        value['radar_timestamp'] = index * 4_000_000
        if accepted:
            value['infrared_timestamp'] = index * 4_000_000
    return value


def cases():
    rows = [dict(id='frame-' + str(c['step_index']), kind='SceneFrame', value=frame(c['step_index']))
            for c in expected()['time_cases']]
    rows += [dict(id='height-' + str(h), kind='SceneFrame', value=frame(height=h)) for h in (0., -2.)]
    rows += [dict(id='request-' + str(i), kind='SceneStepRequest', value=dict(frame=frame(i))) for i in (0, 25)]
    rows += [dict(id='ack-' + str(s), kind='SceneCaptureAck', value=ack(sensor=s)) for s in (1, 2)]
    failed = ack(published=False)
    failed['measurement_timestamp'] = 0
    rows.append(dict(id='ack-failure-zero-time', kind='SceneCaptureAck', value=failed))
    answers = [response(0), response(1), response(25), response(height=-2.), response(height=0.),
               response(accepted=False, applied=False), response(accepted=False)]
    rows += [dict(id=name, kind='SceneStepResponse', value=value)
             for name, value in zip(expected()['response_cases'], answers)]
    return rows


def source_sample(index=1):
    return dict(step_index=index, sim_time_s=index * .004, ecef_ft=[20_000_000., 0., 0.],
                R_ecef_frd=[1., 0., 0., 0., 1., 0., 0., 0., 1.], uvw_ftps=[5., 0., 0.], pqr_radps=[0., 0., 1.])


def verify_analytic(literals):
    for row in literals['coordinate_cases']:
        i, e = row['input'], row['expected']
        if row['id'] == 'ecef_equator_nonzero':
            delta = [F(str(a)) - F(str(b)) for a, b in zip(i['ecef_ft'], i['ecef_origin_ft'])]
            result = [float(F(str(p)) + F('0.3048') * d) for p, d in zip(i['scene_anchor_m'], [delta[1], delta[2], delta[0]])]
            assert result == e['scene_position_m']
        elif row['id'] == 'ned_frd_axes':
            n, b = i['ned_m'], i['frd_mps']
            assert [n[1], n[0], -n[2]] == e['enu_m'] and [b[0], -b[1], -b[2]] == e['flu_mps']
        elif row['id'] == 'yaw_and_mount':
            assert [i['body_m'][0], float(F(str(i['body_m'][1])) + F(str(i['mount_m'][0]))), i['body_m'][2]] == e['radar_m']
            assert all(abs(a - b) < 1e-15 for a, b in zip(e['quaternion_xyzw'], [0, 0, math.sqrt(.5), math.sqrt(.5)]))
        elif 'doppler' in row['id'] or row['id'] == 'angular_lever_arm':
            v, w, p = [[F(str(x)) for x in i[k]] for k in ('velocity_mps', 'omega_radps', 'mount_m')]
            cross = [w[1]*p[2]-w[2]*p[1], w[2]*p[0]-w[0]*p[2], w[0]*p[1]-w[1]*p[0]]
            speed = [a + b for a, b in zip(v, cross)]
            assert [float(x) for x in speed] == e['sensor_velocity_mps']
            assert float(-sum(x * F(str(y)) for x, y in zip(speed, i['los']))) == e['doppler_mps']
        else:
            assert abs(float(F('0.3048')) * math.sqrt(2) - e['scene_delta_m'][2]) < 1e-15
            phi = math.radians(i['geocentric_latitude_deg'])
            assert abs(.3048 * (-math.sin(phi) + math.cos(phi))) > 1e-4
    for row in literals['time_cases']:
        assert row['timestamp'] == row['step_index'] * 4_000_000
        assert row['capture'] == (row['step_index'] > 0 and row['step_index'] % 25 == 0)


def zero(kind, layout):
    match = re.fullmatch(r'(.+)\[(\d*)\]', kind)
    if match:
        base, count = match.groups()
        return [zero(base, layout) for _ in range(int(count) if count else 0)]
    if kind in layout:
        return {field: zero(t, layout) for field, t in (pair.split(':') for pair in layout[kind].split())}
    return '' if kind == 'string' else False if kind == 'bool' else 0


def wire_object(kind, value, layout):
    value = copy.deepcopy(value)
    def state(s):
        s['header']['source_type'] = 0
        s['header']['status'] = 0
        s['state_source'] = 0
        s['quality'] = dict(confidence_available=False, confidence=0., uncertainty=dict(
            s['quality']['uncertainty'], status=0, value=[]))
        return s
    def f(v):
        v['state'] = state(v['state'])
        return v
    if kind == 'SceneFrame':
        return f(value)
    if kind == 'SceneStepRequest':
        return dict(frame=f(value['frame']))
    if kind == 'SceneCaptureAck':
        return value
    return dict(accepted=value['accepted'], reason=value['reason'],
        has_applied_frame=value['applied_frame'] is not None,
        applied_frame=f(value['applied_frame']) if value['applied_frame'] is not None else zero('SceneFrame', layout),
        radar_captured=value['radar_timestamp'] is not None, radar_timestamp=value['radar_timestamp'] or 0,
        infrared_captured=value['infrared_timestamp'] is not None, infrared_timestamp=value['infrared_timestamp'] or 0)


def independent_bytes(kind, value, layout):
    match = re.fullmatch(r'(.+)\[(\d*)\]', kind)
    if match:
        base, count = match.groups()
        assert not count or len(value) == int(count)
        return (b'' if count else struct.pack('<I', len(value))) + b''.join(independent_bytes(base, v, layout) for v in value)
    if kind in layout:
        return b''.join(independent_bytes(t, value[f], layout) for f, t in
                        (pair.split(':') for pair in layout[kind].split()))
    if kind == 'string':
        raw = value.encode('utf-8')
        return struct.pack('<I', len(raw)) + raw
    return struct.pack('<' + dict(bool='B', uint8='B', int64='q', uint64='Q', float32='f', float64='d')[kind], value)
