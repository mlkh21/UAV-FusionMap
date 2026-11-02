"""M3 explicit assembly, refusal and public replay contracts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m3_fixture import CONFIG, load_spec
from m3_motion_fixture import motion_observation
from ufm_mapping.factory import create_map
from ufm_mapping.replay import replay_observations


class M3SelectionTest(unittest.TestCase):
    def test_latest_imports_no_synthetic_backend(self):
        subprocess.run([sys.executable, '-B', '-c',
            "from ufm_mapping.factory import create_map; import sys; create_map(); "
            "assert not any(k.startswith(('ufm_mapping.m2_', 'ufm_mapping.m3_')) or "
            "k.endswith('probability_map') for k in sys.modules)"], check=True, timeout=10)

    def test_explicit_fixed_and_rolling_preserve_interval(self):
        for rolling in (False, True):
            candidate = create_map('m3_fixture', dict(rolling_enabled=rolling),
                run_id='selected', clock_id='sim:selected', fixture_spec=load_spec())
            candidate.update(motion_observation(load_spec(), 'selected', 0))
            cell = candidate.snapshot()['cells'][0]
            self.assertAlmostEqual(cell['probability'], .75)
            for actual, expected in zip(cell['uncertainty']['value'], (.7, .8)):
                self.assertAlmostEqual(actual, expected)
            self.assertEqual(candidate.rolling_enabled, rolling)

    def test_missing_bad_or_implicit_configuration_cannot_fallback(self):
        bad = copy.deepcopy(load_spec())
        bad['fixture_only'] = False
        for kwargs in (dict(backend='m3_fixture'), dict(fixture_spec=load_spec()),
                dict(backend='m3_fixture', fixture_spec=load_spec()),
                dict(backend='m3_fixture', fixture_spec=bad, run_id='r', clock_id='sim:r'),
                dict(backend='m3_fixture', fixture_spec=load_spec(), settings={'rolling_enabled': 1}),
                dict(backend='m3_fixture', fixture_spec=load_spec(), settings={'free_threshold': .3})):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                create_map(**kwargs)

    def test_public_replay_preserves_refusals_and_quality(self):
        spec = load_spec()
        first = motion_observation(spec, 'r', 0)
        bad = motion_observation(spec, 'r', 1)
        bad['voxels'][0]['uncertainty']['unit'] = 'm2'
        rows = [first, copy.deepcopy(first), bad, motion_observation(spec, 'r', 2)]
        result = replay_observations(rows, 'r', backend='m3_fixture',
            clock_id='sim:r', fixture_spec=spec, map_settings={'rolling_enabled': True})
        self.assertEqual([r['outcome'] for r in result['steps']],
                         ['fused', 'not_fused', 'rejected', 'fused'])
        self.assertEqual(result['final_snapshot']['cells'][0]['uncertainty']['status'], 'available')

    def test_replay_cli_success_tampered_quality_and_mixed_config(self):
        spec = load_spec()
        rows = [motion_observation(spec, 'r', 0)]
        result = replay_observations(rows, 'r', backend='m3_fixture',
                                    clock_id='sim:r', fixture_spec=spec)
        with tempfile.TemporaryDirectory() as folder:
            receipt = Path(folder) / 'receipt.json'
            command = [sys.executable, '-B', str(CONFIG.parent.parent / 'ros_ws/local_map_replay.py'),
                '--input', str(receipt), '--run-id', 'r', '--clock-id', 'sim:r',
                '--map-backend', 'm3_fixture', '--m3-fixture-config', str(CONFIG)]
            for tamper, extra, expected in ((False, [], 0), (True, [], 1),
                    (False, ['--m2-fixture-config', str(CONFIG)], 1)):
                snapshots = copy.deepcopy(result['snapshots'])
                if tamper:
                    snapshots[0]['cells'][0]['uncertainty']['source'] = 'foreign'
                receipt.write_text(json.dumps(dict(observations=rows, snapshots=snapshots)))
                process = subprocess.run(command + extra, capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, expected, process.stderr + process.stdout)
                self.assertEqual(json.loads(process.stdout)['passed'], expected == 0)
