"""M4 explicit selection and public receipt replay; no fallback or implicit registration."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml
from m4_fixture import bound_spec,load_spec,observation,step
from ufm_mapping.factory import create_map
from ufm_mapping.replay import replay_observations
from runtime_config import load_m4_config


ROOT=Path(__file__).resolve().parents[1]


class M4SelectionTest(unittest.TestCase):
    def setUp(self):
        self.spec=bound_spec(load_spec(),'selected')
        self.rows=[observation(self.spec,step(0,10_000_000,[],[],0,None)),
                   observation(self.spec,step(1,20_000_000,[],[],0,None,body=40.,points=((48.25,.25,.25),)))]

    def test_explicit_selection_and_missing_mode_config_clock_or_rolling_fail_closed(self):
        candidate=create_map('m4_fixture',{'rolling_enabled':True},run_id='selected',
                             clock_id='sim:selected',fixture_spec=self.spec)
        candidate.update(self.rows[0])
        self.assertEqual(candidate.snapshot()['header']['frame_id'],'map')
        for kwargs in (dict(backend='m4_fixture'),dict(fixture_spec=self.spec),
            dict(backend='m4_fixture',fixture_spec=self.spec),
            dict(backend='m4_fixture',fixture_spec=self.spec,settings={'rolling_enabled':False}),
            dict(backend='m4_fixture',fixture_spec=self.spec,settings={'rolling_enabled':True},run_id='foreign',clock_id='foreign'),
            dict(backend='m4_fixture',fixture_spec=self.spec,settings={'rolling_enabled':True,'free_threshold':.3})):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):create_map(**kwargs)

    def test_missing_bad_registration_and_loader_paths_do_not_fallback(self):
        for path in ('','/unused/m4-missing.yaml'):
            with self.assertRaises((ValueError,OSError)):load_m4_config(path)
        spec=copy.deepcopy(self.spec)
        spec['registration']['source_frame']='map'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'bad.yaml'
            path.write_text(yaml.safe_dump(spec))
            with self.assertRaises(ValueError):load_m4_config(path)

    def test_replay_preserves_sealed_history_outcomes_and_quality(self):
        rows=[self.rows[0],copy.deepcopy(self.rows[0]),self.rows[1]]
        bad=copy.deepcopy(self.rows[1])
        bad['voxels'][0]['uncertainty']['unit']='m2'
        rows.append(bad)
        result=replay_observations(rows,'selected',{'rolling_enabled':True},backend='m4_fixture',
            clock_id='sim:selected',fixture_spec=self.spec)
        self.assertEqual([s['outcome'] for s in result['steps']],['fused','not_fused','fused','rejected'])
        self.assertEqual(len(result['final_snapshot']['cells']),2)
        self.assertEqual(result['final_snapshot']['cells'][0]['last_observed_timestamp'],10_000_000)

    def test_cli_replay_rejects_mixed_implicit_or_altered_registration_and_quality(self):
        result=replay_observations(self.rows,'selected',{'rolling_enabled':True},backend='m4_fixture',
            clock_id='sim:selected',fixture_spec=self.spec)
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'config.yaml'
            config.write_text(yaml.safe_dump(self.spec))
            receipt=Path(directory)/'receipt.json'
            base=[sys.executable,'-B',str(ROOT/'ros_ws/local_map_replay.py'),'--input',str(receipt),
                '--run-id','selected','--clock-id','sim:selected','--m4-fixture-config',str(config),'--rolling']
            for changes,mode,extra,expected in ((False,'m4_fixture',[],0),(True,'m4_fixture',[],1),
                (False,'latest',[],1),(False,'m4_fixture',['--m3-fixture-config',str(config)],1),
                (False,'m4_fixture',['--free-threshold','.3'],1)):
                saved=copy.deepcopy(result['snapshots'])
                if changes:saved[-1]['cells'][0]['uncertainty']['source']='altered'
                receipt.write_text(json.dumps(dict(observations=self.rows,snapshots=saved)))
                process=subprocess.run(base+['--map-backend',mode]+extra,text=True,capture_output=True,timeout=10)
                self.assertEqual(process.returncode,expected,process.stdout+process.stderr)
            spec=copy.deepcopy(self.spec)
            spec['registration']['T_map_odom'][3]=32.25
            config.write_text(yaml.safe_dump(spec))
            process=subprocess.run(base+['--map-backend','m4_fixture'],text=True,capture_output=True,timeout=10)
            self.assertEqual(process.returncode,1)

    def test_default_latest_does_not_import_scene_or_m4_contract(self):
        subprocess.run([sys.executable,'-B','-c',
            "from ufm_mapping.factory import create_map; import sys; create_map(); "
            "assert not any(k in sys.modules for k in ('ufm_mapping.scene_map','ufm_mapping.m4_contract'))"],
            check=True,timeout=10)
