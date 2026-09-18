"""SIM-01B离线验收：以实际bag重读、发布台账和业务关系分别提供证据。"""
from collections import Counter
import io
import json
import math
from pathlib import Path

CLOCK = '/clock'
SOURCE = '/uav/sim/state'
SENSOR = '/uav/sensors/state'
RAW = '/mavlink/from'
DIAGNOSTIC = '/uav/diagnostics'
BUSINESS = (CLOCK, SOURCE, SENSOR)
PYTHON = '/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python'
SPAN_NS = 300_000_000_000
LIMIT_NS = 600_000_000_000


def fail(errors, message):
    if message not in errors:
        errors.append(message)


def read_json(path, errors):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        fail(errors, str(Path(path).name) + ': ' + str(exc))
        return {}


def read_lines(path, errors):
    try:
        with Path(path).open() as stream:
            return [json.loads(line) for line in stream if line.strip()]
    except (OSError, ValueError) as exc:
        fail(errors, str(Path(path).name) + ': ' + str(exc))
        return []


def load_records(run, bag_name, errors):
    """不信任sidecar声明：重读消息、时间和ROS字节后重新解码业务字段。"""
    run = Path(run)
    closed = read_json(run / 'writer-closed.json', errors)
    if closed.get('passed') is not True or closed.get('queue_empty') is not True:
        fail(errors, 'writer-closed: incomplete or failed')
    if closed.get('errors'):
        fail(errors, 'writer-closed: reported errors')
    rows = read_lines(run / 'records.jsonl', errors)
    counts = Counter(row.get('topic') for row in rows)
    if closed.get('records') != len(rows) or closed.get('topic_counts') != dict(counts):
        fail(errors, 'writer-closed: counts mismatch')
    if closed.get('received_counts') != dict(counts):
        fail(errors, 'writer-closed: received counts mismatch')
    start_ns = closed.get('record_start_monotonic_ns')
    for i, row in enumerate(rows, 1):
        if row.get('record_seq') != i:
            fail(errors, 'record_seq: not consecutive')
        receipt, bag_ns = row.get('receipt_monotonic_ns'), row.get('bag_time_ns')
        if (type(receipt) is not int or type(bag_ns) is not int or bag_ns < 0 or
                type(start_ns) is not int or receipt - start_ns != bag_ns):
            fail(errors, 'record_time: wrong domain or type')
        if i > 1 and (type(bag_ns) is not int or bag_ns <= rows[i-2].get('bag_time_ns', -1)):
            fail(errors, 'record_time: not strictly increasing')
    if not (run / bag_name).exists():
        fail(errors, bag_name + ': missing')
        return []
    result = []
    try:
        import rosbag
        from ufm_ros_contract import from_ros_state
        with rosbag.Bag(str(run / bag_name), 'r') as bag:
            iterator = iter(bag.read_messages())
            for row in rows:
                entry = next(iterator, None)
                if entry is None:
                    fail(errors, 'bag: fewer records than sidecar')
                    break
                topic, message, stamp = entry
                buffer = io.BytesIO()
                message.serialize(buffer)
                wire_hex = buffer.getvalue().hex()
                if (topic != row.get('topic') or wire_hex != row.get('wire_hex') or
                        stamp.to_nsec() != row.get('bag_time_ns')):
                    fail(errors, 'bag: topic/time/wire differs from sidecar')
                actual = dict(row, topic=topic, wire_hex=wire_hex)
                if topic == CLOCK:
                    actual['timestamp'] = message.clock.to_nsec()
                    if actual['timestamp'] != row.get('timestamp'):
                        fail(errors, 'bag: clock differs from sidecar')
                elif topic in (SOURCE, SENSOR):
                    state = from_ros_state(message)
                    actual.update(state=state, timestamp=state['header']['timestamp'],
                                  sample_id=state['header']['sample_id'])
                    if any(actual[key] != row.get(key) for key in ('state', 'timestamp', 'sample_id')):
                        fail(errors, 'bag: state differs from sidecar')
                elif topic == RAW:
                    from mavros.mavlink import convert_to_bytes
                    actual.update(raw_wire_hex=convert_to_bytes(message).hex(),
                                  framing=message.framing_status, msgid=message.msgid,
                                  sysid=message.sysid, compid=message.compid)
                    if any(actual[key] != row.get(key) for key in
                           ('raw_wire_hex', 'framing', 'msgid', 'sysid', 'compid')):
                        fail(errors, 'bag: raw MAVLink differs from sidecar')
                elif topic == DIAGNOSTIC:
                    actual['items'] = [dict(name=item.name, level=item.level, message=item.message,
                                           values={v.key: v.value for v in item.values})
                                       for item in message.status]
                    if actual['items'] != row.get('items'):
                        fail(errors, 'bag: diagnostics differ from sidecar')
                else:
                    fail(errors, 'bag: unexpected topic ' + topic)
                result.append(actual)
            if next(iterator, None) is not None:
                fail(errors, 'bag: more records than sidecar')
    except Exception as exc:
        fail(errors, 'bag: read/decode failure ' + str(exc))
    return result


