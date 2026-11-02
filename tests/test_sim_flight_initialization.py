import copy
import json
from pathlib import Path
import tempfile
import unittest

from sim_flight_initialization_fixture import (BINARY_DIR, ROOT, body, event, events, expected,
    header, native, profile, queries, step, steps, topic_fields)
from ufm_simulation import flight_initialization_contract as contract
from ufm_simulation import flight_initialization_observation as observation


class InitializationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        messages = native()['native_messages']
        cls.layouts = observation.layouts_from_texts(messages,messages)

    def reject(self, kind, value):
        with self.assertRaises(ValueError):
            contract.dumps(kind,value,self.layouts,BINARY_DIR)

    def test_n01_independent_query_order_time_and_84_count(self):
        literal = expected()
        self.assertEqual(contract.plan(literal['run_id']),queries())
        self.assertEqual(len(queries()),84)
        for index,cp in enumerate(literal['checkpoints']):
            q = next(q for q in queries() if q['checkpoint']==cp)
            self.assertEqual(event(q)['last_hil_us'],literal['last_hil_us'][index])
            self.assertEqual(event(q)['fdm_time_s'],literal['fdm_after_s'][index])
        self.assertEqual([i['query_index'] for i in queries() if i['kind']=='topic' and i['name']=='estimator_selector_status'],
            literal['topic_query_indices'])

    def test_n02_profile_is_exact_and_independent(self):
        contract.validate_profile(profile())
        for path,value in [(('time','max_step'),2501),(('commands_enabled',),True),
                (('time','step_ns'),4000000.),(('ic','gamma_deg'),0.),(('limits','prepare_wall_ns'),61000000000)]:
            row = profile(); target = row
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            self.reject('profile',row)

    def test_n03_legacy_cross_schema_rejects(self):
        from sim_flight_fixture import header as old_header, record as old_record
        from ufm_simulation.flight_contract import dumps as old_dumps
        self.reject('header',old_header()); self.reject('step',old_record())
        with self.assertRaises(ValueError):old_dumps('record',step())
        q = queries()[0];q['schema_version']='sim_flight_uorb_query.v1'
        self.reject('query',q)

    def test_n04_signed_unit_conversion_and_agl_not_asl(self):
        probe = expected()['units_probe']
        k = header()['initial_kinematics']
        k.update(vel_ned_ftps=probe['raw_ft'],vel_ned_mps=probe['meters'])
        contract.validate_kinematics(k)
        ground = expected()['ground_reference']
        ground[0].update(compression_lbf=probe['raw_lbf'],compression_n=probe['newtons'])
        contract.validate_ground(ground)
        ground[0]['compression_n'] *= -1
        with self.assertRaises(ValueError):contract.validate_ground(ground)
        row=header(); row['initial_kinematics']['agl_m']=row['initial_kinematics']['asl_m']
        self.reject('header',row)
        k['vel_ned_mps'][0]=1.
        with self.assertRaises(ValueError):contract.validate_kinematics(k)

    def test_n05_source_before_after_and_fdm_times(self):
        row=step();row['kinematics_before'],row['kinematics_after']=row['kinematics_after'],row['kinematics_before']
        self.reject('step',row)
        for value in (False,0.,1,2**64):
            row=step();row['hil_sensor_time_us']=value
            self.reject('step',row)
        row=step(2500);contract.validate_step(row)
        row['step_index']=2501;self.reject('step',row)

    def test_n06_ground_and_land_have_different_contracts(self):
        row=step();row['ground_after'][0]['landed']=True;self.reject('step',row)
        row=step();row['ground_before'][0]['wow']=1;self.reject('step',row)
        row=step();row['ground_after'].reverse();self.reject('step',row)

    def test_n07_missing_payload_is_null_not_zero(self):
        contract.validate_step(step())
        for slot in ('actuator','reason'):
            row=step();row[slot]=0;self.reject('step',row)
        row=step();row['properties']['requested']=[0.]*4;self.reject('step',row)
        row=step();row['wall']['actuator_received_ns']=0;self.reject('step',row)

    def test_n08_zero_actuator_and_mapping_order(self):
        row=step(2001,present=True)
        contract.validate_step(row)
        self.assertFalse(row['control_gate_accepted'])
        self.assertNotEqual(row['actuator']['time_usec'],row['hil_sensor_time_us'])
        row['properties']['after'][1]=.01;self.reject('step',row)

    def test_n09_nonzero_armed_and_peer_reject(self):
        for key,value in [('mode',129),('armed',True),('flags',2),('receive_sequence',True)]:
            row=step(2001,present=True);row['actuator'][key]=value;self.reject('step',row)
        row=step(2001,present=True);row['actuator']['controls'][5]=.25;self.reject('step',row)
        row=step(2001,present=True);row['actuator']['peer']['system_id']=2;self.reject('step',row)

    def test_n10_four_states_and_unknown_single_instance(self):
        q=queries()[9]  # estimator_status
        good=event(q)
        contract.dumps('observation',good,self.layouts,BINARY_DIR)
        self.assertEqual(good['observation']['state'],'payload_quality_unavailable')
        q=queries()[8]
        row=event(q)
        self.assertIsNone(row['observation']['instances'][0]['instance'])
        row=event(q,unavailable=True)
        contract.dumps('observation',row,self.layouts,BINARY_DIR)
        row['stdout']='TOPIC: vehicle_imu\n'
        row['observation']=dict(state='payload_unavailable',reason='native_payload_unavailable',instances=[
            dict(instance=None,state='payload_unavailable',fields=None,unavailable_fields=[])],parameter=None)
        contract.dumps('observation',row,self.layouts,BINARY_DIR)
        row=event(queries()[9],changes=dict(vel_test_ratio=.25,pos_test_ratio=.5))
        contract.dumps('observation',row,self.layouts,BINARY_DIR)
        self.assertEqual(row['observation']['state'],'payload')

    def test_n11_mask_same_block_and_exact_nan_token(self):
        row=event(queries()[9],changes=dict(control_mode_flags=7))
        self.reject('observation',row)
        row=event(queries()[9]);row['stdout']=row['stdout'].replace('nan','NaN')
        self.reject('observation',row)
        row=event(queries()[9]);row['observation']['instances'][0]['unavailable_fields']=[]
        self.reject('observation',row)
        row=event(queries()[9]);row['stdout']=row['stdout'].replace("0011)","0010)")
        self.reject('observation',row)

    def test_n12_partial_unknown_duplicate_and_nonfinite_fields(self):
        row=event(queries()[8])
        for stdout in (row['stdout'].replace('    timestamp:', '    unknown:'),
                row['stdout']+'    timestamp: 1\n',
                row['stdout'].replace('0.0000','nan',1),row['stdout'].split('    delta_angle:')[0]):
            bad=copy.deepcopy(row);bad['stdout']=stdout;self.reject('observation',bad)

    def test_n13_typed_float_parameter_and_integer_reject(self):
        for index in range(7):
            row=event(queries()[index]);contract.dumps('observation',row,self.layouts,BINARY_DIR)
        row=event(queries()[3]);row['stdout']=row['stdout'].replace('0.1000','0')
        self.reject('observation',row)
        row=event(queries()[0]);row['stdout']=row['stdout'].replace(': 1033',': 1033.0000')
        self.reject('observation',row)
        row=event(queries()[3]);row['observation']['parameter']['value']=True
        self.reject('observation',row)

    def test_n14_complete_order_no_duplicates_or_extras(self):
        rows=events()
        self.assertEqual(len(observation.validate_events(rows,header()['run_id'],self.layouts,BINARY_DIR)),84)
        for invalid in (rows[:-1],rows+[rows[-1]],rows[:5]+rows[4:]):
            with self.assertRaises(ValueError):observation.validate_events(invalid,header()['run_id'],self.layouts,BINARY_DIR)
        rows[20],rows[21]=rows[21],rows[20]
        with self.assertRaises(ValueError):observation.validate_events(rows,header()['run_id'],self.layouts,BINARY_DIR)

    def test_n15_new_checkpoints_are_not_old_envelopes(self):
        from ufm_simulation.flight_probe_quality import dumps as old_dumps
        row=event(queries()[30])
        with self.assertRaises(ValueError):old_dumps(row,self.layouts,BINARY_DIR)
        row['query']['checkpoint']=250;self.reject('observation',row)

    def test_n16_contiguous_250_steps_settle_and_interrupt(self):
        def interrupted():
            for row in steps():
                if row['step_index']==1999:row['fdm']['hil_sensor']['accel_mps2']=[0.,0.,0.]
                yield row
        summary=contract.validate_steps(header(),interrupted())
        self.assertFalse(summary['input_settled'])
        self.assertFalse(summary['checkpoints']['2000']['input_settled'])
        self.assertTrue(summary['checkpoints']['2500']['input_settled'])

    def group(self, **changes):
        rows=[event(q) for q in queries() if q['checkpoint']==2000 and q['kind']=='topic']
        for index,values in changes.items():
            rows[int(index)]=event(rows[int(index)]['query'],changes=values)
        return rows

    def test_n17_tilt_and_yaw_are_separate_gates(self):
        self.assertTrue(observation.checkpoint_ready(self.group())['ready'])
        for field in ('cs_tilt_align','cs_yaw_align'):
            rows=self.group(**{'3':{field:False}})
            self.assertFalse(observation.checkpoint_ready(rows)['ready'])

    def test_n18_primary_devices_stability_and_topic_ages(self):
        for changes in ({'10':{'primary_instance':1}},{'10':{'instance_changed_count':1}},
                {'2':{'gyro_device_id':999}},{'1':{'gyro_device_id':999}},
                {'5':{'timestamp_sample':1}},{'3':{'timestamp':1}},
                {'0':{'primary_instance':8}}):
            self.assertFalse(observation.checkpoint_ready(self.group(**changes))['ready'])
        # Flags may be one second old while attitude remains within the fast-topic bound.
        stamp=(2000-1)*4000-1000000
        self.assertTrue(observation.checkpoint_ready(self.group(**{'3':{'timestamp':stamp,'timestamp_sample':stamp}}))['ready'])

    def test_n19_health_pose_land_and_output_missing_are_separate(self):
        for changes in ({'0':{'healthy':[False]*9}},{'5':{'q':[0.]*4}},
                {'9':{'landed':False}},{'9':{'at_rest':False}},{'2':{'filter_fault_flags':1}}):
            self.assertFalse(observation.checkpoint_ready(self.group(**changes))['ready'])
        rows=self.group();rows[4]=event(rows[4]['query'],unavailable=True)
        self.assertFalse(observation.checkpoint_ready(rows)['ready'])
        rows=self.group();rows[7]=event(rows[7]['query'],unavailable=True)
        verdict=observation.checkpoint_ready(rows)
        self.assertTrue(verdict['ready']);self.assertFalse(verdict['controls_observed'])

    def test_n20_full_synthetic_ready_keeps_binding_closed(self):
        result=observation.evaluate(header(),steps(present=True),events(),self.layouts,BINARY_DIR)
        for key,value in expected()['expected_summaries']['ready'].items():self.assertEqual(result[key],value,key)
        self.assertEqual(result['records'],2500);self.assertEqual(result['queries'],84)

    def test_n21_complete_collection_can_fail_initialization_at_limit(self):
        result=observation.evaluate(header(),steps(),events(unavailable=True),self.layouts,BINARY_DIR)
        for key,value in expected()['expected_summaries']['unavailable'].items():self.assertEqual(result[key],value,key)
        row=step(2500);row['step_index']=2501;self.reject('step',row)

    def test_n22_time_bounds_cover_write_and_next(self):
        row=event(queries()[0]);row['wall_end_ns']=row['wall_start_ns']+200000001
        self.reject('observation',row)
        row=step();row['wall']['fdm_finished_ns']=1001000001;self.reject('step',row)
        rows=events()
        rows[1]['wall_start_ns']=rows[0]['wall_end_ns']+400000000
        rows[1]['wall_end_ns']=rows[1]['wall_start_ns']+1
        with self.assertRaises(ValueError):observation.validate_events(rows,header()['run_id'],self.layouts,BINARY_DIR)
        row=step();row['wall']['hil_sent_ns']=60000000000;row['wall']['fdm_finished_ns']=60000000100
        with self.assertRaises(ValueError):contract.validate_steps(header(),[row])

    def test_n23_strict_json_encoding_limits_and_supervision(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'\xff',b'{"x":9999999999999999999999}'):
            with self.assertRaises(ValueError):contract.loads('step',raw)
        for field in ('lidar','target','observed_mask'):
            row=step();row['fdm'][field]=[];self.reject('step',row)
        row=step();row['run_id']='x'*121;self.reject('step',row)
        row=event(queries()[0]);row['stdout']='x'*32769;self.reject('observation',row)
        row=step();row['ground_before']*=200;self.reject('step',row)
        row=step();row['kinematics_after']['pqr_radps'][0]=float('inf');self.reject('step',row)
        deep=[];cursor=deep
        for _ in range(9):cursor.append([]);cursor=cursor[0]
        with self.assertRaises(ValueError):contract.bounded(deep)
        with self.assertRaises(ValueError):contract.loads('step',b' '*16385)

    def test_n24_failure_record_and_restart_identity(self):
        row=step(2,failed=True)
        summary=contract.validate_steps(header(),[step(),row])
        self.assertTrue(summary['terminal']);self.assertEqual(summary['fdm_successes'],1)
        with self.assertRaises(ValueError):contract.validate_steps(header(),[step(),row,step(3)])
        with self.assertRaises(ValueError):contract.validate_steps(header(),[step(run_id='other')])
        self.assertEqual(contract.validate_steps(header('new-run'),[step(run_id='new-run')])['records'],1)

    def test_after_first_packet_drop_and_duplicate_sequence_stop(self):
        rows=[step(i,present=i==2001) for i in range(1,2003)]
        with self.assertRaises(ValueError):contract.validate_steps(header(),rows)
        rows[-1]=step(2002,failed=True)
        self.assertTrue(contract.validate_steps(header(),rows)['terminal'])
        rows[-1]=step(2002,present=True);rows[-1]['actuator']['receive_sequence']=1
        with self.assertRaises(ValueError):contract.validate_steps(header(),rows)

    def test_physics_hard_stop_and_continuity(self):
        rows=[step(),step(2)]
        rows[0]['kinematics_after']['agl_m']=-1.
        self.assertTrue(contract.validate_steps(header(),rows[:1])['unsafe'])
        with self.assertRaises(ValueError):contract.validate_steps(header(),rows)
        rows=[step(),step(2)];rows[1]['kinematics_before']['ecef_ft'][0]+=1
        with self.assertRaises(ValueError):contract.validate_steps(header(),rows)

    def test_source_layout_drift_rejects(self):
        sources=native()['native_messages'];altered=dict(sources)
        altered['vehicle_land_detected']+='\nbool unknown\n'
        with self.assertRaises(ValueError):observation.layouts_from_texts(altered,sources)

    def test_armed_owner_argv_projection_and_timestamp_types(self):
        row=event(queries()[13],changes=dict(flag_armed=True));self.reject('observation',row)
        row=event(queries()[0]);row['owner_after']['pid']+=1;self.reject('observation',row)
        row=event(queries()[0]);row['argv'][-2]='set';self.reject('observation',row)
        row=event(queries()[0]);row['last_hil_us']=496000.;self.reject('observation',row)
        row=event(queries()[0]);row['observation']['parameter']['value']=1033.;self.reject('observation',row)

    def test_unknown_instance_is_not_primary_zero(self):
        rows=self.group()
        q=rows[4]['query'];values=topic_fields('estimator_attitude',2000)
        rows[4]=event(q)
        rows[4]['stdout']='TOPIC: estimator_attitude\n'+body('estimator_attitude',values)
        rows[4]['observation']['instances']=rows[4]['observation']['instances'][:1]
        rows[4]['observation']['instances'][0]['instance']=None
        contract.dumps('observation',rows[4],self.layouts,BINARY_DIR)
        self.assertFalse(observation.checkpoint_ready(rows)['ready'])

    def test_roundtrip_and_real_bounded_jsonl_reload(self):
        for kind,value in [('profile',profile()),('header',header()),('step',step()),('query',queries()[0]),
                ('observation',event(queries()[3]))]:
            self.assertEqual(contract.loads(kind,contract.dumps(kind,value,self.layouts,BINARY_DIR),self.layouts,BINARY_DIR),value)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'recording.jsonl'
            path.write_bytes(contract.dumps('header',header())+b'\n'+contract.dumps('step',step())+b'\n')
            self.assertEqual(contract.load_recording(path)['records'],1)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(ValueError):contract.load_recording(path)

    def test_terminal_schema_never_grants_control(self):
        row=dict(schema_version='sim_flight_initialization_terminal.v1',run_id=header()['run_id'],
            clock_id=header()['clock_id'],profile_id=profile()['profile_id'],last_step=2500,
            reason='not_ready_at_limit',wall_ns=3000000000,binding_status='unverified',control_gate_accepted=False)
        self.assertEqual(contract.loads('terminal',contract.dumps('terminal',row)),row)
        row['control_gate_accepted']=True;self.reject('terminal',row)

    def test_budget_guard_before_spawn_after_save_and_next(self):
        contract.check_budget(60000000000,0,0,artifact_bytes=268435456,wire_events=8192)
        for phase in ('before_spawn','after_write','before_next'):
            with self.subTest(phase=phase):
                with self.assertRaises(ValueError):contract.check_budget(60000000001,0,0)
        with self.assertRaises(ValueError):contract.check_budget(120000000001,0)
        with self.assertRaises(ValueError):contract.check_budget(100,0,101)
        for name in ('stream_bytes','query_bytes','wire_bytes','artifact_bytes','wire_events','stream_records','query_records'):
            with self.assertRaises(ValueError):contract.check_budget(0,0,**{name:contract.LIMITS[name]+1})
        with self.assertRaises(ValueError):contract.check_budget(0,0,unknown=0)

    def test_observation_file_reload_and_query_before_next(self):
        rows=events()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'observations.jsonl'
            path.write_bytes(b''.join(contract.dumps('observation',r,self.layouts,BINARY_DIR)+b'\n' for r in rows))
            self.assertEqual(observation.load_observations(path,header()['run_id'],self.layouts,BINARY_DIR),rows)
            path.write_bytes(path.read_bytes()+b'{}\n')
            with self.assertRaises(ValueError):observation.load_observations(path,header()['run_id'],self.layouts,BINARY_DIR)
        # Each event still meets its client/group bound, but the source already advanced.
        for row in rows:
            if row['query']['checkpoint']==125:
                row['wall_start_ns']+=1000000;row['wall_end_ns']+=1000000
        with self.assertRaisesRegex(ValueError,'query_after_next_step'):
            observation.evaluate(header(),steps(),rows,self.layouts,BINARY_DIR)

    def test_future_or_regressed_native_time_cannot_pass(self):
        row=event(queries()[8],changes=dict(timestamp=500001))
        self.reject('observation',row)
        rows=events()
        index=next(i for i,r in enumerate(rows) if r['query']['checkpoint']==250 and r['query']['name']=='vehicle_imu')
        rows[index]=event(rows[index]['query'],changes=dict(timestamp=1,timestamp_sample=1))
        with self.assertRaisesRegex(ValueError,'native_time_regressed'):
            observation.validate_events(rows,header()['run_id'],self.layouts,BINARY_DIR)

    def test_unrun_actuator_is_not_successful_output_chain(self):
        def records():
            for index in range(1,2501):
                row=step(index,present=index>=2499,failed=index==2500)
                if index>=2499:row['actuator']['receive_sequence']=index-2498
                yield row
        result=contract.validate_steps(header(),records())
        self.assertEqual(result['actuator_observations'],2)
        self.assertFalse(result['output_chain_observed'])


if __name__=='__main__':unittest.main()
