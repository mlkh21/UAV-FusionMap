"""Offline synthetic public-chain checks; no actual FDM, ROS graph or camera."""
import copy
import io

import numpy as np
from scipy.spatial.transform import Rotation

from sim_motion_multiscene_oracle import fdm_pose, rotation_from_ic


def verify_sources(rows, literals, profile):
    from ufm_simulation.scene_motion import SceneRegistration
    ref = literals['source_reference']
    assert len(rows) == len(literals['cases']) == 9
    results = []
    for row, case in zip(rows, literals['cases']):
        assert row['case_id'] == case['case_id']
        before = copy.deepcopy(row)
        registration = SceneRegistration(row['initial'], ref['latitude_rad'], ref['longitude_rad'], profile)
        for label in ('initial', 'sample'):
            raw = row[label]
            actual = registration.convert(raw, 'sw04a-' + case['case_id'])
            position, rotation = fdm_pose(raw, ref['ecef_origin_ft'], ref['latitude_rad'], ref['longitude_rad'])
            np.testing.assert_allclose(actual['state']['position'], position, rtol=0, atol=1e-12)
            np.testing.assert_allclose(Rotation.from_quat(actual['state']['orientation_xyzw']).as_matrix(),
                rotation, rtol=0, atol=1e-12)
            np.testing.assert_allclose(rotation, rotation_from_ic(case['ic_degrees']), rtol=0, atol=1e-12)
            if label == 'sample':
                np.testing.assert_allclose(position, ref['position_m'], rtol=0, atol=1e-12)
            np.testing.assert_allclose(actual['state']['linear_velocity'], ref['velocity_flu_mps'], rtol=0, atol=1e-12)
            np.testing.assert_allclose(actual['angular_velocity_flu'], ref['omega_flu_radps'], rtol=0, atol=1e-12)
            assert actual['state']['header']['timestamp'] == raw['step_index']*4000000
            results.append(dict(case_id=case['case_id'], probe=label, position=position))
        assert row == before
    assert len(results) == 18
    return results


def verify_empty_semantics(literals, run=None):
    from test_sensor_scene import SensorSceneTest
    from ufm_sensors.scene_stream import SceneStream
    from ufm_perception.placeholder import placeholder_infer
    from ufm_mapping.factory import create_map
    from ufm_ros_contract import perf01a_codec as codec
    from ufm_ros_contract.query_codec import from_ros_query_result, to_ros_query_result
    helper = SensorSceneTest()
    helper.setUp()
    helper.profile['map'].update(literals['wide_map'])
    settings = dict(helper.profile['map'], free_threshold=.3, occupied_threshold=.7)
    wire = []
    def roundtrip(kind, value, encode, decode, exact=True):
        message = encode(value)
        stream = io.BytesIO()
        message.serialize(stream)
        raw = stream.getvalue()
        decoded = decode(type(message)().deserialize(raw))
        again = io.BytesIO()
        encode(decoded).serialize(again)
        assert raw == again.getvalue()
        if exact:
            assert decoded == value, kind
        if run is not None:
            with (run / ('public-empty-%02d.bin' % len(wire))).open('xb') as output:
                output.write(raw)
        wire.append(dict(kind=kind, bytes=len(raw)))
        return decoded
    def query(local, stamp, point, old=False):
        identity = 'previous-run' if old else 'r'
        return local.query(local.map_id, 'odom', identity, 'sim:'+identity, stamp, point, 500000000)
    def observation(stream, stamp, empty):
        stream.set_clock(stamp)
        state, radar, ir = helper.inputs(stamp)
        state['position'] = [0., 0., 8.]
        if empty:
            radar['points'] = []
        for kind, value in (('state', state), ('radar', radar), ('infrared', ir)):
            stream.add(kind, value)
        bundle, = stream.ready()
        assert bundle['radar_ir_delta_ns'] == bundle['pose_age_ns'] == 0
        obs = placeholder_infer(bundle, **{k:settings[k] for k in ('resolution','shape','origin')})
        assert obs['header']['status'] == 'valid'
        return radar, obs

    local = create_map('latest', settings)
    point = [0., 0., 8.]
    queries = {'new_run':query(local, 0, point)}
    stream = SceneStream('r', helper.profile, require_exact_pose=True)
    for index in range(1, 11):
        radar, obs = observation(stream, index*100000000, True)
        roundtrip('RadarFrame', radar, codec.to_ros_radar, codec.from_ros_radar)
        decoded = roundtrip('OccupancyObservation', obs, codec.to_ros_occupancy, codec.from_ros_occupancy)
        assert decoded['voxels'] == []
        local.update(decoded)
        snapshot = local.snapshot()
        roundtrip('MapSnapshot', snapshot, codec.to_ros_snapshot, codec.from_ros_snapshot)
        assert snapshot['revision'] == index and snapshot['cells'] == []
        assert snapshot['header']['status'] == 'valid'
    queries['ten_empty'] = query(local, 1000000000, point)
    queries['old_identity'] = query(local, 1000000000, point, old=True)

    history = create_map('latest', settings)
    stream = SceneStream('r', helper.profile, require_exact_pose=True)
    for index in range(1, 10):
        _, obs = observation(stream, index*100000000, index >= 5)
        history.update(obs)
    snapshot = history.snapshot()
    assert snapshot['revision'] == 9 and snapshot['header']['timestamp'] == 900000000
    assert snapshot['cells'] and all(c['last_observed_timestamp'] == 400000000 for c in snapshot['cells'])
    cell = snapshot['cells'][0]
    point = [snapshot['origin'][a]+(cell['index'][a]+.5)*snapshot['resolution'][a] for a in range(3)]
    for probe in literals['queries']:
        name = probe['id']
        if name not in queries:
            queries[name] = query(history, probe['query_ns'], point)
        result = queries[name]
        assert (result['status'], result['reason'], result['revision']) == (
            probe['status'], probe['reason'], probe['revision']), name
        assert result['query_timestamp'] == probe['query_ns']
        wanted_cell_time = probe['cell_ns'] if result['status'] in ('occupied','stale') else None
        assert result['last_observed_timestamp'] == wanted_cell_time
        assert result['confidence'] is None and result['status'] != 'free'
        decoded = roundtrip('MapQueryResult', result, to_ros_query_result, from_ros_query_result, exact=False)
        for key in ('status', 'reason', 'revision', 'last_observed_timestamp', 'observed', 'index'):
            assert decoded[key] == result[key]
        if result['probability'] is not None:
            assert abs(decoded['probability'] - .9) < 1e-6
        else:
            assert decoded['probability'] is None
        assert decoded['uncertainty']['status'] == 'unavailable'
    return dict(queries=queries, historical_header_ns=snapshot['header']['timestamp'],
        historical_cell_ns=cell['last_observed_timestamp'], wire=wire,
        actual_sensor_or_ros=False)