def check_audit(audits, rows, topics, errors):
    """逐话题比较完整有序多重集；相同计数或相同集合均不足以通过。"""
    for topic in topics:
        expected = [row for row in audits if row.get('topic') == topic]
        actual = [row for row in rows if row.get('topic') == topic]
        if [row.get('wire_hex') for row in expected] != [row.get('wire_hex') for row in actual]:
            fail(errors, 'audit_wire_sequence: ' + topic)
        if [(row.get('timestamp'), row.get('sample_id')) for row in expected] != [
                (row.get('timestamp'), row.get('sample_id')) for row in actual]:
            # Pure fixtures may keep identity inside state; real records have both fields.
            fail(errors, 'audit_identity_sequence: ' + topic)


def load_audit(run, name, topics, rows, errors, source=False):
    path = Path(run) / name
    audits = read_lines(path, errors)
    closed = read_json(Path(str(path) + '.closed.json'), errors)
    if closed.get('passed') is not True or closed.get('records') != len(audits):
        fail(errors, name + ': not successfully sealed')
    counts = Counter(row.get('topic') for row in audits)
    if closed.get('topic_counts') != dict(counts):
        fail(errors, name + ': sealed counts mismatch')
    if any(row.get('seq') != i for i, row in enumerate(audits, 1)):
        fail(errors, name + ': seq not consecutive')
    if set(counts) != set(topics):
        fail(errors, name + ': missing or unexpected topics')
    if closed.get('python') != PYTHON:
        fail(errors, name + ': interpreter mismatch')
    if source:
        if closed.get('phase') != 'ACTIVE':
            fail(errors, name + ': source not ACTIVE on normal close')
    elif closed.get('pending_count') != 0 or closed.get('locked') is not False:
        fail(errors, name + ': pending or terminal locked at close')
    bad = ('pending_timeout', 'pending_overflow', 'duplicate_state', 'duplicate_clock',
           'sample_identity_conflict', 'old_state', 'clock_regression', 'published_terminal',
           'terminal_cleared_pending', 'locked_state', 'locked_clock')
    counters = closed.get('counters')
    if not isinstance(counters, dict):
        fail(errors, name + ': missing counters')
    elif any(counters.get(key, 0) for key in bad):
        fail(errors, name + ': drop/duplicate/fault counters nonzero')
    check_audit(audits, rows, topics, errors)
    return audits


def quaternion_matrix(values):
    if len(values) != 4 or any(not math.isfinite(v) for v in values):
        raise ValueError('nonfinite/wrong dimension quaternion')
    norm = math.sqrt(sum(v*v for v in values))
    if norm == 0 or abs(norm-1) > .001:
        raise ValueError('quaternion outside norm tolerance')
    x, y, z, w = [v/norm for v in values]
    return [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]


def close_vector(a, b):
    return len(a) == len(b) and all(math.isfinite(v) for v in a+b) and \
        max((abs(x-y) for x, y in zip(a, b)), default=0.) <= 1e-6


