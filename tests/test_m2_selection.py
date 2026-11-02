"""Explicit selection, fail-closed assembly and deterministic public M2 replay."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2_fixture import load_spec, observation
from ufm_mapping.factory import create_map
from ufm_mapping.replay import replay_observations
from m2_fixture import CONFIG


class M2SelectionTest(unittest.TestCase):
    def test_default_does_not_import_candidate(self):
        code = "from ufm_mapping.factory import create_map; import sys; create_map(); assert not any(k.startswith('ufm_mapping.m2_') or k.endswith('probability_map') for k in sys.modules)"
        subprocess.run([sys.executable, '-B', '-c', code], check=True, timeout=10)

    def test_explicit_fixed_and_rolling(self):
        for rolling in (False, True):
            candidate = create_map('m2_fixture', dict(rolling_enabled=rolling),
                run_id='selected', clock_id='sim:selected', fixture_spec=load_spec())
            candidate.update(observation(load_spec(), 'selected', 0, 'occupied'))
            candidate.update(observation(load_spec(), 'selected', 1, 'occupied'))
            self.assertAlmostEqual(candidate.snapshot()['cells'][0]['probability'], .9)
            self.assertEqual(candidate.rolling_enabled, rolling)

    def test_missing_or_bad_selection_fails_without_fallback(self):
        for kwargs in (dict(backend='typo'), dict(backend='m2_fixture'),
                dict(backend='m2_fixture', fixture_spec=load_spec()),
                dict(fixture_spec=load_spec()), dict(backend='m2_fixture',
                    settings={'free_threshold': .3}, fixture_spec=load_spec())):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                create_map(**kwargs)

    def test_bad_spec_and_nonboolean_rolling_fail(self):
        spec = copy.deepcopy(load_spec())
        spec['fixture_only'] = False
        for config, rolling in ((spec, False), (load_spec(), 'false')):
            with self.assertRaises(ValueError):
                create_map('m2_fixture', {'rolling_enabled': rolling}, run_id='r', clock_id='sim:r',
                           fixture_spec=config)

    def test_replay_retains_order_failures_and_synthetic_quality(self):
        spec = load_spec()
        rows = [observation(spec, 'replay', i, kind) for i, kind in
                enumerate(('occupied', 'occupied', 'unavailable', 'free'))]
        rows.insert(2, copy.deepcopy(rows[0]))
        rows.insert(4, observation(spec, 'replay', 0, 'free'))
        result = replay_observations(rows, 'replay', backend='m2_fixture',
                                    clock_id='sim:replay', fixture_spec=spec)
        self.assertEqual([row['outcome'] for row in result['steps']],
                         ['fused', 'fused', 'not_fused', 'not_fused', 'rejected', 'fused'])
        cell = result['final_snapshot']['cells'][0]
        self.assertAlmostEqual(cell['probability'], .75)
        self.assertIsNone(cell['confidence'])
        self.assertEqual(cell['uncertainty']['status'], 'unavailable')
        self.assertEqual(result, replay_observations(rows, 'replay', backend='m2_fixture',
                                                   clock_id='sim:replay', fixture_spec=spec))

    def test_replay_cli_rejects_altered_saved_expectation(self):
        spec = load_spec()
        rows = [observation(spec, 'cli', 0, 'occupied')]
        result = replay_observations(rows, 'cli', backend='m2_fixture', clock_id='sim:cli',
                                     fixture_spec=spec)
        result['snapshots'][0]['cells'][0]['probability'] = .8
        with tempfile.TemporaryDirectory() as folder:
            receipt = Path(folder) / 'receipt.json'
            receipt.write_text(json.dumps(dict(observations=rows, snapshots=result['snapshots'])))
            process = subprocess.run([sys.executable, '-B', str(CONFIG.parent.parent /
                'ros_ws/local_map_replay.py'), '--input', str(receipt), '--run-id', 'cli',
                '--map-backend', 'm2_fixture', '--m2-fixture-config', str(CONFIG), '--clock-id', 'sim:cli'],
                capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 1, process.stderr)
            report = json.loads(process.stdout)
            self.assertFalse(report['passed'])
            self.assertIn('replayed snapshots differ', report['errors'][0])
