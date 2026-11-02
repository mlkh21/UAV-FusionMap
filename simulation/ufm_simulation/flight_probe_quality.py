"""Private v2 observations with two source-guarded, explicitly unavailable ratios."""
import copy
import json
import re

from .flight_probe_contract import (CLIENT_NS, GROUP_NS, RAW_BYTES, RECORD_BYTES, FILE_BYTES,
    _native_field, argv_for, bounded, fields, integer, plan, same, text, validate_owner, validate_query)
from .flight_probe_diagnostic import observation_gate, parse_native as parse_v1

MASKS = {'vel_test_ratio': 0x0100000c, 'pos_test_ratio': 0x00001004}
STATES = ('payload', 'not_published', 'payload_unavailable', 'payload_quality_unavailable')
SEMANTIC_PATHS = ('src/modules/ekf2/EKF/ekf_helper.cpp', 'src/modules/ekf2/EKF/common.h',
    'src/modules/ekf2/EKF2.cpp', 'src/modules/ekf2/EKF/estimator_interface.cpp')


def verify_sources(actual, native_messages, baseline):
    if native_messages != baseline['native_messages']:
        raise ValueError('quality_message_layout_changed')
    if set(actual) != set(SEMANTIC_PATHS) or set(actual) != {r['path'] for r in baseline['source_regions']}:
        raise ValueError('quality_semantic_sources')
    for region in baseline['source_regions']:
        source = actual[region['path']]
        if source.count(region['begin']) != 1:
            raise ValueError('quality_semantic_source_changed')
        tail = source.split(region['begin'], 1)[1]
        if region['end'] not in tail or region['begin']+tail.split(region['end'], 1)[0] != region['text']:
            raise ValueError('quality_semantic_source_changed')


def _status_block(lines, layout, instance):
    if not lines:
        return dict(instance=instance, state='payload_unavailable', fields=None, unavailable_fields=[])
    if lines[0] != ' estimator_status':
        raise ValueError('quality_native_body')
    tokens = {}
    for line in lines[1:]:
        match = re.fullmatch(r'    ([a-z][a-z0-9_]*): (.+)', line)
        if not match or match[1] in tokens or match[1] not in layout:
            raise ValueError('quality_native_fields')
        tokens[match[1]] = match[2]
    if set(tokens) != set(layout):
        raise ValueError('quality_native_incomplete')
    if any(layout.get(name) != ('float32', 1) for name in MASKS) or layout.get('control_mode_flags') != ('uint32', 1):
        raise ValueError('quality_ratio_layout')
    annotation = re.fullmatch(r"([0-9]+) \(0b([01]{4}(?:'[01]{4}){7})\)", tokens['control_mode_flags'])
    if not annotation:
        raise ValueError('quality_mask_annotation')
    values = {}
    pending = []
    for name, raw in tokens.items():
        if name in MASKS and raw == 'nan':
            values[name] = None
            pending.append(name)
        else:
            values[name] = _native_field(raw, name, *layout[name])
    mask = values['control_mode_flags']
    if mask != int(annotation[2].replace("'", ''), 2):
        raise ValueError('quality_mask_annotation')
    unavailable = []
    for name, guard_mask in MASKS.items():
        if name in pending:
            if mask & guard_mask:
                raise ValueError('quality_ratio_source_selected')
            unavailable.append(dict(field=name, native_token='nan', reason='native_ratio_source_not_selected'))
    return dict(instance=instance, state='payload_quality_unavailable' if unavailable else 'payload',
        fields=values, unavailable_fields=unavailable)