def check_pair(source, sensor, errors):
    try:
        expected_header = dict(source['header'], frame_id='odom', source_type='derived',
                               sample_id='sensors.state:' + source['header']['sample_id'])
        if sensor['header'] != expected_header:
            fail(errors, 'metadata: source/sensor header mismatch')
        for field, expected in (('body_frame_id', 'base_link'), ('velocity_frame_id', 'base_link'),
                                ('state_source', source['state_source'])):
            if sensor.get(field) != expected:
                fail(errors, 'metadata: sensor ' + field)
        p, v = source['position'], source['linear_velocity']
        if not close_vector(sensor['position'], [p[1], p[0], -p[2]]):
            fail(errors, 'position: axis conversion mismatch')
        if not close_vector(sensor['linear_velocity'], [v[0], -v[1], -v[2]]):
            fail(errors, 'velocity: FRD/FLU conversion mismatch')
        src_r = quaternion_matrix(source['orientation_xyzw'])
        got_r = quaternion_matrix(sensor['orientation_xyzw'])
        # Independent matrix proof of C_enu_ned * R_ned_frd * D_frd_flu.
        expected_r = [[src_r[1][0], -src_r[1][1], -src_r[1][2]],
                      [src_r[0][0], -src_r[0][1], -src_r[0][2]],
                      [-src_r[2][0], src_r[2][1], src_r[2][2]]]
        if (not all(close_vector(a, b) for a, b in zip(got_r, expected_r)) or
                abs(math.sqrt(sum(v*v for v in sensor['orientation_xyzw']))-1) > 1e-6):
            fail(errors, 'orientation: true rotation mismatch')
        if source['quality'] != sensor['quality']:
            fail(errors, 'quality: complete provenance/value mismatch')
        if (source['quality']['confidence'] is not None or
                source['quality']['uncertainty']['status'] != 'unavailable' or
                source['quality']['uncertainty']['value'] is not None):
            fail(errors, 'quality: unknown confidence/covariance changed')
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        fail(errors, 'state_pair: invalid fields ' + str(exc))


def sequence_metrics(values, name, minimum_hz, errors):
    if len(values) < 2:
        fail(errors, name + ': too few samples')
        return 0., 0
    gaps = [b-a for a, b in zip(values, values[1:])]
    if any(g <= 0 for g in gaps):
        fail(errors, name + ': duplicate/time regression')
    span = values[-1]-values[0]
    hz = (len(values)-1)*1e9/span if span > 0 else 0.
    if hz < minimum_hz:
        fail(errors, name + ': frequency below threshold')
    if max(gaps) > 500_000_000:
        fail(errors, name + ': maximum gap exceeds 0.5 seconds')
    return hz, max(gaps)


