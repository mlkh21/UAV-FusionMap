import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sim_flight_diagnostic_fixture import BINARY_DIR, ROOT, RUN_ID, attitude, event, expected, layouts, mode_text
from sim_flight_probe_fixture import owner, receipt
from sim_flight_uorb_diagnostics import UorbDiagnostics
from ufm_simulation import flight_probe_contract as old
from ufm_simulation import flight_probe_diagnostic as diagnostic


class FlightDiagnosticObservationTests(unittest.TestCase):
    def setUp(self):
        self.literal = expected()
        self.formats = layouts()

    def parse(self, index, raw, stderr='', code=0):
        return diagnostic.parse_native(old.plan(RUN_ID)[index-1], raw, stderr, code, self.formats)

    def test_c01_archived_empty_status_and_old_strict_rejection(self):
        self.assertEqual(self.parse(2, self.literal['empty_status_text']), self.literal['empty_status_result'])
        with self.assertRaisesRegex(ValueError, 'probe_native_incomplete'):
            old.parse_output(old.plan(RUN_ID)[1], self.literal['empty_status_text'], '', 0, self.formats)

    def test_c02_full_single_zero_negative_and_unknown_label(self):
        observation = dict(state='payload', reason='', instances=[attitude()], parameter=None)
        self.assertEqual(self.parse(6, self.literal['attitude_text']), observation)
        row = event(6)
        row.update(stdout=self.literal['attitude_text'], observation=observation, last_hil_us=496000)
        self.assertEqual(diagnostic.loads(diagnostic.dumps(row, self.formats, BINARY_DIR), self.formats, BINARY_DIR), row)

    def test_c03_single_empty_is_not_instance_zero(self):
        self.assertEqual(self.parse(6, self.literal['single_empty_text']), self.literal['single_empty_result'])

    def test_c04_literal_missing_is_not_a_zero_state(self):
        self.assertEqual(self.parse(6, self.literal['missing_text']), self.literal['missing_result'])
        self.assertIsNone(self.parse(6, self.literal['single_empty_text'])['instances'][0]['fields'])

    def multi(self, first=True, second=True):
        body = self.literal['attitude_text'].split('TOPIC: vehicle_attitude\n')[1]
        return ('TOPIC: vehicle_attitude 2 instances\nInstance 0:\n'+(body if first else '')+
            'Instance 2:\n'+(body if second else ''))

    def test_c05_full_noncontiguous_instance_labels(self):
        result = self.parse(6, self.multi())
        self.assertEqual(result, dict(state='payload', reason='', instances=[attitude(0), attitude(2)], parameter=None))

    def test_c06_mixed_instances_keep_complete_and_null_separately(self):
        for first in (False, True):
            result = self.parse(6, self.multi(first, not first))
            self.assertEqual(result['state'], 'payload_unavailable')
            self.assertEqual(result['instances'][0], attitude(0) if first else dict(instance=0,state='payload_unavailable',fields=None))
            self.assertEqual(result['instances'][1], dict(instance=2,state='payload_unavailable',fields=None) if first else attitude(2))

    def test_c07_bad_count_order_duplicate_and_range_reject(self):
        raw = self.multi()
        for bad in (raw.replace('2 instances','3 instances'), raw.replace('Instance 2:','Instance 0:'),
                raw.replace('Instance 0:','Instance 3:'), raw.replace('Instance 2:','Instance 9:')):
            with self.assertRaises(ValueError):self.parse(6,bad)

    def test_c08_body_without_complete_fields_is_fatal_even_in_mixed(self):
        for raw in ('TOPIC: vehicle_attitude\n vehicle_attitude\n',
                self.multi(False,True).replace('Instance 0:\n','Instance 0:\n vehicle_attitude\n'),
                self.literal['attitude_text'].replace('    quat_reset_counter: 0\n','')):
            with self.assertRaises(ValueError):self.parse(6,raw)

    def test_c09_bad_fields_types_nonfinite_and_array_reject(self):
        raw = self.literal['attitude_text']
        for bad in (raw+'    timestamp: 0\n', raw+'    observed_mask: 0\n',raw+'    target: 1\n',
                raw.replace('1.0000','nan'),raw.replace('1.0000','inf'),raw.replace('496000','True'),
                raw.replace('quat_reset_counter: 0','quat_reset_counter: 256'),
                raw.replace('0.0000, 0.0000, 0.0000]','0.0000]')):
            with self.assertRaises(ValueError):self.parse(6,bad)

    def test_c10_exact_text_and_control_bytes(self):
        for raw in ('',' ','never published\nTOPIC: vehicle_attitude\n',
                'TOPIC: foreign\n',self.literal['attitude_text']+'error\n',
                'TOPIC: vehicle_attitude\n \n',self.literal['attitude_text']+'\x1b[0m',
                'never published\r\n','never published\n\t','never published\0'):
            with self.assertRaises(ValueError):self.parse(6,raw)

    def test_c11_client_status_stderr_and_encoding_reject(self):
        for code, stderr in ((1,''),(0,' '),(0,'\n'),(True,'')):
            with self.assertRaises(ValueError):self.parse(6,'never published\n',stderr,code)
        with self.assertRaises(ValueError):self.parse(6,'\ud800')
        # Actual client timeout/flood/UTF-8 checks also run in the unchanged probe tests.

    def test_c12_armed_payload_stops_even_with_empty_other_instance(self):
        raw = 'TOPIC: vehicle_control_mode 2 instances\nInstance 0:\n'+mode_text(True)+'Instance 2:\n'
        obs = self.parse(7,raw)
        self.assertEqual(obs['state'],'payload_unavailable')
        with self.assertRaisesRegex(ValueError,'diagnostic_observation_armed'):
            diagnostic.observation_gate(old.plan(RUN_ID)[6],obs)

    def test_c13_parameter_values_and_complete_shape(self):
        self.assertEqual(self.parse(20,self.literal['parameter_text']),self.literal['parameter_result'])
        for index in (19,20,21):
            row=event(index)
            diagnostic.validate_event(row,self.formats,BINARY_DIR)
            for bad in (row['stdout'].replace(' : '+str(self.literal['parameters'][row['query']['name']]),' : -1'),
                    '', 'never published\n',row['stdout']+row['stdout']):
                with self.assertRaises(ValueError):self.parse(index,bad)

    def test_c14_schema_projection_duplicate_key_and_strict_types(self):
        row=event()
        with self.assertRaises(ValueError):old.dumps(row,self.formats,BINARY_DIR)
        with self.assertRaises(ValueError):diagnostic.dumps(receipt(),self.formats,BINARY_DIR)
        raw=diagnostic.dumps(row,self.formats,BINARY_DIR)
        for bad in (raw.replace(b'"returncode":0',b'"returncode":0,"returncode":0'),
                raw.replace(b'"returncode":0',b'"returncode":NaN'),b'\xff',b'['*10000):
            with self.assertRaises(ValueError):diagnostic.loads(bad,self.formats,BINARY_DIR)
        variants=[('control_gate_accepted',True),('schema_version','other'),('binding_status','matched'),
            ('last_hil_us',True),('wall_start_ns',True),('extra','lidar')]
        for key,value in variants:
            bad=event();bad[key]=value
            with self.assertRaises(ValueError):diagnostic.dumps(bad,self.formats,BINARY_DIR)
        bad=event(6);bad.update(stdout=self.literal['single_empty_text'],observation=self.literal['single_empty_result'])
        bad['observation']['instances'][0]['fields']={}
        with self.assertRaises(ValueError):diagnostic.dumps(bad,self.formats,BINARY_DIR)
        bad=event(6);bad.update(stdout=self.literal['attitude_text'],observation=dict(state='payload',reason='',instances=[attitude()],parameter=None))
        bad['observation']['instances'][0]['fields']['timestamp_sample']=False
        with self.assertRaises(ValueError):diagnostic.dumps(bad,self.formats,BINARY_DIR)

    def test_c15_fixed_queries_and_owner_identity(self):
        for field,value in [('name','SYS_CTRL_ALLOC set 1'),('kind','set'),('clock_id','foreign')]:
            row=event();row['query'][field]=value
            with self.assertRaises(ValueError):diagnostic.dumps(row,self.formats,BINARY_DIR)
        row=event();row['owner_after']['start_ticks']+=1
        with self.assertRaises(ValueError):diagnostic.dumps(row,self.formats,BINARY_DIR)
        row=event();row['argv'][-1]='2'
        with self.assertRaises(ValueError):diagnostic.dumps(row,self.formats,BINARY_DIR)

    def test_c16_structure_bytes_and_client_group_limits(self):
        self.parse(6,'never published\n'+'\n'*(32768-len('never published\n')))
        with self.assertRaises(ValueError):self.parse(6,'\n'*32769)
        with self.assertRaises(ValueError):diagnostic.loads(b' '*262145,self.formats,BINARY_DIR)
        row=event();row['extra']=[[[[[[[[[None]]]]]]]]]
        with self.assertRaises(ValueError):diagnostic.dumps(row,self.formats,BINARY_DIR)
        rows=[event(i) for i in range(1,22)]
        rows[0]['wall_end_ns']=rows[0]['wall_start_ns']+200000001
        with self.assertRaises(ValueError):diagnostic.validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)
        rows=[event(i) for i in range(1,22)]
        for row in rows[4:]:row['wall_start_ns']+=400000000;row['wall_end_ns']+=400000000
        with self.assertRaises(ValueError):diagnostic.validate_stream(rows,RUN_ID,self.formats,BINARY_DIR)

    def test_c17_collection_complete_does_not_mean_payload_ready(self):
        summary=diagnostic.validate_stream([event(i) for i in range(1,22)],RUN_ID,self.formats,BINARY_DIR)
        for key,value in self.literal['collection_with_18_missing'].items():self.assertEqual(summary[key],value)
        self.assertFalse(summary['legacy_sw02b_runtime_accepted'])

    def test_c18_count_order_and_host_context_reject(self):
        rows=[event(i) for i in range(1,22)]
        for bad in (rows[:-1],rows+[rows[-1]],rows[::-1]):
            with self.assertRaises(ValueError):diagnostic.validate_stream(bad,RUN_ID,self.formats,BINARY_DIR)
        for key,value in [('last_hil_us',500000),('fdm_time_s',.504),('fdm_time_s',True)]:
            bad=event();bad[key]=value
            with self.assertRaises(ValueError):diagnostic.dumps(bad,self.formats,BINARY_DIR)

    def recorder(self, directory):
        run=Path(directory)
        texts={name:(ROOT/'.runtime/src/px4-v1.13.3/msg'/(name+'.msg')).read_text() for name in old.MESSAGE_FILES}
        (run/'native-msg-before.json').write_text(json.dumps(texts))
        return UorbDiagnostics(ROOT,run,RUN_ID,SimpleNamespace(pid=12345,poll=lambda:None),
            SimpleNamespace(),10**18,10**18)

    def test_deadline_before_spawn_and_after_persistence_stops(self):
        source=dict(step_index=125,hil_sensor_time_us=496000,fdm=dict(sim_time_after_s=.5))
        with tempfile.TemporaryDirectory() as directory:
            recorder=self.recorder(directory)
            with patch('sim_flight_uorb_diagnostics.time.monotonic_ns',return_value=10**18), \
                    patch('sim_flight_uorb_diagnostics.bounded_client') as client:
                with self.assertRaises(ValueError):recorder.capture(source)
                client.assert_not_called()
        with tempfile.TemporaryDirectory() as directory:
            recorder=self.recorder(directory);clock=[100]
            def after_write(*_):clock[0]=10**18
            with patch('sim_flight_uorb_diagnostics.time.monotonic_ns',side_effect=lambda:clock[0]), \
                    patch('sim_flight_uorb_diagnostics.inspect_owner',return_value=owner()), \
                    patch('sim_flight_uorb_diagnostics.bounded_client',return_value=dict(returncode=0,stdout='never published\n',stderr='')) as client, \
                    patch('sim_flight_uorb_diagnostics.observation_gate',side_effect=after_write):
                with self.assertRaises(ValueError):recorder.capture(source)
                self.assertEqual(client.call_count,1)
                self.assertEqual(len(recorder.rows),1)
                self.assertTrue((recorder.directory/'diagnostics.jsonl').exists())

    def test_recorder_file_budget_and_cli_mutual_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder=self.recorder(directory)
            with self.assertRaises(ValueError):recorder._budget(old.FILE_BYTES+1)
        for flags in (['--uorb-diagnostics','--uorb-probe'],['--uorb-diagnostics','--case','disconnect'],
                ['--uorb-diagnostics','--build-only']):
            result=subprocess.run([sys.executable,'-B',str(ROOT/'ros_ws/sim_flight_diagnostic_run.py')]+flags,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5)
            self.assertEqual(result.returncode,2)


if __name__=='__main__':unittest.main()
