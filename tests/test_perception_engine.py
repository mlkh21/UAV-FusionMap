"""P3-SW-01: backend results must retain the input contract before publication."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from test_perf01a_contract import valid_bundle
from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.engine import PerceptionEngine, UntrustedInputError
from ufm_perception.placeholder import placeholder_infer


class PerceptionEngineTest(unittest.TestCase):
    def engine(self, **kwargs):
        return PerceptionEngine(run_id='perf-run', **kwargs)

    def test_modes_and_old_placeholder_output(self):
        bundle = valid_bundle()
        self.assertEqual(self.engine().process(bundle), placeholder_infer(bundle))
        for mode, source in (('disabled', 'derived'), ('research', 'model')):
            result = self.engine(mode=mode).process(bundle)
            self.assertEqual(result['header']['source_type'], source)
            self.assertEqual(result['header']['status'], 'unavailable')
            self.assertEqual(result['voxels'], [])

    def test_foreign_or_untrusted_input_is_rejected(self):
        for group, key, value in (('header', 'run_id', 'foreign'),
                                  ('context', 'reference_timestamp', 0),
                                  ('context', 'mapping_frame_id', 'map')):
            bundle = valid_bundle()
            bundle[group][key] = value
            with self.subTest(key=key), self.assertRaises(UntrustedInputError):
                self.engine().process(bundle)

    def test_bad_inner_bundle_emits_unavailable_without_calling_backend(self):
        bundle = valid_bundle()
        bundle['radar']['header']['clock_id'] = 'foreign'
        with patch('ufm_perception.engine.placeholder_infer') as backend:
            result = self.engine().process(bundle)
        backend.assert_not_called()
        self.assertEqual(result['header']['status'], 'unavailable')
        self.assertEqual(result['header']['timestamp'], bundle['header']['timestamp'])

    def test_backend_cannot_mutate_input_identity_for_failure(self):
        bundle = valid_bundle()
        before = copy.deepcopy(bundle)
        def corrupt(value, **kwargs):
            value['header']['timestamp'] = 0
            value['context']['reference_timestamp'] = 0
            raise RuntimeError('fixture backend failed')
        with patch('ufm_perception.engine.placeholder_infer', side_effect=corrupt):
            result = self.engine().process(bundle)
        self.assertEqual(bundle, before)
        self.assertEqual(result['header']['timestamp'], before['header']['timestamp'])

    def test_wrong_backend_identity_context_and_geometry_are_unavailable(self):
        valid = placeholder_infer(valid_bundle())
        changes = [('header', 'timestamp', 0), ('header', 'sample_id', 'foreign'),
                   ('header', 'source_type', 'model'), ('header', 'frame_id', 'map'),
                   ('header', 'schema_version', '9'), ('context', 'calibration_id', 'foreign'),
                   ('context', 'reference_timestamp', 0), ('context', 'clock_id', 'foreign'),
                   (None, 'resolution', [1., 1., 1.]), (None, 'shape', [1, 1, 1]),
                   (None, 'origin', [0., 0., 0.]), (None, 'observed_domain_source', '')]
        for group, key, value in changes:
            candidate = copy.deepcopy(valid)
            (candidate[group] if group else candidate)[key] = value
            with self.subTest(group=group, key=key), \
                    patch('ufm_perception.engine.placeholder_infer', return_value=candidate):
                result = self.engine().process(valid_bundle())
                self.assertEqual(result['header']['status'], 'unavailable')
                self.assertEqual(result['voxels'], [])

    def test_bad_voxels_cannot_update_existing_map_and_next_frame_recovers(self):
        initial = placeholder_infer(valid_bundle())
        invalid = [dict(probability=float('nan')), dict(probability=1.1),
                   dict(index=[-1, 0, 0]), dict(index=[1.5, 0, 0]),
                   dict(index=[64, 0, 0]), dict(observed=1), dict(confidence=float('nan')),
                   dict(uncertainty=dict(status='available', value=[.1], kind='', unit='', source=''))]
        for change in invalid:
            local_map = SparseLocalMap()
            local_map.update(initial)
            before = local_map.snapshot()
            later = valid_bundle(radar_timestamp=150_000_000)
            later['header']['sample_id'] += ':later'
            candidate = placeholder_infer(later)
            candidate['voxels'][0].update(change)
            with self.subTest(change=change), \
                    patch('ufm_perception.engine.placeholder_infer', return_value=candidate):
                result = self.engine().process(later)
            self.assertFalse(local_map.update(result))
            self.assertEqual(before, local_map.snapshot())
            recovery = valid_bundle(radar_timestamp=200_000_000)
            recovery['header']['sample_id'] += ':recovery'
            self.assertTrue(local_map.update(self.engine().process(recovery)))

    def test_nonvalid_and_duplicate_voxel_results_are_rejected(self):
        candidate = placeholder_infer(valid_bundle())
        candidate['header'].update(status='unavailable', reason='failed')
        with patch('ufm_perception.engine.placeholder_infer', return_value=candidate):
            self.assertEqual(self.engine().process(valid_bundle())['voxels'], [])
        candidate = placeholder_infer(valid_bundle())
        candidate['voxels'].append(copy.deepcopy(candidate['voxels'][0]))
        with patch('ufm_perception.engine.placeholder_infer', return_value=candidate):
            self.assertEqual(self.engine().process(valid_bundle())['header']['status'], 'unavailable')

    def test_training_fields_rejected_before_all_modes(self):
        for mode in ('disabled', 'placeholder', 'research'):
            for key in ('lidar', 'target', 'observed_mask'):
                bundle = valid_bundle()
                bundle['metadata'] = {key: []}
                result = self.engine(mode=mode).process(bundle)
                self.assertEqual(result['header']['status'], 'unavailable')
                self.assertIn('training-only', result['header']['reason'])

    def test_nondefault_and_rolling_geometry(self):
        engine = self.engine(resolution=(.25, .5, 1.), shape=(40, 8, 8), origin=(0., -2., -4.))
        self.assertEqual(engine.process(valid_bundle())['shape'], [40, 8, 8])
        bundle = valid_bundle()
        bundle['context']['T_mapping_body'][3] = 10.
        self.assertEqual(self.engine(rolling_grid=True).process(bundle),
                         placeholder_infer(bundle, rolling_grid=True))

    def test_disabled_and_placeholder_import_no_research_modules(self):
        code = ('import json,sys; from ufm_perception.engine import PerceptionEngine; '
                'bundle=json.load(sys.stdin); '
                '[PerceptionEngine("perf-run",mode=mode).process(bundle) '
                'for mode in ("disabled","placeholder")]; '
                'assert "ufm_perception.research_preflight" not in sys.modules; '
                'assert "torch" not in sys.modules')
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / 'perception'))
        subprocess.run([sys.executable, '-B', '-c', code], check=True, env=environment,
                       input=json.dumps(valid_bundle()), text=True)


if __name__ == '__main__':
    unittest.main()
