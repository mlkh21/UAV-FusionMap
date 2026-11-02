"""Bounded test-only scenario declarations; no ROS or production implementation imports."""
import copy
from fractions import Fraction
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures'
MAX_BYTES = 1024 * 1024
CASE_IDS = (
    'S01.normal S02.ir_gap S03.bad_output S03.exception S03.untrusted S03.slow S03.deadline '
    'S04.pause S04.repeat S04.reset S04.expiry '
    'S05.v35_exact S05.v50_exact S05.v70_exact S05.v35_aged S05.v50_aged S05.v70_aged '
    'S05.sync_edge S05.sync_over S05.pose_edge S05.pose_over '
    'S06.arithmetic S06.fifo S06.missing '
    'S07.map_stop S07.terrain_stop S07.map_block S07.terrain_late S07.instance '
    'S08.record S08.overflow S08.source_failure S08.tamper '
    'S09.clock_conflict S09.missing_subscriber S09.bad_identity S09.recover_view').split()
LIMITS = dict(cases=48, events_per_case=128, repeat_count=128, receipts_per_topic=256,
    receipt_bytes=16 * 1024 * 1024, wall_ns=45_000_000_000, startup_ns=15_000_000_000,
    drain_ns=5_000_000_000, cleanup_ns=5_000_000_000, terrain_events=64, terrain_status_reserve=16)
FORBIDDEN = {'lidar', 'lidar_points', 'lidar_supervision', 'target', 'targets',
             'occupancy_target', 'observed_mask', 'training_supervision'}
OPS = {
    'sample': ('', 'speed_mps pose_age_ns ir_delta_ns ir_present'),
    'clock': ('', ''), 'clock_repeat': ('count period_ns', ''), 'clock_steps': ('count period_ns', ''),
    'clock_control': ('action', ''), 'map_query': ('', 'point frame_id external_deadline_ns'),
    'terrain_query': ('cell', 'pin'), 'backend': ('mode', 'duration_ns deadline_ns'),
    'observation': ('sequence kind body_x point quality', ''),
    'service': ('layer action', 'duration_ns'), 'poll': ('', ''), 'recording': ('action', ''),
    'graph': ('fault', ''), 'cleanup': ('', ''), 'new_run': ('previous_run', ''), 'view': ('mode', '')}
WIRE_IDS = set(('state radar infrared bundle occupancy unavailable inverse snapshot map_request '
    'map_result terrain_request terrain_result terrain_no_data terrain_zero terrain_negative '
    'terrain_status terrain_integer map_occupied map_free map_unknown map_unavailable '
    'terrain_stale terrain_unavailable').split())


def same_literal(actual, expected):
    return json.dumps(actual,sort_keys=True) == json.dumps(expected,sort_keys=True)


def fields(value, required, optional=''):
    if type(value) is not dict or not set(required.split()) <= set(value) <= set((required+' '+optional).split()):
        raise ValueError('P5 fields differ')


def integer(value, maximum=2**63-1):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('P5 integer range/type')


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('P5 finite numeric required')


def text(value):
    if type(value) is not str or not value.strip() or len(value) > 1024:
        raise ValueError('P5 text range/type')
    if len(value.encode('utf-8')) > 1024:
        raise ValueError('P5 text bytes')


def vector(value, dimensions=3, integral=False):
    if type(value) is not list or len(value) != dimensions:
        raise ValueError('P5 vector shape')
    for item in value:
        integer(item,2**31-1) if integral else number(item)


def bounded(value):
    remaining = [100000]

    def walk(item, depth):
        remaining[0] -= 1
        if remaining[0] < 0 or depth > 20:
            raise ValueError('P5 structural limit')
        if type(item) is dict:
            if len(item) > 256:
                raise ValueError('P5 object limit')
            for key, child in item.items():
                text(key)
                if key.lower() in FORBIDDEN:
                    raise ValueError('P5 training supervision forbidden')
                walk(child, depth+1)
        elif type(item) is list:
            if len(item) > 4096:
                raise ValueError('P5 list limit')
            for child in item:
                walk(child, depth+1)
        elif type(item) is str:
            if item:
                text(item)
        elif type(item) is int:
            if abs(item) >= 2**63:
                raise ValueError('P5 integer magnitude')
        elif type(item) is float:
            number(item)
        elif item is not None and type(item) is not bool:
            raise ValueError('P5 JSON type')
    walk(value, 0)
    size = 0
    for chunk in json.JSONEncoder(ensure_ascii=False, allow_nan=False).iterencode(value):
        size += len(chunk.encode('utf-8'))
        if size > MAX_BYTES:
            raise ValueError('P5 document bytes')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('P5 duplicate JSON key')
        result[key] = value
    return result


