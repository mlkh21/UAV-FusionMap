import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

from sim_flight_probe_fixture import BINARY_DIR,ROOT,RUN_ID,expected,layouts,receipt
from sim_flight_uorb_probe import bounded_client,inspect_owner
from ufm_simulation.flight_probe_contract import (CLIENT_NS,RAW_BYTES,argv_for,plan,parse_output,
    dumps,loads,validate_query,validate_receipt,validate_stream,layouts_from_texts)


class FlightProbeTests(unittest.TestCase):
    def setUp(self):self.formats=layouts()

    def test_frozen_plan_and_read_only_argv(self):
        literals=expected();queries=plan(RUN_ID)
        self.assertEqual(len(queries),literals['query_count'])
        self.assertEqual([q['name'] for q in queries[:9]],literals['topics'])
        self.assertEqual([q['checkpoint'] for q in queries[:18]],[125]*9+[250]*9)
        self.assertEqual(argv_for(BINARY_DIR,queries[0])[1:],literals['query_tail_topic'])
        self.assertEqual(argv_for(BINARY_DIR,queries[19])[1:],literals['query_tail_parameter'])
        for q in queries:self.assertNotIn('-i',argv_for(BINARY_DIR,q))

    def test_bad_queries_cannot_write_or_escape_plan(self):
        for key,value in [('name','SYS_CTRL_ALLOC; arm'),('kind','set'),('query_index',True),
                ('checkpoint',126),('clock_id','sim:foreign'),('schema_version','other'),('extra','lidar')]:
            q=plan(RUN_ID)[0];q[key]=value
            with self.assertRaises(ValueError):argv_for(BINARY_DIR,q)
        for identity in ('bad name','a\n','x'*121):
            with self.assertRaises(ValueError):plan(identity)

    def test_missing_attitude_and_parameter_literals(self):
        literals=expected()
        self.assertEqual(parse_output(plan(RUN_ID)[0],literals['missing_text'],'',0,self.formats),literals['missing_result'])
        self.assertEqual(parse_output(plan(RUN_ID)[5],literals['attitude_text'],'',0,self.formats),literals['attitude_result'])
        self.assertEqual(parse_output(plan(RUN_ID)[19],literals['parameter_text'],'',0,self.formats),literals['parameter_result'])

    def test_multi_instances_preserve_identity(self):
        literal=expected()['attitude_text'];body=literal.split('TOPIC: vehicle_attitude\n',1)[1]
        raw='TOPIC: vehicle_attitude 2 instances\n\nInstance 0:\n'+body+'\nInstance 2:\n'+body
        result=parse_output(plan(RUN_ID)[5],raw,'',0,self.formats)
        self.assertEqual([item['instance'] for item in result['value']['instances']],[0,2])
        for bad in (raw.replace('Instance 2:','Instance 0:'),raw.replace('2 instances','3 instances'),
                raw.replace('Instance 0:','Instance 9:')):
            with self.assertRaises(ValueError):parse_output(plan(RUN_ID)[5],bad,'',0,self.formats)

    def test_incomplete_native_text_not_treated_as_zero_or_missing(self):
        for raw in ('','TOPIC: vehicle_attitude\n','TOPIC: vehicle_attitude\n vehicle_attitude\n',
                'never published\n    timestamp: 0\n','topic too large (600 > 512)\n'):
            with self.assertRaises(ValueError):parse_output(plan(RUN_ID)[5],raw,'',0,self.formats)

    def test_native_advertised_instances_without_payload_are_rejected(self):
        raw='\nTOPIC: estimator_status 6 instances\n'+''.join('\nInstance %d:\n'%i for i in range(6))
        with self.assertRaisesRegex(ValueError,'probe_native_incomplete'):
            parse_output(plan(RUN_ID)[1],raw,'',0,self.formats)

    def test_native_bad_types_nonfinite_and_supervision_reject(self):
        raw=expected()['attitude_text']
        for bad in (raw.replace('496000','True'),raw.replace('1.0000','nan'),raw.replace('1.0000','inf'),
                raw.replace('quat_reset_counter: 0','quat_reset_counter: 256'),
                raw+'    observed_mask: 1\n',raw+'    timestamp: 1\n',raw.replace('0.0000, 0.0000, 0.0000]','0.0000]')):
            with self.assertRaises(ValueError):parse_output(plan(RUN_ID)[5],bad,'',0,self.formats)
        for status,stderr in ((1,''),(0,'error')):
            with self.assertRaises(ValueError):parse_output(plan(RUN_ID)[5],raw,stderr,status,self.formats)

    def test_parameter_exact_name_integer_and_shape(self):
        raw=expected()['parameter_text']
        for bad in (raw.replace('SYS_CTRL_ALLOC','OTHER'),raw.replace(' : 0',' : 0.0'),
                raw.replace(' : 0',' : True'),raw+raw,raw.replace(' : 0',' : nan')):
            with self.assertRaises(ValueError):parse_output(plan(RUN_ID)[19],bad,'',0,self.formats)

    def test_actual_layouts_have_typed_complete_fields(self):
        self.assertEqual(self.formats['vehicle_imu']['delta_angle_dt'],('uint16',1))
        self.assertEqual(self.formats['vehicle_control_mode']['flag_armed'],('bool',1))
        with self.assertRaises(ValueError):layouts_from_texts({})

    def test_native_device_annotation_matches_px4_printer(self):
        from ufm_simulation.flight_probe_contract import _native_field
        raw='1310988 (Type: 0x14, SIMULATION:1 (0x01))'
        self.assertEqual(_native_field(raw,'accel_device_id','uint32',1),1310988)
        for bad in (raw.replace('SIMULATION','OTHER'),raw[:-1],raw+' extra',
                raw.replace('0x14','garbage'),raw.replace('SIMULATION:1','SIMULATION:999')):
            with self.assertRaises(ValueError):_native_field(bad,'accel_device_id','uint32',1)

    def test_receipt_roundtrip_uint64_and_zero_sample_preserved(self):
        value=receipt(6);value['last_hil_us']=2**64-1
        value.update(stdout=expected()['attitude_text'],**expected()['attitude_result'])
        self.assertEqual(loads(dumps(value,self.formats,BINARY_DIR),self.formats,BINARY_DIR),value)
        value['stdout']=value['stdout'].replace('timestamp_sample: 492000 (4000 us before timestamp)','timestamp_sample: 0')
        value['value']['instances'][0]['fields']['timestamp_sample']=0
        validate_receipt(value,self.formats,BINARY_DIR)

    def test_owner_argv_time_flags_version_and_projection_reject(self):
        variants=[]
        for key,item in [('schema_version','other'),('binding_status','matched'),('control_gate_accepted',True),
                ('last_hil_us',-1),('fdm_time_s',True),('wall_start_ns',True),('observed',0),('extra','target')]:
            row=receipt();row[key]=item;variants.append(row)
        row=receipt();row['owner_after']['pid']+=1;variants.append(row)
        row=receipt();row['argv'][-1]='2';variants.append(row)
        row=receipt();row['wall_end_ns']=row['wall_start_ns']+CLIENT_NS+1;variants.append(row)
        row=receipt();row['value']={'instances':[]};variants.append(row)
        for row in variants:
            with self.assertRaises(ValueError):dumps(row,self.formats,BINARY_DIR)

    def test_json_limits_duplicate_key_types_and_depth(self):
        raw=dumps(receipt(),self.formats,BINARY_DIR)
        for bad in (b' '+raw+b' '*262144,raw.replace(b'"returncode":0',b'"returncode":NaN'),
                raw.replace(b'"returncode":0',b'"returncode":0,"returncode":0'),b'\xff',b'['*10000):
            with self.assertRaises(ValueError):loads(bad,self.formats,BINARY_DIR)
        row=receipt();row['stdout']='x'*(RAW_BYTES+1)
        with self.assertRaises(ValueError):dumps(row,self.formats,BINARY_DIR)

    def test_complete_stream_and_missing_semantics(self):
        rows=[receipt(i) for i in range(1,22)]
        summary=validate_stream(iter(rows),RUN_ID,self.formats,BINARY_DIR)
        self.assertEqual((summary['queries'],summary['missing_queries']),(21,18))
        self.assertFalse(summary['control_gate_accepted'])
        for bad in (rows[:-1],rows+[rows[-1]],rows[::-1]):
            with self.assertRaises(ValueError):validate_stream(iter(bad),RUN_ID,self.formats,BINARY_DIR)

    def test_stream_parameter_owner_and_group_deadline(self):
        rows=[receipt(i) for i in range(1,22)]
        rows[19]['stdout']=rows[19]['stdout'].replace(' : 0',' : 1');rows[19]['value']['integer']=1
        with self.assertRaises(ValueError):validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)
        rows=[receipt(i) for i in range(1,22)];rows[9]['owner_before']['start_ticks']+=1;rows[9]['owner_after']['start_ticks']+=1
        with self.assertRaises(ValueError):validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)
        rows=[receipt(i) for i in range(1,22)]
        for row in rows[4:]:row['wall_start_ns']+=400000000;row['wall_end_ns']+=400000000
        with self.assertRaises(ValueError):validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)

    def test_process_identity_is_checked_before_any_query(self):
        with self.assertRaises(ValueError):inspect_owner(os.getpid(),BINARY_DIR/'px4',Path.cwd())

    def client(self,code):
        with tempfile.TemporaryDirectory() as directory:
            processes=SimpleNamespace(run=Path(directory),env=dict(os.environ),children={},manifest={'commands':[]},
                stopped=set(),forced=[])
            result=bounded_client([sys.executable,'-B','-c',code],time.monotonic_ns()+CLIENT_NS,processes,'test-query')
            self.assertIsNotNone(processes.children['test-query'].poll())
            return result

    def test_real_bounded_subprocess_output_and_errors(self):
        self.assertEqual(self.client('print("never published")')['stdout'],'never published\n')
        self.assertEqual(self.client('import sys;sys.exit(3)')['returncode'],3)
        self.assertIn('error',self.client('import sys;sys.stdout.buffer.write(b"x"*40000)'))
        self.assertIn('error',self.client('import time;time.sleep(2)'))
        bad=self.client('import sys;sys.stdout.buffer.write(bytes([255]))')
        self.assertEqual(bad['stdout_hex'],'ff')


if __name__=='__main__':unittest.main()
