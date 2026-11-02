"""Independent saved literals and protocol probes, never a simulated trajectory."""
import copy
import json

from sim_motion_fixture import ROOT, expected as old_expected, frame, independent_bytes, wire_object


def expected():
    return json.loads((ROOT / 'tests/fixtures/sim_motion_multiscene_expectations.json').read_text())


def wire_cases(literals):
    rows = []
    for case in literals['cases']:
        identity = 'sw04a-' + case['case_id']
        def f(index):
            value = frame(index, run_id=identity)
            value['state'].update(position=[0., 0., 8.],
                orientation_xyzw=copy.deepcopy(case['quaternion_xyzw']))
            value['angular_velocity_flu'] = [0., 0., 0.]
            return value
        def add(label, kind, value):
            rows.append(dict(id=case['case_id'] + ':' + label, kind=kind, value=value))
        for index in (0, 25):
            add('frame-' + str(index), 'SceneFrame', f(index))
            add('request-' + str(index), 'SceneStepRequest', dict(frame=f(index)))
            stamp = index*4_000_000 if index else None
            add('response-' + str(index), 'SceneStepResponse', dict(accepted=True, reason='',
                applied_frame=f(index), radar_timestamp=stamp, infrared_timestamp=stamp))
        for kind in (1, 2):
            add('ack-' + str(kind), 'SceneCaptureAck', dict(protocol_version=1, run_id=identity,
                clock_id='sim:' + identity, step_index=25, measurement_timestamp=100_000_000,
                sensor_kind=kind, published=True, reason=''))
        if case['case_id'] == 'S08':
            add('fault-frame', 'SceneFrame', f(125))
            add('fault-request', 'SceneStepRequest', dict(frame=f(125)))
            for kind in (1, 2):
                add('fault-ack-' + str(kind), 'SceneCaptureAck', dict(protocol_version=1, run_id=identity,
                    clock_id='sim:' + identity, step_index=125, measurement_timestamp=500_000_000,
                    sensor_kind=kind, published=True, reason=''))
            # ACK existed on the wire; the planned transaction deliberately ignores Radar ACK.
            add('fault-response', 'SceneStepResponse', dict(accepted=False, reason='scene_radar_timeout',
                applied_frame=f(125), radar_timestamp=None, infrared_timestamp=500_000_000))
    return rows


def expected_wire(row, layout):
    return independent_bytes(row['kind'], wire_object(row['kind'], row['value'], layout), layout)


def layout():
    return old_expected()['layout']


def source_cases(literals):
    rows = []
    ref = literals['source_reference']
    for case in literals['cases']:
        x, y, z, w = case['quaternion_xyzw']
        enu = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
               [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
               [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
        # Equator/zero-longitude ECEF axes: x=up, y=east, z=north.
        ecef = [[row[i]*sign for i, sign in enumerate((1, -1, -1))]
                for row in (enu[2], enu[0], enu[1])]
        initial = dict(step_index=0, sim_time_s=0., ecef_ft=ref['ecef_origin_ft'],
            R_ecef_frd=sum(ecef, []), uvw_ftps=ref['uvw_ftps'], pqr_radps=ref['pqr_radps'])
        moved = copy.deepcopy(initial)
        moved.update(step_index=1, sim_time_s=.004,
            ecef_ft=[a+b for a, b in zip(ref['ecef_origin_ft'], ref['ecef_delta_ft'])])
        rows.append(dict(case_id=case['case_id'], initial=copy.deepcopy(initial), sample=moved))
    return rows
