"""Offline IC, presence, actuator causality observations and bounded recording checks."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sim_flight_fixture import ROOT,cases,expected,header,profile,record
from ufm_simulation import flight_contract as f


class FlightContractTests(unittest.TestCase):
    def test_saved_ic_channels_limits_and_sampling_are_independent(self):
        value=profile();literal=expected()
        f.validate_profile(value);f.validate_ic(literal['ic'])
        self.assertEqual(value['ic'],literal['ic'])
        self.assertEqual(value['actuator_channels'],literal['channels'])
        for key,limit in literal['limits'].items():self.assertEqual(value['limits'][key],limit)
        stamps=[i*4000000 for i in range(10001) if f.capture_step(i)]
        self.assertEqual((stamps[0],stamps[-1],len(stamps)),(30100000000,40000000000,100))
        self.assertFalse(f.capture_step(7500))

    def test_profile_cannot_enable_commands_or_relax_bounds(self):
        for path,value in ((('commands_enabled',),True),(('observation_only',),False),
                (('simulation_only',),False),(('mode',),'offboard'),(('schema_version',),'v2'),
                (('model','bridge_config'),'../4D-Radar-Diffusion/params.json'),
                (('time','max_step'),10001),(('time','prepare_steps'),0),
                (('command_policy','allowed'),['arm']),(('limits','control_events'),8192)):
            data=profile();node=data
            for part in path[:-1]:node=node[part]
            node[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):f.validate_profile(data)

    def test_ic_requires_agl_explicit_ground_and_no_conflicting_gamma(self):
        for key,value in (('altitude_reference','MSL'),('altitude_m',8.),('gamma_deg',0.),
                ('terrain_elevation_m',0.),('true_airspeed_mps',5.),('phi_theta_psi_deg',[0.,5.,90.]),
                ('latitude_deg',True)):
            data=copy.deepcopy(expected()['ic']);data[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):f.validate_ic(data)

    def test_asymmetric_float32_mapping_and_negative_zero_survive(self):
        for probe in expected()['mapping_probes']:
            self.assertEqual(f.map_controls(probe['controls']),probe['properties'])
        value=record(1,present=True);value['actuator']['controls'][0]=-0.
        raw=f.dumps('record',value)
        self.assertIn(b'-0.0',raw)
        self.assertEqual(f.loads('record',raw),value)

    def test_control_vector_rejects_nonfinite_bounds_boolean_and_lost_float32(self):
        for index,value in ((0,True),(0,float('nan')),(0,float('inf')),(0,1.01),(4,-.1),(5,.3)):
            controls=[0.]*16;controls[index]=value
            with self.subTest(index=index,value=value),self.assertRaises(ValueError):f.map_controls(controls)
        for controls in ([0]*15,[0]*17,tuple([0]*16)):
            with self.assertRaises(ValueError):f.map_controls(controls)

    def test_missing_is_not_a_disarmed_observation(self):
        missing,observed=record(),record(2,present=True)
        f.validate_record(missing);f.validate_record(observed)
        self.assertIsNone(missing['actuator']);self.assertFalse(observed['actuator']['armed'])
        for path,value in ((('has_actuator',),0),(('actuator',),observed['actuator']),
                (('properties','requested'),[0]*4),(('wall','actuator_received_ns'),0)):
            data=copy.deepcopy(missing);node=data
            for part in path[:-1]:node=node[part]
            node[path[-1]]=value
            with self.assertRaises(ValueError):f.validate_record(data)

    def test_present_flags_mode_and_armed_consistency(self):
        for key,value in (('armed',0),('armed',True),('mode',0),('mode',257),('mode',True),
                ('flags',2),('flags',True),('receive_sequence',0),('time_usec',-.1),('time_usec',2**64)):
            data=record(2,present=True);data['actuator'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):f.validate_record(data)
        data=record(2,present=True);data['actuator']['controls'][2]=.25
        with self.assertRaisesRegex(ValueError,'disarmed'):f.validate_record(data)

    def test_peer_run_clock_version_step_and_unknown_fields_reject(self):
        for path,value in ((('run_id',),''),(('clock_id',),'foreign'),(('schema_version',),'v2'),
                (('source_step',),1),(('step_index',),True),(('step_index',),10001),
                (('actuator','peer','address'),'192.168.1.1'),(('actuator','peer','port'),True),
                (('actuator','peer','system_id'),2),(('binding_status',),'matched')):
            data=record(1,present=True);node=data
            for part in path[:-1]:node=node[part]
            node[path[-1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):f.validate_record(data)

    def test_training_supervision_and_arbitrary_commands_reject_at_nested_boundaries(self):
        for path in ((),('actuator',),('actuator','peer'),('properties',),('fdm',),('wall',)):
            for key in ('lidar','target','observed_mask','shell','command'):
                data=record(1,present=True);node=data
                for part in path:node=node[part]
                node[key]=[]
                with self.subTest(path=path,key=key),self.assertRaises(ValueError):f.validate_record(data)

    def test_actual_readback_tolerance_without_changing_requested_values(self):
        data=cases()['armed_probe'];data['properties']['after'][0]+=.0000005
        f.validate_record(data)
        data['properties']['after'][0]+=.000002
        with self.assertRaisesRegex(ValueError,'readback'):f.validate_record(data)
        data=cases()['armed_probe'];data['properties']['requested'][0]+=.0000001
        with self.assertRaises(ValueError):f.validate_record(data)

    def test_fdm_run_missing_failed_and_success_are_distinct(self):
        for value in cases().values():f.validate_record(value)
        for key,value in (('ran',1),('result',1),('sim_time_after_s',.005),('sim_time_before_s',True),
                ('sim_time_before_s',-.001)):
            data=record();data['fdm'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):f.validate_record(data)
        data=cases()['not_run'];data['fdm']['result']=False
        with self.assertRaises(ValueError):f.validate_record(data)

    def test_wall_time_is_integer_ordered_and_separate_from_source(self):
        data=record(2,present=True)
        for key,value in (('hil_sent_ns',10.),('actuator_received_ns',True),
                ('actuator_received_ns',19),('properties_applied_ns',25),('fdm_finished_ns',-1)):
            bad=copy.deepcopy(data);bad['wall'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):f.validate_record(bad)
        self.assertNotEqual(data['actuator']['time_usec'],data['hil_sensor_time_us'])
        f.validate_record(data)

    def test_header_contract_and_observation_only_policy(self):
        f.validate_header(header())
        for key,value in (('initial_properties',[.1,0,0,0]),('initial_wall_ns',False),('clock_id','wrong')):
            bad=header();bad[key]=value
            with self.assertRaises(ValueError):f.validate_header(bad)
        f.validate_record(cases()['armed_probe'])
        with self.assertRaisesRegex(ValueError,'observation_only_armed'):
            f.validate_recording(header(),[record(),record(2,present=True),cases()['armed_probe']])

    def test_stream_saved_summary_and_input_isolation(self):
        rows=[record(),record(2,present=True)];before=copy.deepcopy(rows)
        result=f.validate_recording(header(),iter(rows))
        for key,value in expected()['stream_reference'].items():self.assertEqual(result[key],value)
        self.assertEqual(rows,before)
        self.assertFalse(result['control_gate_accepted'])

    def test_stream_identity_order_peer_sequence_and_property_continuity(self):
        for mutate in ('run','step','peer','sequence','properties','hil_time','actuator_time','wall'):
            rows=[record(1,present=True),record(2,present=True)]
            rows[0]['actuator']['receive_sequence']=1;rows[1]['actuator']['receive_sequence']=2
            data=rows[1]
            if mutate=='run':data.update(run_id='other',clock_id='sim:other')
            elif mutate=='step':data.update(step_index=1,source_step=0);data['fdm'].update(sim_time_before_s=0.,sim_time_after_s=.004)
            elif mutate=='peer':data['actuator']['peer']['port']+=1
            elif mutate=='sequence':data['actuator']['receive_sequence']=1
            elif mutate=='properties':data['properties']['before'][0]=.25
            elif mutate=='hil_time':data['hil_sensor_time_us']=0
            elif mutate=='actuator_time':data['actuator']['time_usec']=1
            else:data['wall'].update(hil_sent_ns=10,actuator_received_ns=11,properties_applied_ns=12,fdm_finished_ns=13)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):f.validate_recording(header(),rows)

    def test_missing_after_first_actuator_cannot_advance_or_reuse_old_output(self):
        rows=[record(),record(2,present=True),record(3)]
        with self.assertRaisesRegex(ValueError,'missing_after_bootstrap'):f.validate_recording(header(),rows)
        rows[-1]=cases()['not_run']
        self.assertTrue(f.validate_recording(header(),rows)['terminal'])

    def test_bootstrap_source_and_wall_boundaries_are_both_required(self):
        self.assertEqual(f.validate_recording(header(),(record(i) for i in range(1,501)))['last_step'],500)
        with self.assertRaisesRegex(ValueError,'missing_after_bootstrap'):
            f.validate_recording(header(),(record(i) for i in range(1,502)))
        data=record();data['wall']['fdm_finished_ns']=5000000000
        f.validate_recording(header(),[data])
        data['wall']['fdm_finished_ns']+=1
        with self.assertRaisesRegex(ValueError,'missing_after_bootstrap'):f.validate_recording(header(),[data])

    def test_source_tolerance_and_uint64_wire_time_are_not_replaced_by_wall_time(self):
        data=record();data['fdm']['sim_time_after_s']=.0040000009
        f.validate_record(data)
        data['fdm']['sim_time_after_s']=.0040000011
        with self.assertRaisesRegex(ValueError,'step_time'):f.validate_record(data)
        data=record(2,present=True)
        data['fdm'].update(sim_time_before_s=.0039999991,sim_time_after_s=.0080000009)
        with self.assertRaisesRegex(ValueError,'step_time'):f.validate_record(data)
        data=record(1,present=True);data['actuator']['time_usec']=2**64-1
        self.assertEqual(f.loads('record',f.dumps('record',data))['actuator']['time_usec'],2**64-1)

    def test_failed_fdm_is_terminal_and_new_validation_starts_fresh(self):
        rows=[record(),record(2,present=True),cases()['fdm_failed']]
        self.assertTrue(f.validate_recording(header(),rows)['terminal'])
        with self.assertRaisesRegex(ValueError,'after_terminal'):f.validate_recording(header(),rows+[record(4,present=True)])
        self.assertFalse(f.validate_recording(header(),[record()])['terminal'])
        with self.assertRaises(ValueError):f.validate_recording(header(),[])

    def test_generator_cannot_mutate_previously_validated_property_state(self):
        def changed():
            first=record();yield first
            first['properties']['after'][0]=.25
            second=record(2,present=True);second['properties']['before'][0]=.25
            yield second
        with self.assertRaisesRegex(ValueError,'discontinuity'):f.validate_recording(header(),changed())

    def test_json_roundtrip_and_recording_actual_bytes(self):
        for kind,value in [('profile',profile()),('ic',expected()['ic']),('header',header())]+[
                ('record',value) for value in cases().values()]:
            self.assertEqual(f.loads(kind,f.dumps(kind,value)),value)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'recording.jsonl'
            raw=f.dumps('header',header())+b'   \n'+b'\n'.join(f.dumps('record',r) for r in [record(),record(2,present=True)])+b'\n'
            path.write_bytes(raw)
            self.assertEqual(f.load_recording(path)['source_bytes'],len(raw))
            self.assertEqual(f.load_profile(ROOT/'configs/sim_flight_fixture.json'),profile())

    def test_json_duplicate_nonfinite_encoding_depth_and_byte_limits(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}',b'\xff',
                b'{"a":'+b'9'*400+b'}',b'['*1100+b'0'+b']'*1100,b' '*262145):
            with self.subTest(raw=raw[:30]),self.assertRaises(ValueError):f.loads('profile',raw)
        with self.assertRaises(ValueError):f.loads('record',b' '*16385)
        with self.assertRaises(ValueError):f.loads('unknown',b'{}')

    def test_structure_text_and_utf8_limits_before_encoding(self):
        for value in ({'x':'a'*129},{'x':'\u4e2d'*43},{'x':'\ud800'},{'x':'a\0b'},
                {'x':[0]*513},{'x':{str(i):0 for i in range(65)}},
                {'x':[[[[[[[[[0]]]]]]]]]}, {'x':10**400}):
            with self.subTest(value=str(value)[:30]),self.assertRaises(ValueError):f.dumps('profile',value)
        raw=f.dumps('profile',profile())
        self.assertEqual(f.loads('profile',raw+b' '*(262144-len(raw))),profile())

    def test_stream_budget_checks_precede_consuming_further_records(self):
        cap=len(f.dumps('header',header()))+len(f.dumps('record',record()))+2
        with patch.object(f,'STREAM_BYTES',cap):
            limited=header();limited['profile']['limits']['control_log_bytes']=cap
            with self.assertRaisesRegex(ValueError,'byte_limit'):
                f.validate_recording(limited,[record(),record(2,present=True)])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'padded.jsonl'
            with patch.object(f,'STREAM_BYTES',cap):
                limited=header();limited['profile']['limits']['control_log_bytes']=cap
                path.write_bytes(f.dumps('header',limited)+b' '*cap+b'\n'+f.dumps('record',record())+b'\n')
                with self.assertRaisesRegex(ValueError,'recording_limit'):f.load_recording(path)
        with patch.object(f,'STREAM_RECORDS',1):
            limited=header();limited['profile']['limits']['stream_records']=1
            with self.assertRaisesRegex(ValueError,'count_limit'):
                f.validate_recording(limited,[record(),record(2,present=True)])

    def test_private_module_import_does_not_load_runtime_stacks(self):
        command=[sys.executable,'-B','-c',
            'import sys; import ufm_simulation.flight_contract; assert not any(n in sys.modules for n in ("rospy","pymavlink","torch","ufm_scene_contract"))']
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=10.)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
