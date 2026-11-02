import copy
import json
from pathlib import Path
import tempfile
import unittest

from sim_flight_initialization_selector_fixture import (ROOT,BINARY_DIR,RUN_ID,baseline,body,event,
    events,group,header,literals,physical_header,profile,queries,steps,terminal,values,write_dataset)
from ufm_simulation import flight_initialization_selector as contract
from ufm_simulation import flight_initialization_contract as physical
from ufm_simulation import flight_initialization_observation as original
from ufm_simulation.flight_probe_quality import SEMANTIC_PATHS


class SelectorContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = baseline()
        cls.layouts = contract.layouts_from_texts(cls.frozen['native_messages'],cls.frozen['native_messages'])

    def parse(self, row):
        return contract.parse_native(row['query'],row['stdout'],row['stderr'],row['returncode'],self.layouts)

    def encode(self, kind, value):
        return contract.dumps(kind,value,self.layouts,BINARY_DIR)

    def reject(self, kind, value):
        with self.assertRaises(ValueError):
            self.encode(kind,value)

    def check_events(self, rows):
        return contract.validate_events(rows,RUN_ID,self.layouts,BINARY_DIR)

    def test_s01_historical_exact_eight_explanations(self):
        raw = json.loads((ROOT/'tests/fixtures/sim_flight_initialization_selector_rejection.json').read_text())['raw']
        result = contract.parse_native(queries()[34],raw['stdout'],raw['stderr'],raw['returncode'],self.layouts)
        item = result['instances'][0]
        self.assertEqual(item['unavailable_fields'],literals()['historical_nulls'])
        self.assertEqual(result['state'],'payload_quality_unavailable')
        self.assertIsNone(item['instance'])
        for missing in literals()['historical_nulls']:
            self.assertIsNone(item['fields'][missing['field']][missing['index']])
        self.assertEqual(sum(v is None for n in contract.ARRAYS for v in item['fields'][n]),8)
        rows = group(500)
        rows[1]['observation'] = result
        rows[0] = event(rows[0]['query'],unavailable=True)
        self.assertFalse(contract.checkpoint_ready(rows)['ready'])

    def test_s02_old_strict_rejection_remains(self):
        data = json.loads((ROOT/'tests/fixtures/sim_flight_initialization_selector_rejection.json').read_text())
        raw = data['raw']
        with self.assertRaisesRegex(ValueError,'probe_native_float'):
            original.parse_native(physical.plan(data['evidence_run'])[29],raw['stdout'],raw['stderr'],
                raw['returncode'],self.layouts)

    def test_s03_nine_active_no_tail_and_signed_relative(self):
        row = event(queries()[8],changes=dict(instances_available=9,healthy=[True]*9,
            combined_test_ratio=[1.]*9,relative_test_ratio=[-1.,0.,1.]+[0.]*6,
            accumulated_accel_error=[0.]*4,accumulated_gyro_error=[0.]*4))
        self.assertEqual(self.parse(row)['state'],'payload')
        self.encode('observation',row)

    def test_s04_one_active_exact_tail(self):
        row = event(queries()[8],changes=dict(instances_available=1,primary_instance=0,
            healthy=[True]+[False]*8,combined_test_ratio=[1.]+[None]*8,relative_test_ratio=[0.]+[None]*8))
        self.encode('observation',row)
        self.assertEqual(len(self.parse(row)['instances'][0]['unavailable_fields']),22)

    def test_s05_invalid_range_primary_and_numeric_types(self):
        for name,bad in [('instances_available',0),('instances_available',10),('primary_instance',2),
                ('primary_instance',-1),('primary_instance',True),('timestamp',1.5)]:
            with self.subTest(name=name,bad=bad):
                self.reject('observation',event(queries()[8],changes={name:bad}))

    def test_s06_nan_inside_seen_range_even_unhealthy(self):
        for name in ('combined_test_ratio','relative_test_ratio'):
            data = values('estimator_selector_status',125)
            data[name][0] = None; data['healthy'][0] = False
            self.reject('observation',event(queries()[8],changes=data))

    def test_s07_unseen_finite_and_unseen_healthy_rejected(self):
        for name in ('combined_test_ratio','relative_test_ratio','healthy'):
            data = values('estimator_selector_status',125)
            data[name][8] = True if name=='healthy' else 0.
            self.reject('observation',event(queries()[8],changes=data))

    def test_s08_explanation_bijection_arrays_and_complete_body(self):
        for mutate in ('delete','duplicate','index','reason','order','null','length','field','type'):
            row = event(queries()[8]); item = row['observation']['instances'][0]
            missing = item['unavailable_fields']
            if mutate=='delete':missing.pop()
            elif mutate=='duplicate':missing.append(copy.deepcopy(missing[0]))
            elif mutate=='index':missing[0]['index']=0
            elif mutate=='reason':missing[0]['reason']='native_imu_slot_unavailable'
            elif mutate=='order':missing.reverse()
            elif mutate=='null':item['fields']['combined_test_ratio'][0]=None
            elif mutate=='length':item['fields']['healthy'].pop()
            elif mutate=='type':item['fields']['healthy'][0]=1
            else:row['stdout']=row['stdout'].replace('    gyro_device_id: 222\n','')
            with self.subTest(mutate=mutate):self.reject('observation',row)

    def test_s09_primary_one_gyro_two_accel_zero(self):
        rows = group()
        result = contract.checkpoint_ready(rows)
        self.assertTrue(result['ready'])
        self.assertEqual(result['primary'],1)
        self.assertEqual(result['association'],literals()['association_ready'])

    def test_s10_independent_nan_and_all_missing_veto(self):
        rows = group()
        for index in (1,11):
            rows[index] = event(rows[index]['query'],changes={'accumulated_gyro_error':[None]*4})
            self.encode('observation',rows[index])
        self.assertEqual(contract.association(rows)['reason'],'selector_imu_slot_mismatch')
        self.assertFalse(contract.checkpoint_ready(rows)['ready'])

    def test_s11_duplicate_ids_and_zero_slot_contradictions(self):
        for changes in ({'gyro_device_ids':[222,0,222,0]},
                {'accel_inconsistency_m_s_s':[0.,0.01,0.,0.]},
                {'gyro_healthy':[True,False,True,False]}, {'gyro_priority':[1,0,100,0]},
                {'gyro_inconsistency_rad_s':[0.,0.,-0.1,0.]}):
            with self.subTest(changes=changes):
                self.reject('observation',event(queries()[7],changes=changes))

    def test_s12_missing_changed_unhealthy_primary(self):
        cases = [({'gyro_device_id_primary':0},'imu_primary_identity'),
            ({'gyro_healthy':[False]*4},'imu_slot_unhealthy'),
            ({'gyro_priority':[0]*4},'imu_slot_unhealthy')]
        for changes,reason in cases:
            rows = group()
            for index in (0,12):rows[index]=event(rows[index]['query'],changes=changes)
            self.assertEqual(contract.association(rows)['reason'],reason)
            self.assertFalse(contract.checkpoint_ready(rows)['ready'])
        rows = group();rows[12]=event(rows[12]['query'],changes={'gyro_device_ids':[0,0,223,0]})
        self.assertEqual(contract.association(rows)['reason'],'imu_table_changed')

    def test_s13_nonprimary_slots_mismatch_veto(self):
        rows = group()
        for index in (1,11):
            rows[index]=event(rows[index]['query'],changes={'accumulated_gyro_error':[0.,None,0.,None]})
        self.assertFalse(contract.checkpoint_ready(rows)['ready'])
        rows = group()
        for index in (0,12):
            rows[index]=event(rows[index]['query'],changes={'gyro_device_ids':[999,0,222,0]})
        self.assertEqual(contract.association(rows)['reason'],'selector_imu_slot_mismatch')

    def test_s14_exact_nonfinite_whitelist_and_negative_error(self):
        for token in ('NaN','+nan','-nan','inf','-inf','nan(foo)'):
            row = event(queries()[8]);row['stdout']=row['stdout'].replace('nan',token,1)
            self.reject('observation',row)
        for topic,index in [('sensors_status_imu',7),('vehicle_attitude',13)]:
            row = event(queries()[index]);row['stdout']=row['stdout'].replace('0.0000','nan',1)
            self.reject('observation',row)
        self.reject('observation',event(queries()[8],changes={'accumulated_gyro_error':[None,None,-.1,None]}))

    def test_s15_different_topic_times_never_claim_consumption(self):
        rows = group()
        self.assertNotEqual(rows[0]['observation']['instances'][0]['fields']['timestamp'],
            rows[1]['observation']['instances'][0]['fields']['timestamp'])
        result = contract.association(rows)
        self.assertFalse(result['exact_source_message_verified'])
        self.assertIsNone(result['selector_consumed_imu_timestamp_us'])

    def test_s16_integer_future_regressed_and_stale_time(self):
        for value in (True,1.5,2**64):
            self.reject('observation',event(queries()[7],changes={'timestamp':value}))
        self.reject('observation',event(queries()[7],changes={'timestamp':500001}))
        rows = events();rows[19]=event(queries()[19],changes={'timestamp':1})
        with self.assertRaisesRegex(ValueError,'native_time_regressed'):self.check_events(rows)
        rows = group()
        for index in (0,12):rows[index]=event(rows[index]['query'],changes={'timestamp':1})
        self.assertEqual(contract.association(rows)['reason'],'imu_table_unavailable_or_stale')
        self.assertFalse(contract.checkpoint_ready(rows)['ready'])

    def test_s17_exact_independent_plan_and_profile(self):
        self.assertEqual(contract.plan(RUN_ID),queries())
        self.assertEqual(len(queries()),literals()['query_count'])
        for cp,bounds in zip(literals()['checkpoints'],literals()['group_ranges']):
            rows = [r['query_index'] for r in queries() if r['kind']=='topic' and r['checkpoint']==cp]
            self.assertEqual([min(rows),max(rows)],bounds)
        contract.validate_profile(profile())
        for kind,value in [('profile',profile()),('header',header()),('query',queries()[0])]:
            raw = self.encode(kind,value)
            self.assertEqual(contract.loads(kind,raw,self.layouts,BINARY_DIR),value)
        bad=profile();bad['limits']['group_wall_ns']+=1;self.reject('profile',bad)
        bad=profile();bad['physical_profile']['time']['max_step']=2501;self.reject('profile',bad)

    def test_s18_count_order_argv_owner_and_run_rejections(self):
        rows = events()
        self.assertEqual(len(self.check_events(rows)),98)
        for changed in (rows[:-1],rows+[rows[-1]],rows[:7]+[rows[8],rows[7]]+rows[9:]):
            with self.assertRaises(ValueError):self.check_events(changed)
        row=event(queries()[8]);row['argv'][-1]='2';self.reject('observation',row)
        row=event(queries()[8]);row['owner_after']['pid']+=1;self.reject('observation',row)
        row=event(queries()[8]);row['query']['run_id']='other';self.reject('observation',row)
        rows=events()
        for n in ('owner_before','owner_after'):rows[20][n]['pid']+=1
        with self.assertRaisesRegex(ValueError,'stream_owner'):self.check_events(rows)

    def test_s19_schema_and_physical_path_isolation(self):
        for kind,new,old in [('profile',profile(),physical.profile_reference()),
                ('header',header(),physical_header()),('query',queries()[0],physical.plan(RUN_ID)[0]),
                ('observation',event(queries()[0]),original_event())]:
            self.reject(kind,old)
            with self.assertRaises(ValueError):physical.dumps(kind,new,self.layouts,BINARY_DIR)
        for name,bad in [('steps','../steps.jsonl'),('wire','/tmp/wire'),('header','other/header.json')]:
            row=header();row['physical_files'][name]=bad;self.reject('header',row)

    def test_s20_quality_masks_supervision_and_control_gate(self):
        row=event(queries()[10]);self.encode('observation',row)
        self.reject('observation',event(queries()[10],changes={'control_mode_flags':4}))
        for field in ('target','observed_mask','lidar'):
            row=header();row[field]=[];self.reject('header',row)
            row=event(queries()[8]);row['observation']['instances'][0]['fields'][field]=[]
            self.reject('observation',row)
        row=header();row['control_gate_accepted']=True;self.reject('header',row)
        row=event(queries()[14],changes={'flag_armed':True});self.reject('observation',row)

    def test_s21_bounded_json_text_and_deadlines(self):
        for raw in (b'\xff',b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":1e999}',
                b'['*10000+b']'*10000,b'{"x":1234567890123456789012}',b'x'*262145):
            with self.subTest(raw=raw[:25]):
                with self.assertRaises(ValueError):contract.loads('header',raw,self.layouts,BINARY_DIR)
        row=event(queries()[8]);row['stdout']='x'*32769;self.reject('observation',row)
        row=header();row['run_id']='x'*121;self.reject('header',row)
        row=header();row['profile']['topics']=['x']*513;self.reject('header',row)
        for key in ('session_wall_ns','query_bytes','query_records','artifact_bytes'):
            with self.assertRaises(ValueError):
                if key=='session_wall_ns':physical.check_budget(120000000001,0)
                else:physical.check_budget(0,0,**{key:physical.LIMITS[key]+1})
        row=event(queries()[8]);row['wall_end_ns']=row['wall_start_ns']+200000001;self.reject('observation',row)
        rows=events()
        for row in rows[7:20]:row['wall_start_ns']+=row['query']['query_index']*40000000;row['wall_end_ns']=row['wall_start_ns']+500
        with self.assertRaisesRegex(ValueError,'group_time'):self.check_events(rows)

    def test_s22_both_checkpoints_and_separate_gates(self):
        rows=events()
        result=contract.evaluate(header(),physical_header(),steps(True),terminal(),rows,self.layouts,BINARY_DIR)
        for key,value in literals()['summaries']['ready'].items():self.assertEqual(result[key],value)
        # Earlier readiness cannot substitute for either final checkpoint.
        for cp in (2000,2500):
            changed=events()
            index=next(i for i,r in enumerate(changed) if r['query']['checkpoint']==cp and r['query']['name']=='sensors_status_imu')
            changed[index]=event(changed[index]['query'],unavailable=True)
            result=contract.evaluate(header(),physical_header(),steps(True),terminal(),changed,self.layouts,BINARY_DIR)
            self.assertTrue(result['input_settled']);self.assertTrue(result['output_chain_observed'])
            self.assertFalse(result['initialization_ready']);self.assertFalse(result['passed'])

    def test_s23_actual_private_bytes_and_fixed_file_reread(self):
        with tempfile.TemporaryDirectory() as tmp:
            for ready in (False,True):
                path=Path(tmp)/str(ready);write_dataset(path,ready)
                result=contract.load_recording(path,self.layouts,BINARY_DIR)
                for key,value in literals()['summaries']['ready' if ready else 'missing'].items():
                    self.assertEqual(result[key],value)
        row=event(queries()[8]);raw=self.encode('observation',row)
        self.assertEqual(contract.loads('observation',raw,self.layouts,BINARY_DIR),row)

    def test_s24_source_preflight_and_drift(self):
        px4=ROOT/'.runtime/src/px4-v1.13.3'
        sources={n:(px4/n).read_text() for n in contract.SELECTOR_SOURCES}
        messages={n:(px4/'msg'/(n+'.msg')).read_text() for n in self.frozen['native_messages']}
        quality={n:(px4/n).read_text() for n in SEMANTIC_PATHS}
        self.assertEqual(contract.verify_sources(sources,messages,quality,self.frozen),self.layouts)
        changed=dict(sources);changed[contract.SELECTOR_SOURCES[0]]+='\n'
        with self.assertRaises(ValueError):contract.verify_sources(changed,messages,quality,self.frozen)
        changed=dict(messages);changed['sensors_status_imu']+='\n'
        with self.assertRaises(ValueError):contract.verify_sources(sources,changed,quality,self.frozen)

    def test_physical_boundary_run_terminal_and_partial_stream(self):
        for mutate in ('run','terminal','time','before','after','short'):
            hdr,term,rows=header(),terminal(),events()
            if mutate=='run':hdr['run_id']='other';hdr['clock_id']='sim:other'
            elif mutate=='terminal':term['last_step']=2499;term['reason']='invalid_input'
            elif mutate=='time':term['wall_ns']=1
            elif mutate=='before':rows[7]['wall_start_ns']=1;rows[7]['wall_end_ns']=2
            elif mutate=='after':rows[7]['wall_start_ns']=126000001;rows[7]['wall_end_ns']=126000501
            records=steps(True) if mutate!='short' else iter([next(steps())])
            with self.subTest(mutate=mutate):
                with self.assertRaises(ValueError):contract.evaluate(hdr,physical_header(),records,term,rows,self.layouts,BINARY_DIR)

    def test_unpublished_empty_and_malformed_are_distinct(self):
        row=event(queries()[8],unavailable=True);self.encode('observation',row)
        row['stdout']='TOPIC: estimator_selector_status\n'
        parsed=self.parse(row)
        self.assertEqual(parsed['state'],'payload_unavailable')
        self.assertIsNone(parsed['instances'][0]['fields'])
        for bad in ('TOPIC: estimator_selector_status 2 instances\nInstance 0:\n',
                'TOPIC: estimator_selector_status\n estimator_selector_status\n',
                'never published\nextra\n'):
            row['stdout']=bad
            with self.assertRaises(ValueError):self.parse(row)

    def test_recording_mixed_old_queries_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case';write_dataset(path)
            (path/'queries').mkdir()
            with self.assertRaisesRegex(ValueError,'mixed_query_profiles'):
                contract.load_recording(path,self.layouts,BINARY_DIR)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'case';write_dataset(path)
            (path/'alias').symlink_to(path/'header.json')
            with self.assertRaisesRegex(ValueError,'symlink'):
                contract.load_recording(path,self.layouts,BINARY_DIR)

    def test_availability_faults_and_unaligned_pose_veto(self):
        for changes in ({'gyro_fault_detected':True},{'accel_fault_detected':True}):
            rows=group();rows[1]=event(rows[1]['query'],changes=changes)
            self.assertFalse(contract.checkpoint_ready(rows)['ready'])
        rows=group();rows[4]=event(rows[4]['query'],changes={'cs_tilt_align':False})
        self.assertFalse(contract.checkpoint_ready(rows)['ready'])


def original_event():
    from sim_flight_initialization_fixture import event as old_event
    return old_event(physical.plan(RUN_ID)[0])
