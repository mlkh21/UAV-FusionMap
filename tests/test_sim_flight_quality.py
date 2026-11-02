import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sim_flight_quality_fixture import (BINARY_DIR, ROOT, RUN_ID, baseline, event, expected,
    finite_input, layouts, status_body, status_projection, status_text)
from sim_flight_probe_fixture import owner, receipt
from sim_flight_diagnostic_fixture import event as v1_event, mode_text
from sim_flight_uorb_quality import UorbQualityDiagnostics, source_preflight
from ufm_simulation import flight_probe_contract as snapshot
from ufm_simulation import flight_probe_diagnostic as v1
from ufm_simulation import flight_probe_quality as quality


class FlightQualityTests(unittest.TestCase):
    def setUp(self):
        self.formats = layouts()
        self.literal = expected()

    def parse(self, raw, index=2, stderr='', code=0):
        return quality.parse_native(snapshot.plan(RUN_ID)[index-1],raw,stderr,code,self.formats)

    def test_q01_archived_six_instances_and_twelve_explicit_descriptors(self):
        raw = baseline()['archived_raw']['stdout']
        result = self.parse(raw)
        self.assertEqual(result['state'],'payload_quality_unavailable')
        self.assertEqual([i['instance'] for i in result['instances']],self.literal['archived_instances'])
        self.assertEqual(result['instances'][0],status_projection(instance=0))
        self.assertEqual(sum(len(i['unavailable_fields']) for i in result['instances']),12)
        for item in result['instances']:
            self.assertEqual(item['unavailable_fields'],self.literal['unavailable_descriptors'])
            self.assertIsNone(item['fields']['vel_test_ratio'])
        for parser in (v1.parse_native,snapshot.parse_output):
            with self.assertRaises(ValueError):parser(snapshot.plan(RUN_ID)[1],raw,'',0,self.formats)

    def test_q02_finite_and_zero_preserved_without_descriptors(self):
        result=self.parse(status_text(vel='0.0000',pos='-0.2500'))
        self.assertEqual(result['state'],'payload')
        self.assertEqual(result['instances'],[status_projection(vel=0.0,pos=-.25)])

    def test_q03_single_permitted_field(self):
        for vel,pos,ev,ep in [('nan','0.0000',None,0.0),('0.2500','nan',.25,None)]:
            result=self.parse(status_text(vel=vel,pos=pos))
            self.assertEqual(result['instances'],[status_projection(vel=ev,pos=ep)])

    def test_q04_gps_disallows_both_nan_fields(self):
        with self.assertRaises(ValueError):self.parse(status_text(mask=4))

    def test_q05_ev_velocity_only_affects_velocity_guard(self):
        with self.assertRaises(ValueError):self.parse(status_text(mask=1<<24, pos='0.0000'))
        self.assertEqual(self.parse(status_text(mask=1<<12,pos='0.0000'))['state'],'payload_quality_unavailable')

    def test_q06_ev_position_only_affects_position_guard(self):
        with self.assertRaises(ValueError):self.parse(status_text(mask=1<<12,vel='0.0000'))
        self.assertEqual(self.parse(status_text(mask=1<<24,vel='0.0000'))['state'],'payload_quality_unavailable')

    def test_q07_flow_is_conservatively_rejected_for_velocity(self):
        for mask in (8,8|(1<<12)):
            with self.assertRaises(ValueError):self.parse(status_text(mask=mask,pos='0.0000'))
        self.assertEqual(self.parse(status_text(mask=8,vel='0.0000'))['state'],'payload_quality_unavailable')

    def test_q08_exact_nan_only(self):
        for token in ('NaN','-nan','nan(payload)','inf','-inf','1e999','nan (none)'):
            with self.assertRaises(ValueError):self.parse(status_text(vel=token))

    def test_q09_other_fields_never_allow_nonfinite(self):
        for field in ('mag_test_ratio','pos_horiz_accuracy','hgt_test_ratio','time_slip'):
            raw=status_text()
            import re
            raw=re.sub(r'    '+field+r': [^\n]+','    '+field+': nan',raw)
            with self.assertRaises(ValueError):self.parse(raw)
        for topic,index in [('vehicle_attitude',6),('actuator_outputs',9),('vehicle_imu',1)]:
            raw,_=finite_input(topic)
            with self.assertRaises(ValueError):self.parse(raw.replace('0.0000','nan',1),index)

    def test_q10_complete_unique_fields_required(self):
        raw=status_text()
        for bad in (raw.replace('    time_slip: 0.0000\n',''),raw+'    target: 0\n',
                raw+'    observed_mask: 0\n',raw+'    timestamp: 1\n',
                raw.replace('[0.0006, 0.0047, 1.4457]','[0.0006]')):
            with self.assertRaises(ValueError):self.parse(bad)

    def test_q11_same_block_flags_and_binary_annotation(self):
        raw=status_text()
        for bad in (raw.replace('537002496 (0b','537002497 (0b'),
                raw.replace(" (0b0010'0000'0000'0010'0000'0010'0000'0000)",''),
                raw.replace('control_mode_flags: 537002496','control_mode_flags: True')):
            with self.assertRaises(ValueError):self.parse(bad)

    def test_q12_bad_instance_rejects_whole_query(self):
        raw='TOPIC: estimator_status 2 instances\nInstance 0:\n'+status_body()+'Instance 1:\n'+status_body(mask=4)
        with self.assertRaises(ValueError):self.parse(raw)

    def test_q13_mixed_blocks_keep_quality_fields_and_unknown_single_label(self):
        raw=('TOPIC: estimator_status 3 instances\nInstance 0:\n'+status_body(vel='0.0000',pos='0.0000')+
            'Instance 2:\n'+status_body()+'Instance 5:\n')
        result=self.parse(raw)
        self.assertEqual(result['state'],'payload_unavailable')
        self.assertEqual(result['instances'][1],status_projection(instance=2))
        self.assertIsNone(result['instances'][2]['fields'])
        self.assertIsNone(self.parse(status_text())['instances'][0]['instance'])
        for bad in (raw.replace('3 instances','2 instances'),raw.replace('Instance 2:','Instance 0:'),
                raw.replace('Instance 5:','Instance 9:')):
            with self.assertRaises(ValueError):self.parse(bad)

    def quality_row(self):
        row=event(2)
        row.update(stdout=status_text(),observation=dict(state='payload_quality_unavailable',
            reason='native_optional_quality_unavailable',instances=[status_projection()],parameter=None))
        return row

    def test_q14_nulls_descriptors_and_tokens_must_agree(self):
        row=self.quality_row()
        self.assertEqual(quality.loads(quality.dumps(row,self.formats,BINARY_DIR),self.formats,BINARY_DIR),row)
        variants=[]
        for key,value in [('unavailable_fields',[]),('unavailable_fields',self.literal['unavailable_descriptors'][::-1])]:
            bad=copy.deepcopy(row);bad['observation']['instances'][0][key]=value;variants.append(bad)
        bad=copy.deepcopy(row);bad['observation']['instances'][0]['fields']['vel_test_ratio']=0.0;variants.append(bad)
        bad=copy.deepcopy(row);bad['observation']['instances'][0]['unavailable_fields'][0]['reason']='other';variants.append(bad)
        bad=copy.deepcopy(row);bad['observation']['instances'][0]['fields']['filter_fault_flags']=False;variants.append(bad)
        for bad in variants:
            with self.assertRaises(ValueError):quality.dumps(bad,self.formats,BINARY_DIR)

    def test_q15_schema_crossover_duplicate_and_nonfinite_json(self):
        row=self.quality_row()
        for codec in (snapshot,v1):
            with self.assertRaises(ValueError):codec.dumps(row,self.formats,BINARY_DIR)
        for old in (receipt(),v1_event()):
            with self.assertRaises(ValueError):quality.dumps(old,self.formats,BINARY_DIR)
        raw=quality.dumps(row,self.formats,BINARY_DIR)
        for bad in (raw.replace(b'"returncode":0',b'"returncode":NaN'),
                raw.replace(b'"returncode":0',b'"returncode":0,"returncode":0'),b'\xff',b'['*10000):
            with self.assertRaises(ValueError):quality.loads(bad,self.formats,BINARY_DIR)

    def test_q16_armed_transport_and_text_errors_are_not_quality_gaps(self):
        raw='TOPIC: vehicle_control_mode 2 instances\nInstance 0:\n'+mode_text(True)+'Instance 2:\n'
        result=self.parse(raw,7)
        with self.assertRaises(ValueError):quality.observation_gate(snapshot.plan(RUN_ID)[6],result)
        for code,stderr in ((1,''),(0,' '),(True,'')):
            with self.assertRaises(ValueError):self.parse(status_text(),stderr=stderr,code=code)
        for suffix in ('\r','\t','\x1b[0m','error\n','\ud800'):
            with self.assertRaises(ValueError):self.parse(status_text()+suffix)

    def test_q17_query_owner_flags_and_context_reject(self):
        for key,value in [('last_hil_us',True),('last_hil_us',500000),('fdm_time_s',True),
                ('control_gate_accepted',True),('binding_status','matched'),('extra','lidar')]:
            row=event();row[key]=value
            with self.assertRaises(ValueError):quality.dumps(row,self.formats,BINARY_DIR)
        row=event();row['query']['name']='SYS_CTRL_ALLOC set 1'
        with self.assertRaises(ValueError):quality.dumps(row,self.formats,BINARY_DIR)
        row=event();row['owner_after']['start_ticks']+=1
        with self.assertRaises(ValueError):quality.dumps(row,self.formats,BINARY_DIR)

    def test_q18_source_drift_and_limits(self):
        base=baseline();actual={name:(ROOT/'.runtime/src/px4-v1.13.3'/name).read_text() for name in quality.SEMANTIC_PATHS}
        quality.verify_sources(actual,base['native_messages'],base)
        bad=dict(actual);name=quality.SEMANTIC_PATHS[0];bad[name]=bad[name].replace('vel = NAN;','vel = 0;')
        with self.assertRaises(ValueError):quality.verify_sources(bad,base['native_messages'],base)
        with self.assertRaises(ValueError):quality.verify_sources(actual,{},base)
        with self.assertRaises(ValueError):self.parse('\n'*32769)
        with self.assertRaises(ValueError):quality.loads(b' '*262145,self.formats,BINARY_DIR)
        row=event();row['wall_end_ns']=row['wall_start_ns']+200000001
        with self.assertRaises(ValueError):quality.dumps(row,self.formats,BINARY_DIR)
        row=event();row['extra']=[[[[[[[[[None]]]]]]]]]
        with self.assertRaises(ValueError):quality.dumps(row,self.formats,BINARY_DIR)

    def test_q19_collection_body_and_payload_completeness_are_separate(self):
        rows=[event(i) for i in range(1,22)]
        result=quality.validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)
        for k,v in self.literal['collection_with_missing'].items():self.assertEqual(result[k],v)
        for row in rows[:18]:
            row['stdout'],row['observation']=finite_input(row['query']['name'])
        rows[1]=self.quality_row()
        result=quality.validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)
        self.assertTrue(result['diagnostic_collection_complete'])
        self.assertTrue(result['body_complete'])
        self.assertFalse(result['payload_complete'])
        self.assertEqual(len(result['isolated_fields']),2)
        self.assertFalse(result['control_gate_accepted'])

    def test_q20_full_order_and_parameters_required(self):
        rows=[event(i) for i in range(1,22)]
        for bad in (rows[:-1],rows+[rows[-1]],rows[::-1]):
            with self.assertRaises(ValueError):quality.validate_stream(bad,RUN_ID,self.formats,BINARY_DIR)
        row=event(20);row['stdout']=row['stdout'].replace(' : 0',' : 1')
        with self.assertRaises(ValueError):quality.dumps(row,self.formats,BINARY_DIR)
        for row in rows[4:]:row['wall_start_ns']+=400000000;row['wall_end_ns']+=400000000
        with self.assertRaises(ValueError):quality.validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)

    def test_independent_sixteen_mask_combinations(self):
        for gps,flow,evpos,evvel,allow_vel,allow_pos in self.literal['mask_examples']:
            mask=(gps<<2)|(flow<<3)|(evpos<<12)|(evvel<<24)
            for field,allowed in [('vel',allow_vel),('pos',allow_pos)]:
                args=dict(mask=mask,vel='nan' if field=='vel' else '0.0000',pos='nan' if field=='pos' else '0.0000')
                if allowed:self.assertEqual(self.parse(status_text(**args))['state'],'payload_quality_unavailable')
                else:
                    with self.assertRaises(ValueError):self.parse(status_text(**args))

    def recorder(self,directory):
        run=Path(directory)
        (run/'native-msg-before.json').write_text(json.dumps(baseline()['native_messages']))
        return UorbQualityDiagnostics(ROOT,run,RUN_ID,SimpleNamespace(pid=12345,poll=lambda:None),SimpleNamespace(),10**18,10**18)

    def test_expired_deadline_before_spawn_and_after_write(self):
        source=dict(step_index=125,hil_sensor_time_us=496000,fdm=dict(sim_time_after_s=.5))
        with tempfile.TemporaryDirectory() as directory:
            recorder=self.recorder(directory)
            with patch('sim_flight_uorb_quality.time.monotonic_ns',return_value=10**18),patch('sim_flight_uorb_quality.bounded_client') as client:
                with self.assertRaises(ValueError):recorder.capture(source)
                client.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            recorder=self.recorder(directory);clock=[100]
            def after_write(*_):clock[0]=10**18
            with patch('sim_flight_uorb_quality.time.monotonic_ns',side_effect=lambda:clock[0]), \
                    patch('sim_flight_uorb_quality.inspect_owner',return_value=owner()), \
                    patch('sim_flight_uorb_quality.bounded_client',return_value=dict(returncode=0,stdout='never published\n',stderr='')) as client, \
                    patch('sim_flight_uorb_quality.observation_gate',side_effect=after_write):
                with self.assertRaises(ValueError):recorder.capture(source)
                self.assertEqual(client.call_count,1)
                self.assertEqual(len(recorder.rows),1)
                self.assertTrue((recorder.directory/'quality-diagnostics.jsonl').exists())
            with self.assertRaises(ValueError):recorder._budget(snapshot.FILE_BYTES+1)

    def test_cli_modes_are_explicit_and_mutually_exclusive(self):
        for flags in (['--uorb-probe'],['--uorb-diagnostics'],['--build-only'],['--case','disconnect']):
            result=subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws/sim_flight_diagnostic_run.py'),
                '--uorb-quality-diagnostics']+flags,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
            self.assertEqual(result.returncode,2)


if __name__=='__main__':unittest.main()
