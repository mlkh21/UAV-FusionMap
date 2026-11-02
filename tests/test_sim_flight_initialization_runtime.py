import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase,mock

from sim_flight_initialization_fixture import ROOT,header,native,step
from sim_flight_initialization_queries import InitializationQueries
from ufm_simulation.flight_initialization_contract import check_budget


class PreparationRuntimeTests(TestCase):
    def recorder(self,tmp):
        run=Path(tmp)/'initialization-offline-01';run.mkdir()
        (run/'sim_flight_initialization_native.json').write_text(json.dumps(native()))
        (run/'native-msg-before.json').write_text(json.dumps(native()['native_messages']))
        (run/'quality-source-before.json').write_text('{}')
        return InitializationQueries(ROOT,run,mock.Mock(),mock.Mock(),mock.Mock())

    def test_guard_before_client_never_spawns_when_expired(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp);recorder.guard.side_effect=TimeoutError('deadline')
            with mock.patch('sim_flight_initialization_queries.bounded_client') as client:
                with self.assertRaises(TimeoutError):recorder.capture(step(125),'parameter')
                client.assert_not_called()

    def test_query_budget_includes_metadata_and_rejects_before_write(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            with self.assertRaises(ValueError):recorder.save('too-big.json',b' '*262145)
            with self.assertRaises(ValueError):recorder.budget(16777216)
            self.assertEqual(list(recorder.directory.iterdir()),[])

    def test_guard_after_raw_write_stops_before_parsing(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            recorder.guard.side_effect=[None,None,TimeoutError('late save')]
            with mock.patch('sim_flight_initialization_queries.inspect_owner',return_value={}),mock.patch(
                    'sim_flight_initialization_queries.bounded_client',return_value=dict(argv=[],returncode=0,stdout='',stderr='')):
                with self.assertRaises(TimeoutError):recorder.capture(step(125),'parameter')
            self.assertTrue((recorder.directory/'01-raw.json').exists())
            self.assertFalse((recorder.directory/'observations.jsonl').exists())

    def test_raw_client_error_survives_and_no_retry(self):
        with TemporaryDirectory() as tmp:
            recorder=self.recorder(tmp)
            with mock.patch('sim_flight_initialization_queries.inspect_owner',return_value={}),mock.patch(
                    'sim_flight_initialization_queries.bounded_client',return_value=dict(error='timeout')) as client:
                with self.assertRaisesRegex(ValueError,'timeout'):recorder.capture(step(125),'parameter')
                self.assertEqual(client.call_count,1)
            self.assertTrue((recorder.directory/'01-raw.json').exists())

    def test_source_copies_have_no_initialization_bypass(self):
        from importlib.util import module_from_spec,spec_from_file_location
        spec=spec_from_file_location('test_exact_copy',ROOT/'simulation/flight_bridge/adapt.py')
        module=module_from_spec(spec);spec.loader.exec_module(module)
        source=ROOT/'.runtime/src/px4-v1.13.3/Tools/jsbsim_bridge/src/jsbsim_bridge.cpp'
        adapted=module.adapt(source.name,source.read_text())
        self.assertEqual(adapted.count('_fdmexec->Run();'),1)
        self.assertEqual(adapted.count('flight::allow_run()'),1)
        self.assertNotIn('SetWOW',adapted)
        self.assertNotIn('initialiseFilter',adapted)
        with self.assertRaises(ValueError):module.adapt(source.name,adapted)

    def test_fault_source_time_preserves_original_one_ns_bound(self):
        from ufm_simulation.flight_initialization_contract import _time
        _time(.5000000000000003,125)
        with self.assertRaises(ValueError):_time(.500000002,125)

    def test_actual_selector_nan_remains_strictly_rejected(self):
        from ufm_simulation.flight_initialization_contract import plan
        from ufm_simulation.flight_initialization_observation import layouts_from_texts,parse_native
        evidence=json.loads((ROOT/'tests/fixtures/sim_flight_initialization_selector_rejection.json').read_text())
        formats=layouts_from_texts(native()['native_messages'],native()['native_messages'])
        query=plan(evidence['evidence_run'])[evidence['query_index']-1]
        self.assertEqual(query['checkpoint'],500)
        raw=evidence['raw']
        with self.assertRaisesRegex(ValueError,evidence['expected_error']):
            parse_native(query,raw['stdout'],raw['stderr'],raw['returncode'],formats)
