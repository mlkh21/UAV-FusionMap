"""Independent tests-only native texts and event envelopes."""
import copy
import json

from sim_flight_probe_fixture import BINARY_DIR, ROOT, RUN_ID, layouts, receipt


def expected():
    return json.loads((ROOT/'tests/fixtures/sim_flight_diagnostic_cases.json').read_text())


def event(index=1):
    row = receipt(index)
    for key in ('observed', 'reason', 'value'):
        row.pop(key)
    row['schema_version'] = 'sim_flight_uorb_diagnostic.v1'
    if index <= 18:
        row.update(stdout=expected()['missing_text'], observation=expected()['missing_result'])
    else:
        value = expected()['parameters'][row['query']['name']]
        row['observation'] = dict(state='payload', reason='', instances=[], parameter=dict(integer=value))
    return row


def attitude(instance=None):
    return dict(instance=instance, state='payload', fields=copy.deepcopy(expected()['attitude_fields']))


def mode_text(armed=False):
    names = ('flag_armed flag_multicopter_position_control_enabled flag_control_manual_enabled '
        'flag_control_auto_enabled flag_control_offboard_enabled flag_control_rates_enabled '
        'flag_control_attitude_enabled flag_control_acceleration_enabled flag_control_velocity_enabled '
        'flag_control_position_enabled flag_control_altitude_enabled flag_control_climb_rate_enabled '
        'flag_control_termination_enabled').split()
    body = ' vehicle_control_mode\n    timestamp: 496000\n'
    return body+''.join('    '+name+': '+('True' if armed and name == 'flag_armed' else 'False')+'\n' for name in names)
