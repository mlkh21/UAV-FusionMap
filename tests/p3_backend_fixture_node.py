"""Test-only CPU backend faults through the production ROS wrapper; never a research model."""
import importlib.util
from pathlib import Path
import time

from ufm_perception.engine import PerceptionEngine


class FixtureEngine(PerceptionEngine):
    def _infer(self, bundle):
        identity = bundle['header']['sample_id']
        if identity.endswith(':slow'):
            time.sleep(2.)
        result = super()._infer(bundle)
        if identity.endswith(':bad-output'):
            result['header']['frame_id'] = 'map'
        return result


if __name__ == '__main__':
    path = (Path(__file__).resolve().parents[1] / 'ros_ws/src/uav_fusionmap_perception'
            '/scripts/perf01a_placeholder_node.py')
    spec = importlib.util.spec_from_file_location('p3_production_wrapper', path)
    node = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(node)
    node.main(engine_factory=FixtureEngine)
