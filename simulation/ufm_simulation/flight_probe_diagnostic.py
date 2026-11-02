"""Private diagnostic observations; unavailable payloads never become valid snapshots."""
import copy
import json
import re

from .flight_probe_contract import (CLIENT_NS, GROUP_NS, RAW_BYTES, RECORD_BYTES, FILE_BYTES,
    PARAMETERS, _native_field, argv_for, bounded, fields, integer, parse_output,
    plan, same, text, validate_owner, validate_query)

STATES = ('payload', 'not_published', 'payload_unavailable')


def _block(lines, topic, layout, instance):
    if not lines:
        return dict(instance=instance, state='payload_unavailable', fields=None)
    if lines[0] != ' ' + topic:
        raise ValueError('diagnostic_native_body')
    values = {}
    for line in lines[1:]:
        match = re.fullmatch(r'    ([a-z][a-z0-9_]*): (.+)', line)
        if not match:
            raise ValueError('diagnostic_native_fields')
        name, raw = match.groups()
        if name not in layout or name in values:
            raise ValueError('diagnostic_native_fields')
        values[name] = _native_field(raw, name, *layout[name])
    if set(values) != set(layout):
        raise ValueError('diagnostic_native_incomplete')
    return dict(instance=instance, state='payload', fields=values)


def parse_native(query, stdout, stderr, returncode, layouts):
    validate_query(query)
    text(stdout, RAW_BYTES, raw=True)
    text(stderr, RAW_BYTES, raw=True)
    integer(returncode, 255, -255)
    if len(stdout.encode()) + len(stderr.encode()) > RAW_BYTES:
        raise ValueError('diagnostic_raw_limit')
    if returncode != 0 or stderr != '':
        raise ValueError('diagnostic_client_error')
    if any(ord(c) < 32 and c != '\n' for c in stdout):
        raise ValueError('diagnostic_native_control')
    lines = [line for line in stdout.split('\n') if line != '']
    if query['kind'] == 'parameter':
        result = parse_output(query, stdout, stderr, returncode, layouts)['value']
        if result['integer'] != PARAMETERS[query['name']]:
            raise ValueError('diagnostic_parameter_mismatch')
        return dict(state='payload', reason='', instances=[], parameter=result)
    if lines == ['never published']:
        return dict(state='not_published', reason='native_not_published', instances=[], parameter=None)
    topic = query['name']
    if not lines:
        raise ValueError('diagnostic_native_empty')
    if lines[0] == 'TOPIC: ' + topic:
        instances = [_block(lines[1:], topic, layouts[topic], None)]
    else:
        header = re.fullmatch(r'TOPIC: ' + re.escape(topic) + r' ([2-9]) instances', lines[0])
        if not header:
            raise ValueError('diagnostic_native_header')
        blocks = []
        for line in lines[1:]:
            marker = re.fullmatch(r'Instance ([0-8]):', line)
            if marker:
                blocks.append((int(marker.group(1)), []))
            elif blocks:
                blocks[-1][1].append(line)
            else:
                raise ValueError('diagnostic_native_instance')
        ids = [instance for instance, _ in blocks]
        if len(blocks) != int(header.group(1)) or ids != sorted(set(ids)):
            raise ValueError('diagnostic_native_instance')
        instances = [_block(body, topic, layouts[topic], instance) for instance, body in blocks]
    unavailable = any(item['state'] == 'payload_unavailable' for item in instances)
    return dict(state='payload_unavailable' if unavailable else 'payload',
        reason='native_payload_unavailable' if unavailable else '', instances=instances, parameter=None)


def observation_gate(query, observation):
    if query['name'] == 'vehicle_control_mode':
        if any(item['fields'] is not None and item['fields']['flag_armed']
                for item in observation['instances']):
            raise ValueError('diagnostic_observation_armed')


def validate_event(value, layouts, binary_dir):
    bounded(value)
    fields(value, 'schema_version query argv owner_before owner_after last_hil_us fdm_time_s '
        'wall_start_ns wall_end_ns returncode stdout stderr observation binding_status control_gate_accepted')
    if value['schema_version'] != 'sim_flight_uorb_diagnostic.v1':
        raise ValueError('diagnostic_version')
    q = value['query']
    validate_query(q)
    if not same(value['argv'], argv_for(binary_dir, q)):
        raise ValueError('diagnostic_argv')
    for name in ('owner_before', 'owner_after'):
        validate_owner(value[name], binary_dir, q['run_id'])
    if not same(value['owner_before'], value['owner_after']):
        raise ValueError('diagnostic_owner_changed')
    integer(value['last_hil_us'], 2**64-1)
    if value['last_hil_us'] != (q['checkpoint']-1)*4000:
        raise ValueError('diagnostic_hil_context')
    if (type(value['fdm_time_s']) not in (int, float)
            or abs(value['fdm_time_s']-q['checkpoint']*.004) > 1e-9):
        raise ValueError('diagnostic_fdm_context')
    for name in ('wall_start_ns', 'wall_end_ns'):
        integer(value[name])
    if not 0 <= value['wall_end_ns']-value['wall_start_ns'] <= CLIENT_NS:
        raise ValueError('diagnostic_client_time')
    if value['binding_status'] != 'unverified' or value['control_gate_accepted'] is not False:
        raise ValueError('diagnostic_control_gate')
    expected = parse_native(q, value['stdout'], value['stderr'], value['returncode'], layouts)
    if not same(value['observation'], expected):
        raise ValueError('diagnostic_projection')