def _constant(_):
    raise ValueError('P5 nonfinite JSON')


def load(path):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES+1)
    if len(raw) > MAX_BYTES:
        raise ValueError('P5 input bytes')
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        bounded(value)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('P5 encoding/depth') from exc
    return value


def expand(case, sequences):
    result = []
    for event in case['events']:
        if type(event) is dict:
            fields(event, 'use')
            if event['use'] not in sequences:
                raise ValueError('P5 unknown sequence')
            result.extend(copy.deepcopy(sequences[event['use']]))
        else:
            result.append(copy.deepcopy(event))
        if len(result) > LIMITS['events_per_case']:
            raise ValueError('P5 expanded events limit')
    return result


def validate_event(event):
    if type(event) is not list or len(event) != 5:
        raise ValueError('P5 event columns')
    name, operation, stamp, wall, args = event
    text(name)
    if type(operation) is not str or operation not in OPS:
        raise ValueError('P5 operation')
    integer(stamp, 3_000_000_000)
    integer(wall, LIMITS['wall_ns'])
    fields(args, *OPS[operation])
    for key in ('pose_age_ns', 'ir_delta_ns', 'duration_ns', 'deadline_ns', 'external_deadline_ns'):
        if key in args:
            integer(args[key], LIMITS['wall_ns'])
    if 'speed_mps' in args:
        number(args['speed_mps'])
        if not 0 <= args['speed_mps'] <= 70:
            raise ValueError('P5 fixture speed')
    if 'ir_present' in args and type(args['ir_present']) is not bool:
        raise ValueError('P5 availability flag')
    if 'pose_age_ns' in args and args['pose_age_ns'] > stamp:
        raise ValueError('P5 state before time zero')
    if 'point' in args:
        vector(args['point'])
    if 'frame_id' in args and args['frame_id'] not in ('odom', 'map'):
        raise ValueError('P5 query frame')
    if operation in ('clock_repeat', 'clock_steps'):
        integer(args['count'], LIMITS['repeat_count'])
        integer(args['period_ns'], 1_000_000_000)
        if not args['count'] or not args['period_ns']:
            raise ValueError('P5 repeat must progress wall time')
        if operation == 'clock_steps' and stamp+(args['count']-1)*args['period_ns'] > 3_000_000_000:
            raise ValueError('P5 repeated business time budget')
    if operation == 'terrain_query':
        integer(args['cell'], 3)
        if 'pin' in args and args['pin'] != 'previous_group':
            raise ValueError('P5 unknown pin source')
    if operation == 'backend':
        if args['mode'] not in ('normal', 'bad_output', 'exception', 'untrusted_context', 'slow'):
            raise ValueError('P5 test backend mode')
        if args['mode'] == 'slow':
            fields(args, 'mode duration_ns deadline_ns')
            if not 0 < args['deadline_ns'] < args['duration_ns']:
                raise ValueError('P5 slow task must exceed its deadline')
        else:
            fields(args, 'mode')
    if operation == 'observation':
        integer(args['sequence'], 255)
        number(args['body_x'])
        if args['body_x'] not in (0, 0.5, 40, 80) or args['kind'] not in ('occupied', 'free', 'empty'):
            raise ValueError('P5 explicit inverse input')
        if args['quality'] not in ('bounded', 'missing'):
            raise ValueError('P5 quality availability')
    if operation == 'service':
        if args['layer'] not in ('map', 'terrain') or args['action'] not in ('stop', 'block', 'delay', 'restart'):
            raise ValueError('P5 service injection')
        fields(args, 'layer action duration_ns' if args['action'] == 'delay' else 'layer action')
    if operation == 'clock_control' and args['action'] not in ('stop', 'source_mismatch'):
        raise ValueError('P5 clock injection')
    if operation == 'recording' and args['action'] not in ('start', 'close', 'replay', 'tamper_expected_height'):
        raise ValueError('P5 recording action')
    if operation == 'graph' and args['fault'] not in ('clock_conflict', 'missing_subscriber', 'bad_identity'):
        raise ValueError('P5 graph fault')
    if operation == 'new_run':
        text(args['previous_run'])
    if operation == 'view' and args['mode'] != 'native_separate':
        raise ValueError('P5 unregistered overlay forbidden')


