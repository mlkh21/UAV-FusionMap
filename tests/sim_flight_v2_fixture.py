"""Test-only literal inputs and independent ROS struct packing, no flight imports."""
import copy
import json
from pathlib import Path

from sim_motion_fixture import expected as old_expected, independent_bytes, wire_object

ROOT = Path(__file__).resolve().parents[1]


def expected():
    return json.loads((ROOT / 'tests/fixtures/sim_flight_v2_expectations.json').read_text())


def frame(step=0):
    value = copy.deepcopy(expected()['frame'])
    value['step_index'] = step
    value['state']['header']['timestamp'] = step * 4_000_000
    value['state']['header']['sample_id'] = 'scene.frame:flight-v2:%d' % step
    return value


def ack(step=7525, sensor=1, published=True):
    return dict(protocol_version=2, run_id='flight-v2', clock_id='sim:flight-v2',
                step_index=step, measurement_timestamp=step * 4_000_000,
                sensor_kind=sensor, published=published, reason='' if published else 'scene_capture_timeout')


def response(step=0, accepted=True, partial=False):
    # Expectations follow the saved literal sampling table, not the implementation.
    capture = step in expected()['capture_steps']
    return dict(accepted=accepted, reason='' if accepted else 'scene_ir_timeout',
        applied_frame=frame(step), radar_timestamp=step * 4_000_000 if capture else None,
        infrared_timestamp=step * 4_000_000 if capture and not partial else None)


def cases():
    rows = []
    for step, _, _ in expected()['time_cases']:
        rows.extend([dict(kind='SceneFrame', value=frame(step)),
                     dict(kind='SceneStepRequest', value=dict(frame=frame(step))),
                     dict(kind='SceneStepResponse', value=response(step))])
    for step in expected()['capture_steps']:
        for sensor in (1, 2):
            rows.append(dict(kind='SceneCaptureAck', value=ack(step, sensor)))
    rows.extend([dict(kind='SceneCaptureAck', value=ack(published=False)),
                 dict(kind='SceneStepResponse', value=response(7525, False, True)),
                 dict(kind='SceneStepResponse', value=response(1, False))])
    return rows


def packed(kind, value):
    layout = old_expected()['layout']
    return independent_bytes(kind, wire_object(kind, value, layout), layout)


def replace(value, path, item):
    result = copy.deepcopy(value)
    node = result
    keys = path.split('.')
    for key in keys[:-1]:
        node = node[key]
    node[keys[-1]] = item
    return result
