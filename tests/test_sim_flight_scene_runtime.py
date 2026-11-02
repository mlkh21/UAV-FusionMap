"""Independent ground registration, runtime state and time-production boundaries."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from sim_flight_initialization_fixture import header,step
from sim_flight_v2_fixture import frame,response
from sim_flight_initialization_time_build import module_from
from sim_flight_scene_queries import plan,observation_event
from sim_flight_scene_run import read_record
from ufm_flight_contract.profile import load_profile
from ufm_simulation.flight_scene import (CHECKPOINTS,READY_CHECKPOINTS,FlightRegistration,
    FlightTransactions,PhysicalStream,PROFILE_ID,validate_source)
from ufm_simulation import flight_initialization_contract as old
from ufm_simulation import flight_initialization_selector as selector

ROOT=Path(__file__).resolve().parents[1]


def source(index=0):
    return dict(step_index=index,sim_time_s=index*.004,ecef_ft=[20000000.,0.,0.],
        R_ecef_frd=[1.,0.,0.,0.,1.,0.,0.,0.,1.],uvw_ftps=[1.,2.,3.],pqr_radps=[4.,5.,6.])


def row(index,template=None):
    value=copy.deepcopy(template if template is not None else step())
    value.update(schema_version='sim_flight_scene_step.v1',profile_id=PROFILE_ID,
        step_index=index,source_step=index-1,hil_sensor_time_us=(index-1)*4000)
    value['fdm'].update(sim_time_before_s=(index-1)*.004,sim_time_after_s=index*.004)
    value['fdm']['hil_sensor']['time_usec']=(index-1)*4000
    value['kinematics_before']['sim_time_s']=(index-1)*.004
    value['kinematics_after']['sim_time_s']=index*.004
    value['wall'].update(hil_sent_ns=index*1000000,fdm_finished_ns=index*1000000+100)
    return value


class FlightSceneRuntimeTests(unittest.TestCase):
    def test_partial_host_writes_are_joined_without_losing_byte_limit(self):
        import io
        stream=io.BytesIO(b'{"step":')
        def wait(predicate,until,reason):
            self.assertFalse(predicate())
            current=stream.tell();stream.seek(0,2);stream.write(b'7525}\n');stream.seek(current)
            self.assertTrue(predicate())
        self.assertEqual(read_record(stream,wait,0),dict(step=7525))
        def immediate(predicate,until,reason):predicate()
        with self.assertRaises(ValueError):read_record(io.BytesIO(b'x'*16385),immediate,0)

    def test_query_raw_argv_is_projected_once_and_original_text_is_preserved(self):
        query=plan('offline')[0]
        raw=dict(argv=['px4-param','show','SYS_AUTOSTART'],returncode=0,
            stdout='Symbols: x = used, + = saved, * = unsaved\n',stderr='')
        source=dict(hil_sensor_time_us=496000,fdm=dict(sim_time_after_s=.5))
        result=observation_event(query,raw,{}, {},source,100,200,dict(state='payload'))
        self.assertEqual(result['argv'],raw['argv'])
        self.assertEqual(result['stdout'],raw['stdout'])
        self.assertEqual(result['query'],query)
        self.assertEqual(result['last_hil_us'],496000)
        with self.assertRaises(ValueError):
            observation_event(query,dict(raw,target=[]),{}, {},source,100,200,{})

    def test_independent_runtime_plan_and_original_plan_limits(self):
        expected=json.loads((ROOT/'tests/fixtures/sim_flight_scene_runtime_expectations.json').read_text())
        self.assertEqual(list(CHECKPOINTS),expected['checkpoints'])
        self.assertEqual(list(READY_CHECKPOINTS),expected['ready_checkpoints'])
        queries=plan('offline')
        self.assertEqual(len(queries),150)
        self.assertEqual(queries[-1]['checkpoint'],7500)
        self.assertEqual(queries[-1]['query_index'],150)
        with self.assertRaises(ValueError):selector.validate_query(queries[0])
        self.assertEqual(len(selector.plan('offline')),98)
        self.assertEqual(old.profile_reference()['time']['max_step'],2500)

    def test_ground_registration_has_analytic_enu_and_flu_axes(self):
        profile=load_profile(ROOT/'configs/sim_flight_scene_fixture.json')
        registration=FlightRegistration(source(),0.,0.,profile)
        initial=registration.convert(source(),'offline')
        self.assertEqual(initial['state']['position'],[0.,0.,.5])
        self.assertEqual(initial['state']['linear_velocity'],[.3048,-.6096,-.9144000000000001])
        self.assertEqual(initial['angular_velocity_flu'],[4.,-5.,-6.])
        changed=source(7525);changed['ecef_ft']=[20000001.,2.,3.]
        value=registration.convert(changed,'offline')
        for actual,wanted in zip(value['state']['position'],[.6096,.9144,.8048]):
            self.assertAlmostEqual(actual,wanted)
        self.assertEqual(value['state']['header']['timestamp'],30100000000)
        self.assertEqual(registration.metadata['registration_id'],'jsbsim_cg_to_flight_enu_v1')

    def test_source_bounds_rotation_and_no_timestamp_repair(self):
        validate_source(source(10000))
        for change in (dict(step_index=10001),dict(sim_time_s=.0040000015),
                       dict(sim_time_s=float('nan')),dict(R_ecef_frd=[1.]*9),dict(step_index=True)):
            value=source(1);value.update(change)
            with self.assertRaises(ValueError):validate_source(value)

    def test_transaction_failure_late_reply_and_new_run_are_separate(self):
        tx=FlightTransactions('flight-v2');tx.begin(frame());tx.finish(response())
        self.assertEqual(tx.begin(frame()),response())
        tx.begin(frame(1));bad=response(1,False)
        with self.assertRaises(ValueError):tx.finish(bad)
        terminal=tx.terminal('ack_timeout')
        self.assertEqual(terminal['header']['timestamp'],0)
        self.assertEqual(terminal['header']['status'],'unavailable')
        with self.assertRaises(ValueError):tx.finish(response(1))
        with self.assertRaises(ValueError):tx.begin(frame(1))
        fresh=FlightTransactions('flight-v2');self.assertIsNone(fresh.begin(frame()))

    def test_full_10000_continuous_physical_steps_and_exact_bound(self):
        stream=PhysicalStream('initialization-offline-01',header())
        template=step()
        for index in range(1,10001):self.assertTrue(stream.add(row(index,template)))
        self.assertEqual(stream.count,10000)
        self.assertEqual(set(stream.checkpoints),{str(i) for i in CHECKPOINTS})
        self.assertTrue(all(c['input_settled'] for k,c in stream.checkpoints.items() if int(k)>=250))
        with self.assertRaises(ValueError):stream.add(row(10001,template))

    def test_readiness_needs_all_three_checkpoints_fresh_samples_and_real_output(self):
        stream=PhysicalStream('initialization-offline-01',header())
        stream.checkpoints={str(i):dict(input_settled=True,actuator_count=i) for i in READY_CHECKPOINTS}
        ready={str(i):dict(ready=True,attitude_sample=i,vehicle_sample=i) for i in READY_CHECKPOINTS}
        self.assertTrue(stream.preparation_ready(ready))
        for i in READY_CHECKPOINTS:
            changed=copy.deepcopy(ready);changed[str(i)]['ready']=False
            self.assertFalse(stream.preparation_ready(changed))
        changed=copy.deepcopy(ready);changed['7500']['attitude_sample']=7000
        self.assertFalse(stream.preparation_ready(changed))
        stream.checkpoints['7500']['actuator_count']=7001
        self.assertFalse(stream.preparation_ready(ready))

    def test_physical_discontinuity_identity_nonzero_and_old_envelope_rejected(self):
        for change in ('old','identity','skip','nonzero','not_finite'):
            value=row(1)
            if change=='old':value=step()
            elif change=='identity':value['run_id']='foreign';value['clock_id']='sim:foreign'
            elif change=='skip':value=row(2)
            elif change=='nonzero':value['properties']['after'][0]=.1
            else:value['kinematics_after']['agl_m']=float('nan')
            stream=PhysicalStream('initialization-offline-01',header())
            with self.assertRaises(ValueError):stream.add(value)

    def test_pure_native_payload_parser_keeps_real_long_checkpoint_data(self):
        from sim_flight_initialization_selector_fixture import baseline,layout,values,body
        layouts={n:layout(n) for n in set(selector.TOPICS)}
        text='TOPIC: sensors_status_imu\n'+body('sensors_status_imu',values('sensors_status_imu',7500))+'\n'
        parsed=selector.parse_native_payload('topic','sensors_status_imu',text,'',0,layouts)
        self.assertEqual(parsed['instances'][0]['fields']['timestamp'],29988000)
        with self.assertRaises(ValueError):selector.parse_native_payload('topic','unknown',text,'',0,layouts)

    def test_exact_source_adaptation_and_old_time_function_stay_separate(self):
        adapter=module_from(ROOT/'simulation/flight_scene/adapt.py','test_scene_copy_adapter')
        for name in ('host.cpp','diagnostics.cpp'):
            original=(ROOT/'simulation/flight_initialization'/name).read_text()
            result=adapter.adapt(name,original)
            self.assertIn('10000',result)
            with self.assertRaises(ValueError):adapter.adapt(name,result)
            with self.assertRaises(ValueError):adapter.adapt(name,original+original)
            self.assertEqual((ROOT/'simulation/flight_initialization'/name).read_text(),original)
        self.assertIn('source_step > 2500',(ROOT/'simulation/flight_initialization_time/time_grid.h').read_text())

    def test_real_cpp_source_time_boundaries_without_relaxing_1ns(self):
        literals=json.loads((ROOT/'tests/fixtures/sim_flight_scene_runtime_expectations.json').read_text())
        with tempfile.TemporaryDirectory(dir=ROOT/'.runtime/ros',prefix='flight-scene-time-') as directory:
            binary=Path(directory)/'time-probe'
            subprocess.run(['g++','-std=c++17',str(ROOT/'simulation/flight_scene/time_probe.cpp'),'-o',str(binary)],check=True)
            for seconds,index,wanted in literals['source_time_probes']:
                result=subprocess.run([str(binary),str(seconds),str(index)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0)
                self.assertEqual(int(result.stdout),wanted)
            for seconds,index in literals['source_time_reject']+[[float('nan'),1],[float('inf'),1]]:
                result=subprocess.run([str(binary),str(seconds),str(index)],capture_output=True,text=True)
                self.assertEqual(result.returncode,3)
                self.assertEqual(result.stdout,'')


if __name__=='__main__':unittest.main()
