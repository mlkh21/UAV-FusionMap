"""Fail-closed mode receipt oracle and old-map preservation."""
import copy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
for relative in ('ros_ws', 'mapping', 'perception'):
    sys.path.insert(0, str(ROOT / relative))

from perception_mode_validation import validate_unavailable_mode
from test_perf01a_contract import valid_bundle
from ufm_mapping.local_map import SparseLocalMap
from ufm_perception.modes import disabled_infer, placeholder_infer, research_infer


def sample(mode='disabled'):
    run_id = 'fixture-run'
    bundle = valid_bundle(run_id=run_id, radar_timestamp=0)
    bundle['header']['sample_id'] = 'sensors.bundle:fixture.radar:%s:0' % run_id
    observation = (disabled_infer(bundle) if mode == 'disabled' else
                   research_infer(bundle, dict(ready=False, blockers=['research_checkpoint_missing'])))
    event = dict(run_id=run_id, clock_id='sim:' + run_id,
                 parent_sample_id=bundle['header']['sample_id'], business_timestamp=0,
                 stage='map_snapshot_publish', status='unavailable', reason='observation_not_fused')
    graph = dict(errors=[])
    query = dict(status='unavailable', revision=0, probability=None, reason='map_unavailable')
    return run_id, mode, 1, [bundle], [observation], [event], [], query, graph


class PerceptionModeValidationTest(unittest.TestCase):
    def test_disabled_and_research_refusal(self):
        for mode in ('disabled', 'research'):
            with self.subTest(mode=mode):
                self.assertEqual(validate_unavailable_mode(*sample(mode)), [])

    def test_rejects_fallback_free_and_missing_map_refusal(self):
        args = list(sample('research'))
        args[4][0]['header']['status'] = 'valid'
        args[4][0]['header']['source_type'] = 'fixture'
        args[4][0]['voxels'] = [dict(index=[0, 0, 0], observed=True, probability=.1)]
        self.assertTrue(validate_unavailable_mode(*args))
        args = list(sample())
        args[5] = []
        self.assertIn('map refusal count differs from source', validate_unavailable_mode(*args))

    def test_rejects_leaked_supervision_and_map_refresh(self):
        args = list(sample())
        args[3][0]['observed_mask'] = []
        args[6] = [dict(revision=1)]
        errors = validate_unavailable_mode(*args)
        self.assertTrue(any('training supervision' in error for error in errors))
        self.assertTrue(any('map snapshots' in error for error in errors))

    def test_existing_map_is_not_refreshed_by_unavailable(self):
        bundle = valid_bundle()
        local_map = SparseLocalMap('mode-fixture')
        initial = placeholder_infer(bundle)
        self.assertTrue(local_map.update(initial))
        before = copy.deepcopy(local_map.snapshot())
        later = valid_bundle(radar_timestamp=150_000_000)
        later['header']['sample_id'] += ':later'
        self.assertFalse(local_map.update(disabled_infer(later)))
        after = local_map.snapshot()
        self.assertEqual(after['revision'], before['revision'])
        self.assertEqual(after['cells'], before['cells'])
        self.assertEqual(after['header']['timestamp'], before['header']['timestamp'])


if __name__ == '__main__':
    unittest.main()
