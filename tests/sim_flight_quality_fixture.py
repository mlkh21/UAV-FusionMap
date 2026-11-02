"""Tests-only v2 inputs and independent literal projections."""
import copy
import json
import re

from sim_flight_diagnostic_fixture import BINARY_DIR, ROOT, RUN_ID, event as old_event
from ufm_simulation.flight_probe_contract import layouts_from_texts


def expected():
    return json.loads((ROOT/'tests/fixtures/sim_flight_quality_cases.json').read_text())


def baseline():
    return json.loads((ROOT/'tests/fixtures/sim_flight_quality_baseline.json').read_text())


def layouts():
    return layouts_from_texts(baseline()['native_messages'])


def event(index=1):
    row = old_event(index)
    row['schema_version'] = 'sim_flight_uorb_diagnostic.v2'
    for item in row['observation']['instances']:
        item['unavailable_fields'] = []
    return row


def status_body(mask=537002496, vel='nan', pos='nan'):
    body = baseline()['archived_raw']['stdout'].split('Instance 0:\n', 1)[1].split('\nInstance 1:', 1)[0]
    binary = format(mask, '032b')
    annotation = "'".join(binary[i:i+4] for i in range(0,32,4))
    body = re.sub(r'    control_mode_flags: [^\n]+', '    control_mode_flags: %s (0b%s)' % (mask,annotation), body)
    body = body.replace('vel_test_ratio: nan', 'vel_test_ratio: '+vel)
    return body.replace('pos_test_ratio: nan', 'pos_test_ratio: '+pos)


def status_text(mask=537002496, vel='nan', pos='nan'):
    return '\nTOPIC: estimator_status\n'+status_body(mask,vel,pos)


def status_projection(mask=537002496, vel=None, pos=None, instance=None):
    literal = expected()
    fields = copy.deepcopy(literal['status_fields'])
    fields.update(control_mode_flags=mask, vel_test_ratio=vel, pos_test_ratio=pos)
    unavailable = [copy.deepcopy(d) for d in literal['unavailable_descriptors'] if fields[d['field']] is None]
    return dict(instance=instance, state='payload_quality_unavailable' if unavailable else 'payload',
        fields=fields, unavailable_fields=unavailable)


def finite_input(topic):
    lines = ['TOPIC: '+topic, ' '+topic]
    fields = {}
    for name,(kind,size) in layouts()[topic].items():
        value = False if kind == 'bool' else 0.0 if kind == 'float32' else 0
        token = 'False' if kind == 'bool' else '0.0000' if kind == 'float32' else '0'
        fields[name] = [value]*size if size != 1 else value
        raw = '['+', '.join([token]*size)+']' if size != 1 else token
        if name == 'control_mode_flags':raw += " (0b0000'0000'0000'0000'0000'0000'0000'0000)"
        lines.append('    '+name+': '+raw)
    return '\n'.join(lines)+'\n',dict(state='payload',reason='',instances=[
        dict(instance=None,state='payload',fields=fields,unavailable_fields=[])],parameter=None)
