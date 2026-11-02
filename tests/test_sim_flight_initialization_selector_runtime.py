import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,mock

from sim_flight_initialization_selector_fixture import (ROOT,BINARY_DIR,baseline,event,events,header,
    physical_header,profile,queries,steps,terminal,write_dataset)
from sim_flight_initialization_selector_queries import SelectorQueries
from ufm_simulation import flight_initialization_selector as contract
from ufm_simulation import flight_initialization_contract as physical


class SelectorRuntimeTests(TestCase):
    def recorder(self, tmp):
        run=Path(tmp)/'selector-offline-01';run.mkdir()
        for name,value in [('sim_flight_initialization_selector_native.json',baseline()),
                ('native-msg-before.json',baseline()['native_messages']),('selector-source-before.json',{}),
                ('quality-source-before.json',{}),('sim_flight_initialization_selector_fixture.json',profile()),
                ('header.json',physical_header()),('selector-header.json',header())]:
            (run/name).write_text(json.dumps(value))
        return SelectorQueries(ROOT,run,mock.Mock(),mock.Mock(),mock.Mock())

    def owner(self, recorder):
        value=event(queries()[0])['owner_before']
        value.update(executable=str(recorder.binary_dir/'px4'),rootfs=str(recorder.run/'rootfs'))
        return value

    def source(self):
        return dict(step_index=125,hil_sensor_time_us=496000,fdm=dict(sim_time_after_s=.5))

    def test_expired_before_client_never_spawns_and_locks(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp);recorder.guard.side_effect=TimeoutError('deadline')
            with mock.patch('sim_flight_initialization_selector_queries.bounded_client') as client:
                with self.assertRaises(TimeoutError):recorder.capture(self.source(),'parameter')
                self.assertTrue(recorder.failed);client.assert_not_called()

    def test_raw_client_failure_survives_without_retry(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            with mock.patch('sim_flight_initialization_selector_queries.inspect_owner',return_value=self.owner(recorder)),mock.patch(
                    'sim_flight_initialization_selector_queries.bounded_client',return_value=dict(error='timeout')) as client:
                with self.assertRaisesRegex(ValueError,'timeout'):recorder.capture(self.source(),'parameter')
                with self.assertRaisesRegex(ValueError,'recorder stopped'):recorder.capture(self.source(),'parameter')
                self.assertEqual(client.call_count,1)
            self.assertTrue((recorder.directory/'01-raw.json').exists())
            self.assertFalse((recorder.directory/'observations.jsonl').exists())

    def test_deadline_after_raw_write_stops_before_projection(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            recorder.guard.side_effect=[None,None,TimeoutError('late save')]
            raw=dict(argv=[],stdout='',stderr='',returncode=0)
            with mock.patch('sim_flight_initialization_selector_queries.inspect_owner',return_value=self.owner(recorder)),mock.patch(
                    'sim_flight_initialization_selector_queries.bounded_client',return_value=raw):
                with self.assertRaises(TimeoutError):recorder.capture(self.source(),'parameter')
            self.assertTrue((recorder.directory/'01-raw.json').exists())
            self.assertEqual(recorder.rows,[])

    def test_malformed_native_saved_then_locks(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            with mock.patch('sim_flight_initialization_selector_queries.inspect_owner',return_value=self.owner(recorder)),mock.patch(
                    'sim_flight_initialization_selector_queries.bounded_client',return_value=dict(
                    argv=[],stdout='garbled\n',stderr='',returncode=0)) as client:
                with self.assertRaises(ValueError):recorder.capture(self.source(),'parameter')
                self.assertEqual(client.call_count,1)
            self.assertTrue(recorder.failed);self.assertEqual(recorder.rows,[])
            self.assertTrue((recorder.directory/'01-raw.json').exists())

    def test_raw_persistence_failure_locks_without_event(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            with mock.patch('sim_flight_initialization_selector_queries.inspect_owner',return_value=self.owner(recorder)),mock.patch(
                    'sim_flight_initialization_selector_queries.bounded_client',return_value=dict(error='timeout')),mock.patch.object(
                    recorder,'save',side_effect=OSError('disk write failed')):
                with self.assertRaises(OSError):recorder.capture(self.source(),'parameter')
            self.assertTrue(recorder.failed);self.assertEqual(recorder.rows,[])

    def test_event_persistence_failure_preserves_raw_and_stops(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            raw=event(queries()[0]);raw={k:raw[k] for k in ('argv','stdout','stderr','returncode')}
            (recorder.directory/'observations.jsonl').mkdir()
            with mock.patch('sim_flight_initialization_selector_queries.inspect_owner',return_value=self.owner(recorder)),mock.patch(
                    'sim_flight_initialization_selector_queries.bounded_client',return_value=raw):
                with self.assertRaises(OSError):recorder.capture(self.source(),'parameter')
            self.assertTrue((recorder.directory/'01-raw.json').exists())
            self.assertTrue(recorder.failed);self.assertEqual(recorder.rows,[])

    def test_metadata_and_record_budgets_before_write(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            with self.assertRaises(ValueError):recorder.save('large.json',b' '*262145)
            with self.assertRaises(ValueError):recorder.budget(16777216)
            self.assertEqual(list(recorder.directory.iterdir()),[])

    def test_seven_parameters_saved_once_in_new_envelopes(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            def raw(argv,*args):
                row=event(queries()[len(recorder.rows)])
                return dict(argv=argv,stdout=row['stdout'],stderr='',returncode=0)
            with mock.patch('sim_flight_initialization_selector_queries.inspect_owner',return_value=self.owner(recorder)),mock.patch(
                    'sim_flight_initialization_selector_queries.bounded_client',side_effect=raw):
                recorder.capture(self.source(),'parameter')
            self.assertEqual(len(recorder.rows),7)
            self.assertTrue((recorder.directory/'group-125-parameter.json').exists())
            self.assertEqual(len((recorder.directory/'observations.jsonl').read_bytes().splitlines()),7)
            with self.assertRaisesRegex(ValueError,'query order'):recorder.capture(self.source(),'parameter')

    def test_final_capture_can_follow_physical_terminal_without_retiming(self):
        messages=baseline()['native_messages'];layouts=contract.layouts_from_texts(messages,messages)
        term=terminal();term['wall_ns']=2500000100
        result=contract.evaluate(header(),physical_header(),steps(True),term,events(),layouts,BINARY_DIR)
        self.assertTrue(result['passed']);self.assertFalse(result['control_gate_accepted'])
        self.assertEqual(term['wall_ns'],2500000100)
        # The same exception does not admit captures after an early or failed terminal.
        term['reason']='invalid_input'
        with self.assertRaisesRegex(ValueError,'query_after_physical_boundary'):
            contract.evaluate(header(),physical_header(),steps(True),term,events(),layouts,BINARY_DIR)

    def test_only_fixed_px4_runtime_etc_link_is_ignored(self):
        messages=baseline()['native_messages'];layouts=contract.layouts_from_texts(messages,messages)
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'dataset';write_dataset(path)
            (path/'rootfs').mkdir()
            (path/'rootfs/etc').symlink_to(ROOT/'.runtime/build/px4-v1.13.3/etc',target_is_directory=True)
            self.assertTrue(contract.load_recording(path,layouts,BINARY_DIR)['passed'])
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'dataset';write_dataset(path)
            (path/'rootfs').mkdir()
            (path/'rootfs/etc').symlink_to('/tmp',target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):contract.load_recording(path,layouts,BINARY_DIR)

    def test_native_double_truncation_is_not_a_permitted_grid_timestamp(self):
        from sim_flight_initialization_fixture import step
        source_seconds=4.028
        physical._time(source_seconds,1007)
        self.assertEqual(int(source_seconds*1e6),4027999)
        self.assertEqual(1007*4000,4028000)
        row=step(1008)
        row['hil_sensor_time_us']=4027999
        row['fdm']['hil_sensor']['time_usec']=4027999
        with self.assertRaisesRegex(ValueError,'initialization_hil_time'):physical.validate_step(row)