def validate_business(rows, window, errors):
    source = [r['state'] for r in rows if r.get('topic') == SOURCE]
    sensor = [r['state'] for r in rows if r.get('topic') == SENSOR]
    clocks = [r['timestamp'] for r in rows if r.get('topic') == CLOCK]
    metrics = dict(source_samples=len(source), sensor_samples=len(sensor), clocks=len(clocks))
    if not source or not sensor or not clocks:
        fail(errors, 'business: missing topic')
        return metrics
    if any(type(ns) is not int or not 0 <= ns < LIMIT_NS for ns in clocks):
        fail(errors, 'clock: integer/domain/600-second safety limit')
    if any(b <= a for a, b in zip(clocks, clocks[1:])):
        fail(errors, 'clock: whole-run duplicate/time regression')
    src_ids = [s['header']['sample_id'] for s in source]
    raw_sensor_ids = [s['header']['sample_id'] for s in sensor]
    sensor_ids = [s[len('sensors.state:'):] for s in raw_sensor_ids]
    if (any(not s.startswith('sensors.state:') for s in raw_sensor_ids) or
            Counter(src_ids) != Counter(sensor_ids) or src_ids != sensor_ids):
        fail(errors, 'identity: full ordered multiset mismatch')
    if any(n != 1 for n in Counter(src_ids).values()) or any(n != 1 for n in Counter(sensor_ids).values()):
        fail(errors, 'identity: duplicate published state')
    run_id = source[0]['header']['run_id']
    for states, name in ((source, 'source'), (sensor, 'sensor')):
        ns = [s['header']['timestamp'] for s in states]
        if any(type(t) is not int or not 0 <= t < LIMIT_NS for t in ns):
            fail(errors, name + ': timestamp domain/safety limit')
        if any(b <= a for a, b in zip(ns, ns[1:])):
            fail(errors, name + ': whole-run duplicate/time regression')
        if any(s['header']['status'] != 'valid' or s['header']['reason'] != '' for s in states):
            fail(errors, name + ': terminal/nonvalid state')
        if any(s['header']['schema_version'] != '0.1' or s['header']['run_id'] != run_id or
               s['header']['clock_id'] != 'sim:' + run_id for s in states):
            fail(errors, name + ': schema/run/clock metadata')
        if ns[-1] > clocks[-1]:
            fail(errors, 'clock_coverage: final state exceeds clock')
    for state in source:
        h = state['header']
        if (h['frame_id'] != 'world_ned' or h['source_type'] != 'simulation' or
                state['body_frame_id'] != 'body_frd' or state['velocity_frame_id'] != 'body_frd' or
                state['state_source'] != 'estimated'):
            fail(errors, 'metadata: source frames/type')
        if h['sample_id'] != 'sim.odometry:1:1:' + str(h['timestamp']//1000):
            fail(errors, 'identity: source sample/timestamp mismatch')
    pairs = {s['header']['sample_id']: s for s in source}
    for identity, state in zip(sensor_ids, sensor):
        if identity in pairs:
            check_pair(pairs[identity], state, errors)
    t0, t1 = window.get('t0_ns'), window.get('t1_ns')
    if type(t0) is not int or type(t1) is not int:
        fail(errors, 'window: integer timestamps required')
        return metrics
    if t0 != source[0]['header']['timestamp'] or window.get('first_sample_id') != src_ids[0]:
        fail(errors, 'first_source: T0/identity cannot skip first valid source')
    target = next((s for s in source if s['header']['timestamp'] >= t0+SPAN_NS), None)
    if target is None or t1 != target['header']['timestamp'] or window.get('last_sample_id') != target['header']['sample_id']:
        fail(errors, 'window: T1 must be first source at 300 seconds')
    metrics['valid_span_ns'] = t1-t0
    if t1-t0 < SPAN_NS:
        fail(errors, 'window: less than 300 seconds')
    before = [ns for ns in clocks if ns <= t0]
    after = [ns for ns in clocks if ns >= t1]
    if not before or not after:
        fail(errors, 'clock_coverage: missing window boundary')
    clock_window = [ns for ns in clocks if before and after and before[-1] <= ns <= after[0]]
    for name, values, minimum in (
            ('clock', clock_window, 40.),
            ('source', [s['header']['timestamp'] for s in source if t0 <= s['header']['timestamp'] <= t1], 10.),
            ('sensor', [s['header']['timestamp'] for s in sensor if t0 <= s['header']['timestamp'] <= t1], 10.)):
        hz, gap = sequence_metrics(values, name, minimum, errors)
        metrics[name + '_hz'], metrics[name + '_max_gap_ns'] = hz, gap
    return metrics


def check_diagnostics(rows, errors):
    for row in rows:
        if row.get('topic') != DIAGNOSTIC:
            continue
        for item in row.get('items', []):
            if item['level'] >= 2:
                fail(errors, 'diagnostic: ERROR ' + item['name'] + ': ' + item['message'])
            values = item.get('values', {})
            if 'python' in values and values['python'] != PYTHON:
                fail(errors, 'diagnostic: interpreter mismatch')
            for key in ('pending_timeout', 'pending_overflow', 'sample_identity_conflict',
                        'duplicate_state', 'duplicate_clock', 'old_state', 'clock_regression'):
                if int(values.get(key, '0')):
                    fail(errors, 'diagnostic: nonzero drop/fault ' + key)


def check_raw(rows, errors):
    from pymavlink.dialects.v20 import common
    counts = Counter()
    for row in rows:
        if row.get('topic') != RAW:
            continue
        if row.get('framing') != 1:
            fail(errors, 'raw: MAVLink framing error')
            continue
        msgid = row['msgid']
        selected = (row.get('sysid'), row.get('compid')) == (1, 1)
        if selected:
            counts[str(msgid)] += 1
        if msgid == 0 or (selected and msgid == 105):
            try:
                # pymavlink decode补齐MAVLink2短负载时会append，必须保留可变字节缓冲。
                decoded = common.MAVLink(None).decode(bytearray.fromhex(row['raw_wire_hex']))
                if msgid == 0 and decoded.base_mode & 128:
                    fail(errors, 'raw: armed heartbeat')
                if msgid == 105 and decoded.time_usec*1000 >= LIMIT_NS:
                    fail(errors, 'raw: 600-second absolute IMU safety limit')
            except Exception as exc:
                fail(errors, 'raw: MAVLink decode failure ' + str(exc))
    if not all(counts.get(key) for key in ('0', '105', '331')):
        fail(errors, 'raw: missing heartbeat/IMU/ODOMETRY')
    return dict(counts)


def validate_live(run):
    errors = []
    metrics = {}
    try:
        run = Path(run)
        rows = load_records(run, 'live.bag', errors)
        window = read_json(run / 'window.json', errors)
        load_audit(run, 'source-audit.jsonl', (CLOCK, SOURCE), rows, errors, source=True)
        load_audit(run, 'sensor-audit.jsonl', (SENSOR,), rows, errors)
        metrics.update(validate_business(rows, window, errors))
        check_diagnostics(rows, errors)
        metrics['raw_counts'] = check_raw(rows, errors)
    except Exception as exc:
        fail(errors, 'validation: ' + str(exc))
    return dict(passed=not errors, errors=errors, **metrics)


def check_recomputed(expected, actual, errors):
    if len(expected) != len(actual):
        fail(errors, 'B2: sensor count/EOF incomplete')
    for a, b in zip(expected, actual):
        for key in a:
            if key in ('position', 'linear_velocity', 'orientation_xyzw'):
                continue
            if a[key] != b.get(key):
                fail(errors, 'B2: exact field mismatch ' + key)
        if set(a) != set(b):
            fail(errors, 'B2: business field set mismatch')
        for key in ('position', 'linear_velocity'):
            if not close_vector(a[key], b[key]):
                fail(errors, 'B2: geometric mismatch ' + key)
        qa, qb = a['orientation_xyzw'], b['orientation_xyzw']
        if not (close_vector(qa, qb) or close_vector(qa, [-v for v in qb])):
            fail(errors, 'B2: orientation mismatch')


def validate_replay(live, replay, mode):
    errors = []
    metrics = {}
    try:
        if mode not in ('B1', 'B2'):
            raise ValueError('mode must be B1 or B2')
        live, replay = Path(live), Path(replay)
        expected = load_records(live, 'live.bag', errors)
        actual = load_records(replay, 'replay.bag', errors)
        window = read_json(live / 'window.json', errors)
        exact_topics = BUSINESS if mode == 'B1' else (CLOCK, SOURCE)
        for topic in exact_topics:
            a = [r['wire_hex'] for r in expected if r['topic'] == topic]
            b = [r['wire_hex'] for r in actual if r['topic'] == topic]
            if not a or a != b:
                fail(errors, mode + ': wire/topic ordered multiset or EOF mismatch ' + topic)
        if any(r['topic'] == RAW for r in actual):
            fail(errors, mode + ': unexpected live raw input')
        if mode == 'B2':
            load_audit(replay, 'sensor-audit.jsonl', (SENSOR,), actual, errors)
            check_recomputed([r['state'] for r in expected if r['topic'] == SENSOR],
                             [r['state'] for r in actual if r['topic'] == SENSOR], errors)
        metrics.update(validate_business(actual, window, errors))
        check_diagnostics(actual, errors)
    except Exception as exc:
        fail(errors, 'validation: ' + str(exc))
    return dict(passed=not errors, errors=errors, mode=mode, **metrics)