def budget(events, recording):
    clocks = sum(1 if row[1] in ('sample', 'clock', 'observation') else row[4]['count']
                 if row[1] in ('clock_repeat', 'clock_steps') else 0 for row in events)
    samples = sum(row[1] == 'sample' for row in events)
    observations = sum(row[1] == 'observation' for row in events)
    queries = sum(row[1] == 'terrain_query' for row in events)
    return dict(clock=clocks, state=samples, radar=samples,
        infrared=sum(row[1] == 'sample' and row[4].get('ir_present', True) for row in events),
        occupancy_ceiling=samples+observations+1, snapshot_ceiling=samples+observations,
        terrain_events_ceiling=0 if recording == 'off' else
            clocks+queries+1+1+LIMITS['terrain_status_reserve']+1)


def validate_inputs(value):
    bounded(value)
    fields(value, 'schema_version fixture_only event_columns profiles sequences cases')
    if (value['schema_version'] != 'test.p5.inputs.v1' or value['fixture_only'] is not True or
            value['event_columns'] != ['id', 'operation', 'time_ns', 'wall_ns', 'arguments']):
        raise ValueError('P5 input version/columns')
    profiles = value['profiles']
    fields(profiles, 'A B C terrain limits')
    if profiles['limits'] != LIMITS or any(type(v) is not int for v in profiles['limits'].values()):
        raise ValueError('P5 budgets must remain explicit')
    fields(profiles['A'], 'map_kind map_id frame_id origin resolution shape free_threshold '
                         'occupied_threshold max_age_ns world_point')
    a = profiles['A']
    if a['map_kind'] != 'latest' or a['frame_id'] != 'odom':
        raise ValueError('P5 A requires latest odom')
    text(a['map_id'])
    for key in ('origin', 'resolution', 'shape', 'world_point'):
        vector(a[key], integral=key == 'shape')
    if any(v <= 0 for v in a['shape']+a['resolution']):
        raise ValueError('P5 grid dimensions')
    number(a['free_threshold']); number(a['occupied_threshold'])
    if not 0 <= a['free_threshold'] < a['occupied_threshold'] <= 1:
        raise ValueError('P5 classification thresholds')
    integer(a['max_age_ns'])
    if not same_literal(profiles['B'], dict(map_kind='m4_fixture', config='configs/m4_fixture.yaml',
            registration_interval_ns=[0,1_000_000_000], T_map_odom_translation=[32,0,0])):
        raise ValueError('P5 B registration/profile')
    if not same_literal(profiles['C'], dict(native=True, terrain_registered_to_scene=False)):
        raise ValueError('P5 native view isolation')
    if not same_literal(profiles['terrain'], dict(config='configs/m5_terrain_fixture.yaml',
            registration_interval_ns=[0,3_000_000_000],
            eligibility_interval_ns=[100_000_000,1_500_000_000],install_ns=100_000_000)):
        raise ValueError('P5 terrain explicit authorization')
    if type(value['cases']) is not list or len(value['cases']) != len(CASE_IDS):
        raise ValueError('P5 complete subcase coverage')
    if type(value['sequences']) is not dict or set(value['sequences']) != {'seed'}:
        raise ValueError('P5 seed sequence')
    seed = value['sequences']['seed']
    if type(seed) is not list or len(seed) != 4:
        raise ValueError('P5 seed length')
    for i, row in enumerate(seed):
        validate_event(row)
        if row != ['seed'+str(i), 'sample', i*50_000_000, i*50_000_000, {}]:
            raise ValueError('P5 seed schedule')
    ids = []
    for case in value['cases']:
        fields(case, 'id profile recording settings events')
        text(case['id']); ids.append(case['id'])
        if case['profile'] not in ('A','B','C') or case['recording'] not in ('off','complete','incomplete','tampered'):
            raise ValueError('P5 case mode')
        lane = 'B' if case['id'].startswith('S06.') or case['id'] == 'S07.map_block' else (
               'C' if case['id'].startswith('S09.') else 'A')
        if case['profile'] != lane:
            raise ValueError('P5 subcase lane differs from design')
        fields(case['settings'], 'max_sealed_submaps' if case['profile'] == 'B' else '')
        if case['profile'] == 'B':
            integer(case['settings']['max_sealed_submaps'], 2)
            if not case['settings']['max_sealed_submaps']:
                raise ValueError('P5 positive sealed limit')
        if type(case['events']) is not list or not 0 < len(case['events']) <= LIMITS['events_per_case']:
            raise ValueError('P5 case event limit')
        events = expand(case, value['sequences'])
        names, last_wall, last_clock = set(), 0, None
        for event in events:
            validate_event(event)
            name, op, stamp, wall, args = event
            if name in names or wall < last_wall:
                raise ValueError('P5 duplicate event or wall order')
            names.add(name)
            last_wall = wall
            if op in ('clock_repeat','clock_steps'):
                last_wall += (args['count']-1)*args['period_ns']
            if last_wall > LIMITS['wall_ns']:
                raise ValueError('P5 repeat wall budget')
            if op in ('sample','clock','clock_repeat','clock_steps','observation'):
                if last_clock is not None and stamp < last_clock and case['id'] != 'S04.reset':
                    raise ValueError('P5 undeclared clock regression')
                last_clock = stamp+(args['count']-1)*args['period_ns'] if op == 'clock_steps' else stamp
            if op == 'observation' and (case['profile'] != 'B' or stamp >= 1_000_000_000):
                raise ValueError('P5 inverse domain/registration')
            if op == 'sample' and case['profile'] != 'A':
                raise ValueError('P5 placeholder cannot enter cumulative lane')
            if case['profile'] == 'B' and op == 'map_query' and stamp >= 1_000_000_000:
                raise ValueError('P5 scene query registration')
        counts = budget(events, case['recording'])
        if any(v > LIMITS['receipts_per_topic'] for k,v in counts.items() if k != 'terrain_events_ceiling'):
            raise ValueError('P5 per-topic receipt budget')
        if case['recording'] in ('complete','tampered') and counts['terrain_events_ceiling'] > 64:
            raise ValueError('P5 complete recording cannot exceed protocol')
        if case['recording'] != 'off':
            actions = [r[4]['action'] for r in events if r[1] == 'recording']
            required = ['start','close','tamper_expected_height','replay'] if case['recording'] == 'tampered' else ['start','close','replay']
            if actions != required or events[0][1] != 'recording':
                raise ValueError('P5 recording lifecycle')
    if sorted(ids) != sorted(CASE_IDS):
        raise ValueError('P5 missing/duplicate subcase')