def parse_native(query, stdout, stderr, returncode, layouts):
    validate_query(query)
    if query['name'] != 'estimator_status':
        result = parse_v1(query, stdout, stderr, returncode, layouts)
        for item in result['instances']:
            item['unavailable_fields'] = []
        return result
    text(stdout, RAW_BYTES, raw=True)
    text(stderr, RAW_BYTES, raw=True)
    integer(returncode, 255, -255)
    if returncode or stderr != '':
        raise ValueError('quality_client_error')
    if len(stdout.encode())+len(stderr.encode()) > RAW_BYTES:
        raise ValueError('quality_raw_limit')
    if any(ord(c) < 32 and c != '\n' for c in stdout):
        raise ValueError('quality_native_control')
    lines = [line for line in stdout.split('\n') if line != '']
    if lines == ['never published']:
        return dict(state='not_published', reason='native_not_published', instances=[], parameter=None)
    if not lines:
        raise ValueError('quality_native_empty')
    if lines[0] == 'TOPIC: estimator_status':
        instances = [_status_block(lines[1:], layouts['estimator_status'], None)]
    else:
        header = re.fullmatch(r'TOPIC: estimator_status ([2-9]) instances', lines[0])
        if not header:
            raise ValueError('quality_native_header')
        blocks = []
        for line in lines[1:]:
            marker = re.fullmatch(r'Instance ([0-8]):', line)
            if marker:
                blocks.append((int(marker[1]), []))
            elif blocks:
                blocks[-1][1].append(line)
            else:
                raise ValueError('quality_native_instance')
        ids = [i for i, _ in blocks]
        if len(blocks) != int(header[1]) or ids != sorted(set(ids)):
            raise ValueError('quality_native_instance')
        instances = [_status_block(body, layouts['estimator_status'], i) for i, body in blocks]
    states = {item['state'] for item in instances}
    if 'payload_unavailable' in states:
        state, reason = 'payload_unavailable', 'native_payload_unavailable'
    elif 'payload_quality_unavailable' in states:
        state, reason = 'payload_quality_unavailable', 'native_optional_quality_unavailable'
    else:
        state, reason = 'payload', ''
    return dict(state=state, reason=reason, instances=instances, parameter=None)


def validate_event(value, layouts, binary_dir):
    bounded(value)
    fields(value, 'schema_version query argv owner_before owner_after last_hil_us fdm_time_s '
        'wall_start_ns wall_end_ns returncode stdout stderr observation binding_status control_gate_accepted')
    if value['schema_version'] != 'sim_flight_uorb_diagnostic.v2':
        raise ValueError('quality_version')
    q = value['query']
    validate_query(q)
    if not same(value['argv'], argv_for(binary_dir, q)):
        raise ValueError('quality_argv')
    for name in ('owner_before', 'owner_after'):
        validate_owner(value[name], binary_dir, q['run_id'])
    if not same(value['owner_before'], value['owner_after']):
        raise ValueError('quality_owner_changed')
    integer(value['last_hil_us'], 2**64-1)
    if value['last_hil_us'] != (q['checkpoint']-1)*4000:
        raise ValueError('quality_hil_context')
    if type(value['fdm_time_s']) not in (int, float) or abs(value['fdm_time_s']-q['checkpoint']*.004) > 1e-9:
        raise ValueError('quality_fdm_context')
    for name in ('wall_start_ns', 'wall_end_ns'):
        integer(value[name])
    if not 0 <= value['wall_end_ns']-value['wall_start_ns'] <= CLIENT_NS:
        raise ValueError('quality_client_time')
    if value['binding_status'] != 'unverified' or value['control_gate_accepted'] is not False:
        raise ValueError('quality_control_gate')
    if not same(value['observation'], parse_native(q, value['stdout'], value['stderr'], value['returncode'], layouts)):
        raise ValueError('quality_projection')


def dumps(value, layouts, binary_dir):
    validate_event(value, layouts, binary_dir)
    raw = json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(raw) > RECORD_BYTES:
        raise ValueError('quality_record_limit')
    return raw


def loads(raw, layouts, binary_dir):
    if type(raw) is not bytes or len(raw) > RECORD_BYTES:
        raise ValueError('quality_record_limit')

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('quality_duplicate_key')
            value[key] = item
        return value

    def bad(_):
        raise ValueError('quality_nonfinite_json')

    def number(raw):
        if len(raw) > 21:
            raise ValueError('quality_integer_text')
        return int(raw)

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_int=number, parse_constant=bad)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('quality_json_encoding') from exc
    validate_event(value, layouts, binary_dir)
    return value