def dumps(value, layouts, binary_dir):
    validate_event(value, layouts, binary_dir)
    raw = json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(raw) > RECORD_BYTES:
        raise ValueError('diagnostic_record_limit')
    return raw


def loads(raw, layouts, binary_dir):
    if type(raw) is not bytes or len(raw) > RECORD_BYTES:
        raise ValueError('diagnostic_record_limit')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('diagnostic_duplicate_key')
            result[key] = value
        return result

    def bad(_):
        raise ValueError('diagnostic_nonfinite_json')

    def integer_text(raw):
        if len(raw) > 21:
            raise ValueError('diagnostic_integer_text')
        return int(raw)

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
            parse_int=integer_text, parse_constant=bad)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('diagnostic_json_encoding') from exc
    validate_event(value, layouts, binary_dir)
    return value


def validate_stream(records, run_id, layouts, binary_dir):
    expected = plan(run_id)
    seen = []
    total = 0
    groups = {}
    for row in records:
        if len(seen) >= 21:
            raise ValueError('diagnostic_stream_count')
        total += len(dumps(row, layouts, binary_dir))+1
        if total > FILE_BYTES:
            raise ValueError('diagnostic_stream_bytes')
        if not same(row['query'], expected[len(seen)]):
            raise ValueError('diagnostic_stream_order')
        if seen and (not same(row['owner_before'], seen[0]['owner_before'])
                or row['wall_start_ns'] < seen[-1]['wall_end_ns']):
            raise ValueError('diagnostic_stream_identity_or_time')
        key = (row['query']['checkpoint'], row['query']['kind'])
        first = groups.setdefault(key, row['wall_start_ns'])
        if row['wall_end_ns']-first > GROUP_NS:
            raise ValueError('diagnostic_group_time')
        observation_gate(row['query'], row['observation'])
        seen.append(copy.deepcopy(row))
    if len(seen) != 21:
        raise ValueError('diagnostic_stream_incomplete')
    query_states = {state: 0 for state in STATES}
    instance_states = {state: 0 for state in ('payload', 'payload_unavailable')}
    observations = []
    gaps = []
    previous = {}
    payloads = {}
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
                    ('timestamp', 'timestamp_sample', 'delta_angle_dt', 'delta_velocity_dt',
                     'primary_instance', 'instances_available', 'healthy', 'noutputs',
                     'control_mode_flags', 'filter_fault_flags')
                    or 'device_id' in k or k.startswith(('cs_', 'flag_'))}
                payloads[(q['checkpoint'], q['name'], item['instance'])] = selected
                for name in ('timestamp', 'timestamp_sample'):
                    if name in selected:
                        key = (q['name'], item['instance'], name)
                        if selected[name] == 0 or (key in previous and selected[name] < previous[key]):
                            gaps.append(dict(checkpoint=q['checkpoint'], topic=q['name'],
                                instance=item['instance'], field=name, reason='zero_or_regressing_time'))
                        previous[key] = selected[name]
            if item['instance'] is None:
                gaps.append(dict(checkpoint=q['checkpoint'], topic=q['name'], reason='instance_label_unavailable'))
            observations.append(dict(checkpoint=q['checkpoint'], topic=q['name'], instance=item['instance'],
                state=item['state'], fields=selected))
    for (checkpoint, topic, _), values in list(payloads.items()):
        if topic == 'estimator_selector_status' and 'primary_instance' in values:
            primary = values['primary_instance']
            if (checkpoint, 'estimator_attitude', primary) not in payloads:
                gaps.append(dict(checkpoint=checkpoint, topic=topic, primary_instance=primary,
                    reason='primary_attitude_payload_unconfirmed'))
    return dict(diagnostic_collection_complete=True,
        payload_complete=all(r['observation']['state'] == 'payload' for r in seen[:18]),
        queries=21, bytes=total, query_states=query_states, instance_states=instance_states,
        topic_observations=observations, gaps=gaps, binding_status='unverified', control_gate_accepted=False,
        legacy_sw02b_runtime_accepted=False,
        scope='Diagnostic collection only; payload availability and control readiness are separate')