INTEGER_SIGNALS = set(('map.revision map.evidence_ns terrain.revision bundle.delta occupancy.delta '
    'radar.delta occupancy.voxels worker.pending worker.late_applied bundle.pose_age_ns '
    'recording.event_ceiling').split())
BOOL_SIGNALS = set(('clock.locked map.clock_liveness_gate map.client_deadline map.fallback_free '
    'recording.complete replay.executed replay.matches graph.accepted cleanup.owned_only '
    'run.inherits view.native view.unregistered_overlay').split())
ENUM_SIGNALS = {
    'map.state': ('occupied','free','unknown','stale','unavailable'),
    'terrain.state': ('valid','unknown','stale','unavailable'),
    'occupancy.state': ('valid','degraded','unavailable'), 'map.frame': ('map','odom'),
    'terrain.instance': ('$first','$different'),
    'terrain.group': ('discarded',), 'transport.state': ('unavailable','external_deadline')}


def validate_signal(key, value):
    if key in INTEGER_SIGNALS:
        integer(value)
    elif key in BOOL_SIGNALS:
        if type(value) is not bool:
            raise ValueError('P5 expected bool')
    elif key in ENUM_SIGNALS:
        if type(value) is not str or value not in ENUM_SIGNALS[key]:
            raise ValueError('P5 expected enum')
    elif key in ('geometry.index','map.index'):
        vector(value, integral=True)
    elif key == 'geometry.point':
        vector(value)
    elif key in ('geometry.error_m','map.probability','terrain.height'):
        if value is not None or key == 'geometry.error_m':
            number(value)
            if key == 'map.probability' and not 0 <= value <= 1:
                raise ValueError('P5 probability range')
    elif key == 'map.interval':
        if value is not None:
            if type(value) is not list or len(value) != 2 or any(type(v) is not str for v in value):
                raise ValueError('P5 exact fraction interval')
            try:
                lo, hi = map(Fraction, value)
                if not 0 <= lo <= hi <= 1:
                    raise ValueError('P5 probability interval')
            except (ZeroDivisionError, ValueError) as exc:
                raise ValueError('P5 rational interval') from exc
    elif key in ('terrain.reason','bundle.reason'):
        text(value)
    else:
        raise ValueError('P5 unknown expected signal: '+key)


