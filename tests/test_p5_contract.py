"""P5 saved declarations, independent arithmetic and negative contract examples."""
import copy
from fractions import Fraction as F
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from p5_contract import (CASE_IDS, MAX_BYTES, ROOT, bounded, budget, expand, load,
                         load_pair, validate_inputs, validate_pair)
from p5_oracle import verify_seeds


class CombinationContractTest(unittest.TestCase):
    def setUp(self):
        self.inputs,self.expected = load_pair()

    def case(self, identity):
        return next(c for c in self.inputs['cases'] if c['id'] == identity)

    def test_all_nine_groups_and_subcases_are_saved_separately(self):
        self.assertEqual(len(CASE_IDS),37)
        self.assertEqual({c['id'].split('.')[0] for c in self.inputs['cases']},
                         {'S%02d'%i for i in range(1,10)})
        self.assertNotIn('expectations',self.inputs)
        verify_seeds(self.inputs,self.expected)

    def test_recording_clock_events_and_status_reserve_are_counted(self):
        case = self.case('S08.record')
        counts = budget(expand(case,self.inputs['sequences']),case['recording'])
        self.assertEqual(counts['clock'],10)
        self.assertEqual(counts['terrain_events_ceiling'],33)
        case = self.case('S08.overflow')
        self.assertGreater(budget(expand(case,self.inputs['sequences']),case['recording'])['terrain_events_ceiling'],64)

    def test_bool_float_negative_and_overlong_times_are_rejected(self):
        for value in (True, 200000000., -1, 2**63):
            invalid = copy.deepcopy(self.inputs)
            invalid['cases'][0]['events'][1][2] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_inputs(invalid)

    def test_nonfinite_and_boolean_geometry_are_rejected(self):
        for value in (float('nan'),float('inf'),True):
            invalid = copy.deepcopy(self.inputs)
            invalid['profiles']['A']['world_point'][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_inputs(invalid)

    def test_missing_or_duplicate_cases_and_checkpoints_are_rejected(self):
        for target in ('inputs','expected'):
            for duplicate in (False,True):
                a,b = copy.deepcopy((self.inputs,self.expected))
                cases = (a if target == 'inputs' else b)['cases']
                if duplicate:
                    cases[-1] = copy.deepcopy(cases[0])
                else:
                    cases.pop()
                with self.subTest(target=target,duplicate=duplicate), self.assertRaises(ValueError):
                    validate_pair(a,b)
        self.expected['cases'][0]['checks'].append(copy.deepcopy(self.expected['cases'][0]['checks'][0]))
        with self.assertRaises(ValueError): validate_pair(self.inputs,self.expected)

    def test_unknown_version_operation_fields_and_injection_are_rejected(self):
        variants = []
        for field,value in [('schema_version','test.p5.inputs.v2'),('fixture_only',1),('surprise',{})]:
            row = copy.deepcopy(self.inputs); row[field] = value; variants.append(row)
        row = copy.deepcopy(self.inputs); row['cases'][0]['events'][1][1] = 'silent_fallback'; variants.append(row)
        row = copy.deepcopy(self.inputs); row['cases'][0]['events'][1][4]['unknown'] = 1; variants.append(row)
        row = copy.deepcopy(self.inputs); row['cases'][2]['events'][1][4]['mode'] = 'research'; variants.append(row)
        for i,row in enumerate(variants):
            with self.subTest(i=i), self.assertRaises(ValueError): validate_inputs(row)

    def test_training_supervision_is_rejected_at_any_depth(self):
        for field in ('LiDAR','target','occupancy_target','observed_mask'):
            row = copy.deepcopy(self.inputs)
            row['cases'][0]['events'][1][4][field] = []
            with self.subTest(field=field), self.assertRaises(ValueError): validate_inputs(row)
        self.expected['cases'][0]['checks'][0]['values']['target'] = []
        with self.assertRaises(ValueError): validate_pair(self.inputs,self.expected)

    def test_nested_limits_and_text_are_checked_before_serialization(self):
        for value in ('x'*1025,[0]*4097):
            with self.assertRaises(ValueError): bounded(value)
        nested = 0
        for _ in range(22): nested = [nested]
        with self.assertRaises(ValueError): bounded(nested)

    def test_json_duplicate_nonfinite_oversize_and_bad_encoding_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'input.json'
            for value in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e9999}',b'\xff',b' '* (MAX_BYTES+1)):
                path.write_bytes(value)
                with self.subTest(size=len(value)), self.assertRaises(ValueError): load(path)

    def test_unknown_sequence_duplicate_event_and_wall_regression_are_rejected(self):
        for action in ('sequence','duplicate','wall'):
            row = copy.deepcopy(self.inputs)
            events = row['cases'][0]['events']
            if action == 'sequence': events[0]['use'] = 'not_defined'
            elif action == 'duplicate': events[-1][0] = events[-2][0]
            else: events[-1][3] = 1
            with self.subTest(action=action), self.assertRaises(ValueError): validate_inputs(row)

    def test_undeclared_reset_and_m4_registration_overflow_are_rejected(self):
        row = copy.deepcopy(self.inputs)
        row['cases'][0]['events'].append(['reset','clock',0,200000000,{}])
        with self.assertRaises(ValueError): validate_inputs(row)
        self.case('S06.missing')['events'][-1][2] = 1000000000
        with self.assertRaises(ValueError): validate_inputs(self.inputs)

    def test_placeholder_cannot_be_selected_for_cumulative_lane(self):
        case = self.case('S06.missing')
        case['events'][1] = ['fake','sample',110000000,110000000,{}]
        with self.assertRaises(ValueError): validate_inputs(self.inputs)

    def test_complete_recording_cannot_silently_drop_clock_or_expand_budget(self):
        case = self.case('S08.record')
        case['events'][-3][4] = dict(count=65,period_ns=1000000)
        with self.assertRaises(ValueError): validate_inputs(self.inputs)
        self.inputs,_ = load_pair()
        self.inputs['profiles']['limits']['terrain_events'] = 512
        with self.assertRaises(ValueError): validate_inputs(self.inputs)

    def test_recording_lifecycle_must_be_explicit(self):
        self.case('S08.record')['events'][-1][4]['action'] = 'start'
        with self.assertRaises(ValueError): validate_inputs(self.inputs)

    def test_profile_boolean_time_and_unregistered_overlay_are_rejected(self):
        for key,value in [('C',dict(native=1,terrain_registered_to_scene=False)),
                          ('terrain',dict(self.inputs['profiles']['terrain'],registration_interval_ns=[False,3000000000]))]:
            row = copy.deepcopy(self.inputs); row['profiles'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_inputs(row)

    def test_expected_signals_have_explicit_types_and_coverage(self):
        for value in (True,4.,-1):
            row = copy.deepcopy(self.expected)
            row['cases'][0]['checks'][0]['values']['map.revision'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): validate_pair(self.inputs,row)
        self.expected['wire_projections'].pop('terrain_zero')
        with self.assertRaises(ValueError): validate_pair(self.inputs,self.expected)

    def test_orphan_expected_event_and_unknown_signal_are_rejected(self):
        for key,value in [('after','no_such_event'),('values',{'map.magic':'free'})]:
            row = copy.deepcopy(self.expected); row['cases'][0]['checks'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_pair(self.inputs,row)

    def test_independent_arithmetic_detects_changed_geometry_and_interval(self):
        row = copy.deepcopy(self.inputs); row['profiles']['A']['world_point'][0] += .5
        with self.assertRaises(ValueError): verify_seeds(row,self.expected)
        case = next(c for c in self.expected['cases'] if c['id'] == 'S06.arithmetic')
        case['checks'][1]['values']['map.interval'] = ['7/10','9/10']
        with self.assertRaises(ValueError): verify_seeds(self.inputs,self.expected)

    def test_lower_upper_quality_are_outward_bounds_without_using_a_map(self):
        lower,upper = self.expected['wire_projections']['terrain_result']['height_quality.value']
        self.assertLessEqual(F.from_float(lower),F('12.65'))
        self.assertGreaterEqual(F.from_float(upper),F('13.35'))

    def test_contract_and_oracle_do_not_import_business_or_ros(self):
        code = ('import sys; sys.path.insert(0,"tests"); from p5_contract import load_pair; '
                'from p5_oracle import verify_seeds; verify_seeds(*load_pair()); '
                'assert not any(n.startswith(("ufm_","rospy","uav_fusionmap")) for n in sys.modules)')
        result = subprocess.run([sys.executable,'-B','-c',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_private_ownership_is_declaration_only_not_a_public_measurement(self):
        case = next(c for c in self.expected['cases'] if c['id'] == 'S06.fifo')
        self.assertEqual(case['checks'][1]['declared'],dict(sealed_count=1,owner='sealed'))
        case['checks'][1]['values']['map.owner'] = 'sealed'
        with self.assertRaises(ValueError): validate_pair(self.inputs,self.expected)


if __name__ == '__main__':
    unittest.main()
