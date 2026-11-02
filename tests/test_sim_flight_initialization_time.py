import importlib.util
from fractions import Fraction
import json
from unittest import TestCase

from sim_flight_initialization_selector_fixture import ROOT
from sim_flight_initialization_time_build import module_from
from sim_flight_initialization_time_probe import build_probe,execute,literals,check_wire,verify
from ufm_simulation import flight_initialization_contract as physical


class IntegerTimeTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary=build_probe()
        cls.timer=module_from(ROOT/'simulation/flight_initialization_time/adapt.py','test_time_adapter')
        cls.old=module_from(ROOT/'simulation/flight_bridge/adapt.py','test_original_time_adapter')
        cls.bridge=ROOT/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge'

    def test_real_cpp_boundaries_and_actual_mavlink_bytes(self):
        result=verify(self.binary)
        self.assertEqual(result['boundary_cases'],16)
        self.assertEqual(result['trajectory_records'],2501)
        self.assertEqual(result['actual_mavlink_packets'],5016)

    def test_historical_source_is_accepted_without_accepting_old_wire(self):
        value=literals()['old_failure']
        self.assertEqual(int(value['seconds']*1e6),value['old_truncated_us'])
        self.assertLessEqual(abs(Fraction(value['seconds'])*1000000000-value['source_step']*4000000),1)
        row=execute(self.binary)[2]
        check_wire(row,value['required_us'])
        self.assertNotEqual(value['old_truncated_us'],row['time_usec'])
        physical._time(value['seconds'],value['source_step'])

    def test_both_sender_calls_change_only_in_new_copies(self):
        bridge=(self.bridge/'src/jsbsim_bridge.cpp').read_text()
        old=self.old.adapt('jsbsim_bridge.cpp',bridge)
        adapted=self.timer.adapt('jsbsim_bridge.cpp',old)
        self.assertIn('static_cast<uint64_t>(simtime * 1e6)',old)
        self.assertIn('flight::source_time_us(simtime, 1)',adapted)
        self.assertEqual(adapted.count('_fdmexec->Run();'),1)
        self.assertEqual(adapted.count('flight::allow_run()'),1)
        gps=(self.bridge/'src/sensor_gps_plugin.cpp').read_text()
        patched=self.timer.adapt('sensor_gps_plugin.cpp',gps)
        self.assertIn('flight::source_time_us(_sim_ptr->GetSimTime(), 2)',patched)
        self.assertEqual((self.bridge/'src/jsbsim_bridge.cpp').read_text(),bridge)
        self.assertEqual((self.bridge/'src/sensor_gps_plugin.cpp').read_text(),gps)

    def test_duplicate_or_drifting_source_is_rejected(self):
        for name,path in [('jsbsim_bridge.cpp',self.bridge/'src/jsbsim_bridge.cpp'),
                ('sensor_gps_plugin.cpp',self.bridge/'src/sensor_gps_plugin.cpp'),
                ('diagnostics.cpp',ROOT/'simulation/flight_initialization/diagnostics.cpp')]:
            source=path.read_text();adapted=self.timer.adapt(name,source)
            with self.assertRaises(ValueError):self.timer.adapt(name,adapted)
            with self.assertRaises(ValueError):self.timer.adapt(name,source+source)
        with self.assertRaises(ValueError):self.timer.adapt('unexpected.cpp','')

    def test_live_hook_requires_current_transaction_and_bounded_receipts(self):
        source=(ROOT/'simulation/flight_initialization/diagnostics.cpp').read_text()
        patched=self.timer.adapt('diagnostics.cpp',source)
        self.assertIn('!emitted && step>=1 && step<=2500',patched)
        self.assertIn('ufm_time::grid_time_us(seconds,step-1)',patched)
        self.assertIn('time_record_count<5000',patched)
        self.assertIn('time-grid.jsonl',patched)
        self.assertIn('sensor.time_usec==(step-1)*4000ULL',patched)

    def test_invalid_source_never_produces_wire_fields(self):
        rows=execute(self.binary)
        for expected,row in zip(literals()['cases'],rows):
            if not expected['accepted']:self.assertEqual(row,{'accepted':False})

    def test_source_fixture_keeps_limits_and_no_control(self):
        value=literals()['runtime_limits']
        self.assertEqual(value,dict(steps=2500,queries=98,source_seconds=10,
            binding_status='unverified',control_gate_accepted=False))
        self.assertEqual(physical.LIMITS['group_wall_ns'],400000000)