def validate_pair(inputs, expected):
    validate_inputs(inputs)
    bounded(expected)
    fields(expected, 'schema_version fixture_only cases wire_projections')
    if expected['schema_version'] != 'test.p5.expectations.v1' or expected['fixture_only'] is not True:
        raise ValueError('P5 expected version')
    if type(expected['cases']) is not list or len(expected['cases']) != len(CASE_IDS):
        raise ValueError('P5 expected case coverage')
    lookup = {c['id']: c for c in inputs['cases']}
    ids = []
    for case in expected['cases']:
        fields(case, 'id checks')
        text(case['id'])
        if case['id'] not in lookup:
            raise ValueError('P5 orphan expected case')
        ids.append(case['id'])
        events = {r[0] for r in expand(lookup[case['id']], inputs['sequences'])}
        if type(case['checks']) is not list or not 0 < len(case['checks']) <= 128:
            raise ValueError('P5 check limit')
        afters = set()
        for row in case['checks']:
            fields(row, 'after values', 'declared')
            text(row['after'])
            if row['after'] not in events or row['after'] in afters:
                raise ValueError('P5 orphan/duplicate checkpoint')
            afters.add(row['after'])
            if type(row['values']) is not dict or not 0 < len(row['values']) <= 32:
                raise ValueError('P5 checkpoint shape')
            for key, value in row['values'].items():
                validate_signal(key, value)
            if 'declared' in row:
                if lookup[case['id']]['profile'] != 'B':
                    raise ValueError('P5 ownership declarations only apply to Scene fixture')
                fields(row['declared'], '', 'owner sealed_count')
                if not row['declared']:
                    raise ValueError('P5 empty ownership declaration')
                if 'owner' in row['declared'] and row['declared']['owner'] not in ('active','sealed'):
                    raise ValueError('P5 declared owner')
                if 'sealed_count' in row['declared']:
                    integer(row['declared']['sealed_count'],lookup[case['id']]['settings']['max_sealed_submaps'])
    if sorted(ids) != sorted(CASE_IDS):
        raise ValueError('P5 missing expected subcase')
    if type(expected['wire_projections']) is not dict or set(expected['wire_projections']) != WIRE_IDS:
        raise ValueError('P5 wire projection limit')
    for name, projection in expected['wire_projections'].items():
        text(name)
        if type(projection) is not dict or not projection:
            raise ValueError('P5 nonempty wire projection')
        for path in projection:
            if any(not part or not part.replace('_','').isalnum() for part in path.split('.')):
                raise ValueError('P5 wire projection path')


def load_pair():
    inputs, expected = (load(FIXTURES / name) for name in
                        ('p5_combination_inputs.json','p5_combination_expectations.json'))
    validate_pair(inputs, expected)
    return inputs, expected