def validate_stream(records, run_id, layouts, binary_dir):
    expected = plan(run_id)
    seen, groups = [], {}
    total = 0
    for row in records:
        if len(seen) >= 21:
            raise ValueError('quality_stream_count')
        total += len(dumps(row, layouts, binary_dir))+1
        if total > FILE_BYTES:
            raise ValueError('quality_stream_bytes')
        if not same(row['query'], expected[len(seen)]):
            raise ValueError('quality_stream_order')
        if seen and (not same(row['owner_before'], seen[0]['owner_before'])
                or row['wall_start_ns'] < seen[-1]['wall_end_ns']):
            raise ValueError('quality_stream_identity_or_time')
        key = (row['query']['checkpoint'], row['query']['kind'])
        first = groups.setdefault(key, row['wall_start_ns'])
        if row['wall_end_ns']-first > GROUP_NS:
            raise ValueError('quality_group_time')
        observation_gate(row['query'], row['observation'])
        seen.append(copy.deepcopy(row))
    if len(seen) != 21:
        raise ValueError('quality_stream_incomplete')
    query_states = {state: 0 for state in STATES}
    instance_states = {state: 0 for state in STATES if state != 'not_published'}
    observations, isolated, gaps = [], [], []
    previous, payloads = {}, {}
    for row in seen:
        q, obs = row['query'], row['observation']
        query_states[obs['state']] += 1
        if q['kind'] == 'parameter':
            continue
        if obs['state'] != 'payload':
            gaps.append(dict(checkpoint=q['checkpoint'], topic=q['name'], reason=obs['reason']))
        for item in obs['instances']:
            instance_states[item['state']] += 1
            selected = None
            if item['fields'] is not None:
                selected = {k: v for k, v in item['fields'].items() if k in
                    ('timestamp', 'timestamp_sample', 'delta_angle_dt', 'delta_velocity_dt', 'primary_instance',
                     'instances_available', 'healthy', 'noutputs', 'control_mode_flags', 'filter_fault_flags',
                     'vel_test_ratio', 'pos_test_ratio') or 'device_id' in k or k.startswith(('cs_', 'flag_'))}
                payloads[(q['checkpoint'], q['name'], item['instance'])] = selected
                for name in ('timestamp', 'timestamp_sample'):
                    if name in selected:
                        key = (q['name'], item['instance'], name)
                        if selected[name] == 0 or (key in previous and selected[name] < previous[key]):
                            gaps.append(dict(checkpoint=q['checkpoint'], topic=q['name'], instance=item['instance'],
                                field=name, reason='zero_or_regressing_time'))
                        previous[key] = selected[name]
                for descriptor in item['unavailable_fields']:
                    isolated.append(dict(checkpoint=q['checkpoint'], topic=q['name'], instance=item['instance'],
                        timestamp=selected.get('timestamp'), control_mode_flags=selected.get('control_mode_flags'),
                        **descriptor))
            if item['instance'] is None:
                gaps.append(dict(checkpoint=q['checkpoint'], topic=q['name'], reason='instance_label_unavailable'))
            observations.append(dict(checkpoint=q['checkpoint'], topic=q['name'], instance=item['instance'],
                state=item['state'], fields=selected, unavailable_fields=item['unavailable_fields']))
    for (checkpoint, topic, _), values in list(payloads.items()):
        if topic == 'estimator_selector_status' and 'primary_instance' in values:
            primary = values['primary_instance']
            if (checkpoint, 'estimator_attitude', primary) not in payloads:
                gaps.append(dict(checkpoint=checkpoint, topic=topic, primary_instance=primary,
                    reason='primary_attitude_payload_unconfirmed'))
    return dict(diagnostic_collection_complete=True,
        payload_complete=all(r['observation']['state'] == 'payload' for r in seen[:18]),
        body_complete=all(r['observation']['state'] in ('payload', 'payload_quality_unavailable') for r in seen[:18]),
        queries=21, bytes=total, query_states=query_states, instance_states=instance_states,
        isolated_fields=isolated, topic_observations=observations, gaps=gaps,
        binding_status='unverified', control_gate_accepted=False,
        legacy_sw02b_runtime_accepted=False, legacy_sw02c_runtime_accepted=False,
        scope='Conditional quality isolation for diagnostic collection only; no state or control permission')
