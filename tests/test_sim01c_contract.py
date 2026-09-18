"""SIM-01C离线契约反例；相同计数或进程退出成功不能代替业务证据。"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from check_sim01c_scenario import (
    CLOCK, DIAGNOSTIC, PYTHON, SENSOR, SOURCE, evaluate_speed_measurement,
    validate_artifacts, validate_observations, validate_speed_matrix,
)


TERMINALS = {
    'F0': 'startup_timeout', 'F1': 'imu_timeout', 'F2': 'odometry_timeout',
    'F3': 'imu_timeout', 'F4': 'imu_regression_or_reordering', 'F5': 'estimator_reset',
}


def config(scenario):
    expected = {
        'source_terminal_count': 0 if scenario in ('F6', 'F7') else 1,
        'sensors_terminal_count': 0 if scenario in ('F6', 'F7') else 1,
        'gate_locked': scenario != 'F7', 'pending_count': 0,
    }
    code = TERMINALS.get(scenario)
    if code:
        expected.update(terminal_code=code, source_fault_diagnostic_count=1,
                        max_post_terminal_valid=0)
    if scenario == 'F0':
        expected.update(terminal_timestamp_ns='0',
            terminal_window_from_first_preparing_diagnostic_receipt_proxy_wall_s=[58.5, 60.5],
            terminal_window_from_source_node_lookup_receipt_proxy_wall_s=[59.5, 60.5])
    elif scenario in ('F1', 'F3'):
        expected.update(terminal_timestamp_equals_last_clock=True,
            terminal_window_from_last_valid_imu_driver_publish_receipt_proxy_wall_s=[2., 2.5])
    elif scenario == 'F2':
        expected.update(terminal_timestamp_equals_last_clock=True, clock_advances_until_terminal=True,
            terminal_window_from_last_valid_odometry_driver_publish_receipt_proxy_wall_s=[2., 2.5])
    elif scenario in ('F4', 'F5'):
        expected.update(terminal_timestamp_equals_last_clock=True,
                        terminal_max_from_injection_wall_s=.5)
    if scenario == 'F1':
        expected['clock_advances_while_imu_stopped'] = False
    if scenario == 'F3':
        expected.update(clock_constant_while_paused=True, recovery_valid_increment=0)
    if scenario == 'F5':
        expected['reset_sample_valid_increment'] = 0
    if scenario == 'F6':
        expected.update(local_error_code='clock_regression', local_error_diagnostic_count=1,
                        max_post_error_valid=0, regressed_clock_valid_increment=0,
                        cleanup_start_max_from_error_wall_s=.5,
                        accepted_states=2, published_states=1)
    if scenario == 'F7':
        expected.update(min_new_run_valid_count=1, distinct_run_id_from_predecessor=True,
                        distinct_clock_id_from_predecessor=True,
                        old_run_valid_increment=0, old_terminal_reappeared_count=0)
    source_allowed = {'timeline:PREPARING': ['WARN'], 'timeline:ACTIVE': ['OK']}
    if code:
        source_allowed.update({code: ['ERROR'], 'timeline:FAULT': ['ERROR']})
    if scenario == 'F1':
        source_allowed['pending_timeout'] = ['WARN']
    allowed = {'simulation/state_clock': source_allowed,
               'sensors/state_adapter': {'clock_gate': ['OK']}}
    if scenario not in ('F6', 'F7'):
        allowed['sensors/state_adapter']['clock_gate_locked'] = ['ERROR']
    if scenario == 'F6':
        allowed['sensors/state_adapter'].update(
            {'clock_regression': ['ERROR'], 'clock_gate_locked': ['ERROR']})
    return {'expected': expected, 'allowed_diagnostics': allowed}


def state(topic, seq, run='run', ns=20_000_000_000, terminal=None,
          sample_suffix=None, receipt_ns=None):
    source = topic == SOURCE
    sample = ('sim.terminal:%s:%d' % (terminal, ns // 1000) if terminal else
              'sim.odometry:1:1:%s' % (sample_suffix if sample_suffix is not None else ns // 1000))
    if not source:
        sample = 'sensors.state:' + sample
    header = dict(schema_version='0.1', run_id=run, clock_id='sim:' + run,
                  timestamp=ns, sample_id=sample,
                  frame_id='world_ned' if source else 'odom',
                  source_type='simulation' if source else 'derived',
                  status='unavailable' if terminal else 'valid',
                  reason='terminal:' + terminal if terminal else '')
    return dict(event_seq=seq, receipt_monotonic_ns=receipt_ns or seq * 100_000_000,
                topic=topic, state={'header': header})


def diagnostic(seq, name, message, level, receipt_ns=None, **values):
    return dict(event_seq=seq, receipt_monotonic_ns=receipt_ns or seq * 100_000_000,
                topic=DIAGNOSTIC, name=name, message=message, level=level,
                hardware_id='run', values=dict(python=PYTHON,
                **{key: str(value) for key, value in values.items()}))


def terminal_fixture(scenario):
    code = TERMINALS[scenario]
    if scenario == 'F0':
        return [diagnostic(1, 'simulation/state_clock', 'timeline:PREPARING', 1,
                           receipt_ns=1_000_000_000),
                diagnostic(2, 'simulation/state_clock', code, 2,
                           receipt_ns=61_000_000_000, **{code: 1}),
                state(SOURCE, 3, ns=0, terminal=code, receipt_ns=61_010_000_000),
                state(SENSOR, 4, ns=0, terminal=code, receipt_ns=61_020_000_000)], []
    rows = [diagnostic(1, 'simulation/state_clock', 'timeline:ACTIVE', 0),
            dict(event_seq=2, receipt_monotonic_ns=200_000_000,
                 topic=CLOCK, timestamp=20_000_000_000),
            state(SOURCE, 3), state(SENSOR, 4)]
    if scenario == 'F1':
        rows.append(diagnostic(5, 'simulation/state_clock', 'pending_timeout', 1,
                               pending_timeout=3))
    rows.extend([diagnostic(len(rows) + 1, 'simulation/state_clock', code, 2,
                            **{code: 1}),
                 state(SOURCE, len(rows) + 2, terminal=code),
                 state(SENSOR, len(rows) + 3, terminal=code)])
    if scenario == 'F2':
        rows.insert(-3, dict(topic=CLOCK, timestamp=21_000_000_000))
        for row in rows[-2:]:
            row['state']['header']['timestamp'] = 21_000_000_000
            row['state']['header']['sample_id'] = (
                '' if row['topic'] == SOURCE else 'sensors.state:') + \
                'sim.terminal:odometry_timeout:21000000'
    for index, row in enumerate(rows, 1):
        row['event_seq'] = index
        row['receipt_monotonic_ns'] = 10_000_000_000 + index * 100_000_000
    terminal_receipt = next(row['receipt_monotonic_ns'] for row in rows
                            if row.get('topic') == SOURCE and
                            row['state']['header']['status'] == 'unavailable')
    if scenario in ('F1', 'F3'):
        driver = [dict(event_seq=1, action='warmup_imu', msg_type='HIGHRES_IMU',
                       time_usec=20_000_000,
                       receipt_monotonic_ns=terminal_receipt - 2_200_000_000,
                       publish_end_monotonic_ns=terminal_receipt - 2_200_000_000)]
    elif scenario == 'F2':
        driver = [dict(event_seq=1, action='warmup_odometry', msg_type='ODOMETRY',
                       time_usec=20_000_000,
                       receipt_monotonic_ns=terminal_receipt - 2_200_000_000,
                       publish_end_monotonic_ns=terminal_receipt - 2_200_000_000),
                  dict(event_seq=2, action='continue_imu', msg_type='HIGHRES_IMU',
                       time_usec=21_000_000,
                       receipt_monotonic_ns=terminal_receipt - 100_000_000,
                       publish_end_monotonic_ns=terminal_receipt - 100_000_000)]
    elif scenario == 'F4':
        driver = [dict(event_seq=1, action='inject_imu_regression', msg_type='HIGHRES_IMU',
                       time_usec=19_000_000,
                       receipt_monotonic_ns=terminal_receipt - 100_000_000,
                       publish_end_monotonic_ns=terminal_receipt - 100_000_000)]
    elif scenario == 'F5':
        driver = [dict(event_seq=1, action='inject_estimator_reset', msg_type='ODOMETRY',
                       time_usec=20_050_000, reset_counter=4,
                       receipt_monotonic_ns=terminal_receipt - 100_000_000,
                       publish_end_monotonic_ns=terminal_receipt - 100_000_000)]
    else:
        driver = []
    if scenario == 'F3':
        driver.append(dict(event_seq=2, action='post_terminal_recovery_imu',
                           msg_type='HIGHRES_IMU', time_usec=20_050_000,
                           receipt_monotonic_ns=terminal_receipt + 100_000_000,
                           publish_end_monotonic_ns=terminal_receipt + 100_000_000))
    return rows, driver


def f6_fixture():
    return [dict(event_seq=1, receipt_monotonic_ns=100_000_000,
                 topic=CLOCK, timestamp=10_000_000_000),
            state(SOURCE, 2, ns=10_000_000_000),
            state(SENSOR, 3, ns=10_000_000_000),
            state(SOURCE, 4, ns=12_000_000_000),
            diagnostic(5, 'sensors/state_adapter', 'clock_regression', 2,
                       clock_regression=1)]


class ScenarioContractTest(unittest.TestCase):
    def test_f0_to_f5_good_fixtures_pass(self):
        for scenario in TERMINALS:
            with self.subTest(scenario=scenario):
                rows, driver = terminal_fixture(scenario)
                source_start = 1_010_000_000 if scenario == 'F0' else None
                self.assertEqual(validate_observations(
                    rows, 'run', scenario, config(scenario), driver_rows=driver,
                    source_start_ns=source_start), [])

    def test_f0_requires_node_lookup_timing_proxy(self):
        rows, driver = terminal_fixture('F0')
        errors = validate_observations(rows, 'run', 'F0', config('F0'),
                                       driver_rows=driver)
        self.assertTrue(any('node lookup' in error for error in errors))

    def test_same_counts_wrong_reason_identity_or_clock_fail(self):
        rows, driver = terminal_fixture('F1')
        for field, value in (('reason', 'terminal:odometry_timeout'),
                             ('sample_id', 'sim.terminal:imu_timeout:wrong'),
                             ('clock_id', 'sim:other')):
            broken = copy.deepcopy(rows)
            terminal = next(row for row in broken if row.get('topic') == SOURCE and
                            row['state']['header']['status'] == 'unavailable')
            terminal['state']['header'][field] = value
            self.assertTrue(validate_observations(
                broken, 'run', 'F1', config('F1'), driver_rows=driver), field)

    def test_terminal_can_equal_last_valid_and_callback_order_is_not_cross_topic_contract(self):
        rows, driver = terminal_fixture('F1')
        source_terminal = next(row for row in rows if row.get('topic') == SOURCE and
                               row['state']['header']['status'] == 'unavailable')
        clock = next(row for row in rows if row.get('topic') == CLOCK)
        clock['receipt_monotonic_ns'] = source_terminal['receipt_monotonic_ns'] + 1
        rows.sort(key=lambda row: row['receipt_monotonic_ns'])
        for index, row in enumerate(rows, 1):
            row['event_seq'] = index
        self.assertEqual(validate_observations(
            rows, 'run', 'F1', config('F1'), driver_rows=driver), [])

    def test_only_f1_allows_pending_timeout(self):
        rows, driver = terminal_fixture('F1')
        self.assertEqual(validate_observations(
            rows, 'run', 'F1', config('F1'), driver_rows=driver), [])
        self.assertTrue(any('only allowed' in error for error in validate_observations(
            rows, 'run', 'F2', config('F2'), driver_rows=driver)))

    def test_proxy_window_uses_current_yaml_key(self):
        rows, driver = terminal_fixture('F2')
        driver[0]['publish_end_monotonic_ns'] += 1_000_000_000
        self.assertTrue(any('outside' in error for error in validate_observations(
            rows, 'run', 'F2', config('F2'), driver_rows=driver)))

    def test_f3_requires_recovery_injection_and_no_post_terminal_valid(self):
        rows, driver = terminal_fixture('F3')
        self.assertTrue(validate_observations(rows, 'run', 'F3', config('F3'),
                                              driver_rows=driver[:-1]))
        broken = copy.deepcopy(rows)
        broken.append(state(SOURCE, len(broken) + 1, ns=21_000_000_000,
                            receipt_ns=broken[-1]['receipt_monotonic_ns'] + 1))
        self.assertTrue(any('after' in error for error in validate_observations(
            broken, 'run', 'F3', config('F3'), driver_rows=driver)))

    def test_f5_reset_sample_must_not_be_valid(self):
        rows, driver = terminal_fixture('F5')
        broken = copy.deepcopy(rows)
        broken.insert(-2, state(SOURCE, 0, ns=20_050_000_000))
        for index, row in enumerate(broken, 1):
            row['event_seq'] = index
            row['receipt_monotonic_ns'] = 10_000_000_000 + index * 100_000_000
        self.assertTrue(any('reset sample' in error for error in validate_observations(
            broken, 'run', 'F5', config('F5'), driver_rows=driver)))


class LocalRegressionAndNewRunTest(unittest.TestCase):
    def test_f6_zero_terminal_error_pending_and_no_later_valid(self):
        rows = f6_fixture()
        self.assertEqual(validate_observations(rows, 'run', 'F6', config('F6')), [])
        broken = copy.deepcopy(rows)
        broken.append(state(SENSOR, 6, ns=12_000_000_000))
        self.assertTrue(any('after clock regression' in error for error in
                            validate_observations(broken, 'run', 'F6', config('F6'))))
        broken = copy.deepcopy(rows)
        broken.append(state(SENSOR, 6, terminal='clock_regression'))
        self.assertTrue(any('terminal count' in error for error in
                            validate_observations(broken, 'run', 'F6', config('F6'))))

    def test_f7_uses_composite_identity_and_allows_same_raw_sample_id(self):
        previous = [state(SOURCE, 1, run='old', sample_suffix='same'),
                    state(SENSOR, 2, run='old', sample_suffix='same'),
                    state(SOURCE, 3, run='old', terminal='imu_timeout'),
                    state(SENSOR, 4, run='old', terminal='imu_timeout')]
        rows = [state(SOURCE, 1, run='new', sample_suffix='same'),
                state(SENSOR, 2, run='new', sample_suffix='same')]
        self.assertEqual(validate_observations(rows, 'new', 'F7', config('F7'),
                                               previous_rows=previous), [])
        broken = copy.deepcopy(rows)
        broken[1]['state']['header']['run_id'] = 'old'
        broken[1]['state']['header']['clock_id'] = 'sim:old'
        self.assertTrue(validate_observations(broken, 'new', 'F7', config('F7'),
                                              previous_rows=previous))


def write_json(path, value):
    Path(path).write_text(json.dumps(value) + '\n')


def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(row) + '\n' for row in rows))


class SealedAuditContractTest(unittest.TestCase):
    def make_f6_run(self, root):
        run = Path(root)
        rows = f6_fixture()
        trigger = dict(passed=True, observed=True, scenario='C-F6', run_id='run',
                       receipt_monotonic_ns=rows[-1]['receipt_monotonic_ns'])
        manifest = dict(run_id='run', scenario='C-F6', errors=[], checker_exit=0,
                        expected_reason='clock_regression', supervisor_trigger=trigger,
                        cleanup_start_monotonic_ns=trigger['receipt_monotonic_ns'] + 100_000_000,
                        python_process_audit={
                            'passed': True,
                            'expected': str(Path(PYTHON).resolve()),
                            'processes': [{'executable': str(Path(PYTHON).resolve())}],
                        })
        cleanup = dict(passed=True, forced=[], remaining_audited_python_pids=[],
                       ports=[{'free': True}])
        sensor_states = [row for row in rows if row.get('topic') == SENSOR]
        audit = [dict(seq=index, topic=SENSOR,
                      timestamp=row['state']['header']['timestamp'],
                      sample_id=row['state']['header']['sample_id'])
                 for index, row in enumerate(sensor_states, 1)]
        marker = dict(passed=True, records=len(audit), topic_counts={SENSOR: len(audit)},
                      python=PYTHON, pending_count=0, locked=True,
                      counters={'clock_regression': 1, 'published_terminal': 0,
                                'accepted_states': 2, 'published_states': 1})
        write_jsonl(run / 'scenario-observations.jsonl', rows)
        write_json(run / 'manifest.json', manifest)
        write_json(run / 'supervisor-trigger.json', trigger)
        write_json(run / 'cleanup-audit.json', cleanup)
        write_jsonl(run / 'sensor-audit.jsonl', audit)
        write_json(run / 'sensor-audit.jsonl.closed.json', marker)
        return marker

    def test_f6_final_audit_not_periodic_diagnostic_count_is_authoritative(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = self.make_f6_run(directory)
            complete = {'scenarios': {'F6': config('F6')}}
            self.assertTrue(validate_artifacts(directory, 'run', 'F6', complete)['passed'])
            marker['counters']['clock_regression'] = 0
            write_json(Path(directory) / 'sensor-audit.jsonl.closed.json', marker)
            result = validate_artifacts(directory, 'run', 'F6', complete)
            self.assertFalse(result['passed'])
            self.assertTrue(any('sealed clock_regression counter' in error
                                for error in result['errors']))

    def test_f6_requires_sealed_pending_causal_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = self.make_f6_run(directory)
            complete = {'scenarios': {'F6': config('F6')}}
            for key, value in (('accepted_states', 1), ('published_states', 2)):
                broken = copy.deepcopy(marker)
                broken['counters'][key] = value
                write_json(Path(directory) / 'sensor-audit.jsonl.closed.json', broken)
                result = validate_artifacts(directory, 'run', 'F6', complete)
                self.assertFalse(result['passed'], key)


class SpeedContractTest(unittest.TestCase):
    def setUp(self):
        self.spec = dict(tolerance_fraction=.15,
                         measurement_min_source_span_ns='20000000000',
                         static_unarmed_required=True,
                         strict_clock_increase_required=True,
                         source_timestamp_rewrite_allowed=False,
                         terminal_count=0)
        self.case = dict(requested_factor=.5)

    def measurement(self, wall_span=40_000_000_000, claimed_factor=.5,
                    claimed_pass=True, requested_factor=.5,
                    source_span=20_000_000_000):
        return dict(measurement_complete=True, requested_factor=requested_factor,
                    actual_factor=claimed_factor, factor_passed=claimed_pass,
                    endpoints={'c0_ns': 1_000_000_000,
                               'c0_receipt_monotonic_ns': 10_000_000_000,
                               'c1_ns': 1_000_000_000 + source_span,
                               'c1_receipt_monotonic_ns': 10_000_000_000 + wall_span},
                    schema_version='0.1', run_id='run', armed=False, static_unarmed=True,
                    strict_clock_increase=True, terminal_count=0,
                    measurement_source_states=400, measurement_adapted_states=400,
                    window_identity_complete=True,
                    timestamp_identity_basis=(
                        'measurement_window_sample_id_time_usec_with_raw_overlap'),
                    raw_odometry_timestamp_matches=100,
                    raw_counts={'0': 10, '331': 100},
                    timestamp_rewrite_detected=False,
                    observer_python=PYTHON,
                    node_pythons={'simulation/state_clock': PYTHON,
                                  'sensors/state_adapter': PYTHON},
                    measurement_source_span_ns=source_span,
                    measurement_wall_span_ns=wall_span,
                    measurement_clock_samples=1000,
                    clock_receipt_hz=25., source_receipt_hz=10., source_sim_time_hz=20.,
                    max_source_interval_ns=50_000_000,
                    max_source_receipt_interval_ns=100_000_000,
                    cpu_environment={'model': 'fixture', 'logical_count': 4,
                                     'affinity': [0, 1, 2, 3]},
                    errors=[])

    def test_green_measurement_is_complete_and_passed(self):
        result = evaluate_speed_measurement(self.measurement(), self.case, self.spec)
        self.assertTrue(result['measurement_complete'])
        self.assertTrue(result['factor_passed'])
        self.assertTrue(result['passed'])

    def test_half_speed_red_is_complete_but_not_green(self):
        result = evaluate_speed_measurement(
            self.measurement(wall_span=20_000_000_000, claimed_factor=1.,
                             claimed_pass=False), self.case, self.spec)
        self.assertTrue(result['measurement_complete'])
        self.assertFalse(result['factor_passed'])
        self.assertFalse(result['passed'])
        self.assertEqual(result['errors'], [])

    def test_claimed_factor_or_factor_passed_cannot_override_endpoints(self):
        for changes in (dict(actual_factor=2.), dict(factor_passed=False)):
            measurement = self.measurement()
            measurement.update(changes)
            result = evaluate_speed_measurement(measurement, self.case, self.spec)
            self.assertTrue(result['errors'], changes)

    def test_incomplete_or_unsafe_measurement_is_infrastructure_failure(self):
        for changes in (dict(measurement_complete=False), dict(armed=True),
                        dict(static_unarmed=False), dict(strict_clock_increase=False),
                        dict(terminal_count=1), dict(window_identity_complete=False),
                        dict(raw_odometry_timestamp_matches=0),
                        dict(timestamp_rewrite_detected=True), dict(errors=['terminal'])):
            measurement = self.measurement()
            measurement.update(changes)
            result = evaluate_speed_measurement(measurement, self.case, self.spec)
            self.assertFalse(result['passed'])
            self.assertTrue(result['errors'], changes)

    def test_run_python_metrics_and_span_are_independently_checked(self):
        for changes in (dict(run_id='other'), dict(observer_python='/usr/bin/python3'),
                        dict(measurement_adapted_states=399),
                        dict(measurement_source_span_ns=1),
                        dict(clock_receipt_hz=0.), dict(cpu_environment={})):
            measurement = self.measurement()
            measurement.update(changes)
            result = evaluate_speed_measurement(
                measurement, self.case, self.spec, expected_run_id='run')
            self.assertTrue(result['errors'], changes)

    def test_nominal_factor_boundaries_are_inclusive_and_outside_is_red(self):
        nominal = {'requested_factor': 1.}
        for source_span, passed in ((34_000_000_000, True),
                                    (46_000_000_000, True),
                                    (33_960_000_000, False),
                                    (46_040_000_000, False)):
            actual = source_span / 40_000_000_000
            measurement = self.measurement(
                wall_span=40_000_000_000, claimed_factor=actual,
                claimed_pass=passed, requested_factor=1., source_span=source_span)
            result = evaluate_speed_measurement(measurement, nominal, self.spec)
            self.assertIs(result['factor_passed'], passed, actual)
            self.assertEqual(result['errors'], [], actual)


class SpeedMatrixContractTest(unittest.TestCase):
    """SIM-SPEED-01整批门禁不能由九个彼此无关的单run GREEN替代。"""

    SELECTION_RULE = (
        'first_clock_at_or_after_first_valid_source_plus_warmup_then_'
        'first_clock_at_or_after_c0_plus_measurement_span')
    PLAN = (
        ('A', 1, 'SPEED_05', .5), ('A', 2, 'SPEED_1', 1.),
        ('A', 3, 'SPEED_2', 2.), ('B', 1, 'SPEED_2', 2.),
        ('B', 2, 'SPEED_1', 1.), ('B', 3, 'SPEED_05', .5),
        ('C', 1, 'SPEED_1', 1.), ('C', 2, 'SPEED_05', .5),
        ('C', 3, 'SPEED_2', 2.))

    @staticmethod
    def identity(path):
        path = Path(path).resolve()
        stat = path.stat()
        return {'path': str(path), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def make_matrix(self, root):
        suite = Path(root).resolve()
        matrix_id = 'matrix-01'
        binary_path = suite / 'jsbsim_bridge'
        tool_path = suite / 'sim01c_run.py'
        config_path = suite / 'sim01c_scenarios.yaml'
        binary_path.write_bytes(b'candidate-binary')
        tool_path.write_text('tool\n')
        config_path.write_text('config\n')
        frozen = {
            'candidate_binary': self.identity(binary_path),
            'tool_identity': self.identity(tool_path),
            'config_identity': self.identity(config_path),
            'boot_id': 'boot-fixture',
        }
        planned = [dict(matrix_id=matrix_id, global_index=index, batch=batch,
                        batch_index=batch_index, scenario=scenario,
                        requested_factor=factor)
                   for index, (batch, batch_index, scenario, factor)
                   in enumerate(self.PLAN, 1)]
        config_plan = [{key: value for key, value in item.items() if key != 'matrix_id'}
                       for item in planned]
        config = {'speed_smoke': {
            'tolerance_fraction': .15,
            'warmup_source_span_ns': '5000000000',
            'measurement_min_source_span_ns': '20000000000',
            'static_unarmed_required': True,
            'strict_clock_increase_required': True,
            'source_timestamp_rewrite_allowed': False,
            'terminal_count': 0,
            'cases': {
                'half': {'requested_factor': .5},
                'nominal': {'requested_factor': 1.},
                'double': {'requested_factor': 2.},
            },
            'matrix': {'selection_rule': self.SELECTION_RULE,
                       'planned_runs': config_plan},
        }}
        actual = []
        for item in planned:
            index, scenario, factor = (item['global_index'], item['scenario'],
                                       item['requested_factor'])
            run = suite / ('speed-%s-m%02d' % (scenario.lower().replace('_', '-'), index))
            run.mkdir()
            run_id = 'matrix-run-%02d' % index
            wall_span = int(20_000_000_000 / factor)
            endpoints = {
                'first_valid_source_ns': 1_000_000_000,
                'warmup_target_ns': 6_000_000_000,
                'c0_ns': 6_000_000_000,
                'c0_receipt_monotonic_ns': 10_000_000_000,
                'c1_ns': 26_000_000_000,
                'c1_receipt_monotonic_ns': 10_000_000_000 + wall_span,
                'selection_rule': self.SELECTION_RULE,
            }
            result = SpeedContractTest().measurement(
                wall_span=wall_span, claimed_factor=factor, claimed_pass=True)
            result.update(run_id=run_id, requested_factor=factor,
                          actual_factor=factor, measurement_wall_span_ns=wall_span,
                          warmup_source_span_ns=5_000_000_000,
                          endpoints=endpoints)
            write_json(run / 'speed-result.json', result)
            observations = [
                {'event_seq': 1, 'event': 'state', 'channel': 'source',
                 'timestamp_ns': 1_000_000_000, 'status': 'valid'},
                {'event_seq': 2, 'event': 'clock', 'timestamp_ns': 5_999_999_999},
                {'event_seq': 3, 'event': 'clock', 'timestamp_ns': 6_000_000_000},
                {'event_seq': 4, 'event': 'clock', 'timestamp_ns': 25_999_999_999},
                {'event_seq': 5, 'event': 'clock', 'timestamp_ns': 26_000_000_000},
            ]
            write_jsonl(run / 'speed-observations.jsonl', observations)
            bridge_command = {'name': 'bridge',
                              'args': [frozen['candidate_binary']['path'], 'rascal'],
                              'environment_overrides': {
                                  'PX4_SIM_SPEED_FACTOR': str(factor)}}
            px4_command = {'name': 'px4', 'args': ['/fixture/px4'],
                           'environment_overrides': {
                               'PX4_SIM_SPEED_FACTOR': str(factor)}}
            manifest = dict(schema_version='0.1', suite_run_id='suite-01',
                            run_id=run_id, scenario=scenario, run=str(run),
                            python=PYTHON, streams_configured=True, errors=[],
                            acceptance_failures=[], armed_commands=False,
                            phase='COMPLETE', exit=0, speed_matrix=item,
                            commands=[bridge_command, px4_command,
                                      {'name': 'stream-HIGHRES_IMU', 'exit': 0},
                                      {'name': 'stream-ODOMETRY', 'exit': 0}],
                            python_process_audit={
                                'passed': True, 'expected': str(Path(PYTHON).resolve()),
                                'processes': [{'executable': str(Path(PYTHON).resolve())}]},
                            bridge_binary=frozen['candidate_binary'],
                            tool_identity=frozen['tool_identity'],
                            config_identity=frozen['config_identity'],
                            boot_id=frozen['boot_id'])
            write_json(run / 'manifest.json', manifest)
            write_json(run / 'cleanup-audit.json', {
                'passed': True, 'forced': [], 'remaining_audited_python_pids': [],
                'ports': [{'free': True}]})
            write_json(run / 'scenario-result.json', {
                'passed': True, 'errors': [], 'case': {
                    'SPEED_05': 'half', 'SPEED_1': 'nominal',
                    'SPEED_2': 'double'}[scenario],
                'measurement_complete': True, 'factor_passed': True,
                'actual_factor': factor})
            actual.append(dict(item, run=str(run), run_id=run_id,
                               phase='COMPLETE', exit=0))
        matrix = dict(schema_version='0.1', matrix_id=matrix_id,
                      suite_run_id='suite-01', planned_runs=planned,
                      actual_runs=actual, errors=[], phase='COMPLETE', exit=0,
                      **frozen)
        write_json(suite / 'speed-matrix-manifest.json', matrix)
        write_json(suite / 'suite-manifest.json', {
            'schema_version': '0.1', 'suite_run_id': 'suite-01',
            'phase': 'COMPLETE', 'exit': 0, 'bridge_binary': frozen['candidate_binary'],
            'tool_identity': frozen['tool_identity'],
            'config_identity': frozen['config_identity'], 'boot_id': frozen['boot_id'],
            'results': [{key: item[key] for key in
                         ('scenario', 'run', 'run_id', 'phase', 'exit')}
                        for item in actual],
            'speed_matrix': {'matrix_id': matrix_id,
                             'manifest': str(suite / 'speed-matrix-manifest.json'),
                             'planned_runs': planned}})
        return suite, config, matrix

    def assert_matrix_red(self, suite, config, needle):
        result = validate_speed_matrix(suite, config)
        self.assertFalse(result['passed'])
        self.assertTrue(any(needle in error for error in result['errors']), result['errors'])

    def test_complete_preregistered_matrix_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            suite, config, _ = self.make_matrix(directory)
            self.assertEqual(validate_speed_matrix(suite, config)['errors'], [])

    def test_missing_normal_or_run_and_reordered_plan_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            suite, config, matrix = self.make_matrix(directory)
            config['speed_smoke']['cases'].pop('nominal')
            self.assert_matrix_red(suite, config, 'half/nominal/double')
            config['speed_smoke']['cases']['nominal'] = {'requested_factor': 1.}
            matrix['actual_runs'].pop()
            write_json(suite / 'speed-matrix-manifest.json', matrix)
            self.assert_matrix_red(suite, config, 'actual sequence')
        with tempfile.TemporaryDirectory() as directory:
            suite, config, matrix = self.make_matrix(directory)
            matrix['planned_runs'][0], matrix['planned_runs'][1] = (
                matrix['planned_runs'][1], matrix['planned_runs'][0])
            write_json(suite / 'speed-matrix-manifest.json', matrix)
            self.assert_matrix_red(suite, config, 'planned sequence')

    def test_result_replacement_and_binary_identity_drift_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            suite, config, matrix = self.make_matrix(directory)
            matrix['actual_runs'][0]['run'] = matrix['actual_runs'][1]['run']
            write_json(suite / 'speed-matrix-manifest.json', matrix)
            self.assert_matrix_red(suite, config, 'run identity')
        with tempfile.TemporaryDirectory() as directory:
            suite, config, matrix = self.make_matrix(directory)
            manifest_path = Path(matrix['actual_runs'][3]['run']) / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['bridge_binary']['sha256'] = '0' * 64
            write_json(manifest_path, manifest)
            self.assert_matrix_red(suite, config, 'candidate binary identity')

    def test_warmup_automatic_endpoints_and_frozen_environment_fail_closed(self):
        mutations = (
            ('warmup target', lambda result, manifest: result['endpoints'].__setitem__(
                'warmup_target_ns', 5_000_000_000)),
            ('automatic c0', lambda result, manifest: result['endpoints'].__setitem__(
                'c0_ns', 6_000_000_001)),
            ('automatic c1', lambda result, manifest: result['endpoints'].__setitem__(
                'c1_ns', 26_000_000_001)),
            ('tool identity', lambda result, manifest: manifest['tool_identity'].__setitem__(
                'sha256', '1' * 64)),
            ('config identity', lambda result, manifest: manifest['config_identity'].__setitem__(
                'sha256', '2' * 64)),
            ('boot_id', lambda result, manifest: manifest.__setitem__('boot_id', 'other-boot')),
        )
        for needle, mutate in mutations:
            with self.subTest(needle=needle), tempfile.TemporaryDirectory() as directory:
                suite, config, matrix = self.make_matrix(directory)
                run = Path(matrix['actual_runs'][0]['run'])
                result = json.loads((run / 'speed-result.json').read_text())
                manifest = json.loads((run / 'manifest.json').read_text())
                mutate(result, manifest)
                write_json(run / 'speed-result.json', result)
                write_json(run / 'manifest.json', manifest)
                self.assert_matrix_red(suite, config, needle)

    def test_manifest_bridge_command_must_execute_frozen_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            suite, config, matrix = self.make_matrix(directory)
            run = Path(matrix['actual_runs'][0]['run'])
            manifest = json.loads((run / 'manifest.json').read_text())
            next(item for item in manifest['commands']
                 if item['name'] == 'bridge')['args'][0] = '/old/init01/jsbsim_bridge'
            write_json(run / 'manifest.json', manifest)
            self.assert_matrix_red(suite, config, 'bridge command')

    def test_missing_run_manifest_matrix_or_candidate_field_fails(self):
        for field, needle in (('speed_matrix', 'matrix identity'),
                              ('bridge_binary', 'candidate binary')):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                suite, config, matrix = self.make_matrix(directory)
                run = Path(matrix['actual_runs'][0]['run'])
                manifest = json.loads((run / 'manifest.json').read_text())
                manifest.pop(field)
                write_json(run / 'manifest.json', manifest)
                self.assert_matrix_red(suite, config, needle)

if __name__ == '__main__':
    unittest.main()
