"""ALG-01/T-13B研究前置和感知模式 fail-closed 契约。"""
import ast
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for relative in ("mapping", "perception", "sensors", "ros_ws"):
    sys.path.insert(0, str(ROOT / relative))

from test_perf01a_contract import valid_bundle
from ufm_perception.modes import disabled_infer, placeholder_infer, research_infer
from ufm_perception.research_preflight import (
    ResearchPreflightConfig,
    preflight,
    validate_research_input,
)


class ResearchPreflightTest(unittest.TestCase):
    def _config(self, root, **changes):
        research = root / "research"
        project = research / "diffusion_consistency_radar"
        (project / "launch").mkdir(parents=True)
        (project / "scripts").mkdir()
        (research / "Result/train_results/formal/vae").mkdir(parents=True)
        (research / "Result/train_results/formal/ldm").mkdir(parents=True)
        (research / "Data/config").mkdir(parents=True)
        launcher = project / "launch/inference_ldm.sh"
        inference = project / "scripts/inference.py"
        launcher.write_text("#!/bin/sh\n", encoding="utf-8")
        inference.write_text("# fixture\n", encoding="utf-8")
        vae = research / "Result/train_results/formal/vae/vae_best.pt"
        model = research / "Result/train_results/formal/ldm/ldm_best.pt"
        threshold = research / "Result/train_results/formal/ldm/occupancy_threshold.json"
        normalization = research / "normalization.json"
        calibration = research / "Data/config"
        coordinate = root / "coordinate.json"
        adapter = root / "research_backend.py"
        for path in (vae, model, threshold, adapter):
            path.write_text("fixture\n", encoding="utf-8")
        normalization.write_text(json.dumps({
            "protocol": "radar_normalization_v1",
            "formal": True,
            "training_scenes": ["fixture"],
            "frame_count": 1,
            "target_size": [32, 128, 128],
            "source_pc_range": [0, -20, -6, 80, 20, 10],
            "model_pc_range": [0, -20, -6, 80, 20, 10],
            "intensity": {
                "transform": "log1p_robust_zscore",
                "log_median": 2.0,
                "log_iqr": 1.0,
                "clip": [-5.0, 5.0],
            },
            "doppler": {
                "transform": "symmetric_physical_scale",
                "scale_mps": 86.8,
                "clip": [-1.0, 1.0],
            },
            "variance": {"transform": "identity"},
        }), encoding="utf-8")
        threshold.write_text(json.dumps({
            "protocol": "occupancy_threshold_validation_artifact_v2",
            "checkpoint_protocol": "formal_chain_v2",
            "stage": "ldm",
            "selected_threshold": 0.2,
            "checkpoint_sha256": "0" * 64,
        }), encoding="utf-8")
        coordinate.write_text(json.dumps({
            "source_frame": "model_lidar", "target_frame": "radar",
            "status": "verified", "T_target_source": [1, 0, 0, 0, 0, 1, 0, 0,
                                                             0, 0, 1, 0, 0, 0, 0, 1],
        }), encoding="utf-8")
        values = dict(
            research_root=research, launcher=launcher,
            checkpoint_paths=(vae, model), threshold_artifact=threshold,
            normalization_spec=normalization, calibration_dir=calibration,
            coordinate_contract=coordinate,
            input_contract=ROOT / "configs/research_backend_input_contract.json",
            backend_adapter=adapter, python_executable=Path(sys.executable),
        )
        values.update(changes)
        return ResearchPreflightConfig(**values)

    def test_disabled_and_placeholder_work_without_research_import_or_artifacts(self):
        bundle = valid_bundle()
        disabled = disabled_infer(bundle)
        self.assertEqual(disabled["header"]["status"], "unavailable")
        self.assertEqual(disabled["voxels"], [])
        self.assertEqual(placeholder_infer(bundle)["header"]["source_type"], "fixture")

        node = (ROOT / "ros_ws/src/uav_fusionmap_perception/scripts/perf01a_placeholder_node.py").read_text()
        tree = ast.parse(node)
        top_level_imports = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        imported = " ".join(ast.dump(node) for node in top_level_imports)
        self.assertNotIn("research_preflight", imported)
        self.assertNotIn("torch", imported)

    def test_missing_research_cli_is_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root)
            report = preflight(config)
            self.assertFalse(report["ready"])
            self.assertIn("research_checkpoint_chain_cli_missing", report["blockers"])

    def test_real_protocol_assets_are_checked_without_model_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root)
            for filename in config.required_calibration_files:
                (config.calibration_dir / filename).write_text("fixture\n", encoding="utf-8")
            report = preflight(config)
            by_name = {item["name"]: item for item in report["checks"]}
            self.assertTrue(by_name["threshold_artifact"]["passed"])
            self.assertTrue(by_name["normalization_spec"]["passed"])
            self.assertTrue(by_name["calibration_files"]["passed"])

    def test_missing_checkpoint_is_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._config(root)
            missing = config.checkpoint_paths[1].with_name("missing.pt")
            report = preflight(ResearchPreflightConfig(**{
                **config.__dict__, "checkpoint_paths": (config.checkpoint_paths[0], missing)
            }))
            self.assertFalse(report["ready"])
            self.assertTrue(any(item.startswith("research_checkpoint_missing:")
                                for item in report["blockers"]))

    def test_research_input_rejects_lidar_target_and_observed_mask(self):
        bundle = valid_bundle()
        for key in ("lidar", "target", "occupancy_target", "observed_mask"):
            invalid = copy.deepcopy(bundle)
            invalid["metadata"] = {key: []}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "training-only"):
                validate_research_input(invalid)
        self.assertTrue(validate_research_input(bundle))

    def test_research_failure_never_falls_back_to_placeholder(self):
        bundle = valid_bundle()
        report = {"ready": False, "blockers": ["research_checkpoint_missing"]}
        result = research_infer(bundle, report)
        self.assertEqual(result["header"]["source_type"], "model")
        self.assertEqual(result["header"]["status"], "unavailable")
        self.assertEqual(result["voxels"], [])
        self.assertIn("research_preflight_blocked", result["header"]["reason"])
        self.assertNotEqual(result, placeholder_infer(bundle))

    def test_old_placeholder_ros_entry_remains_default(self):
        launch = (ROOT / "ros_ws/launch/perf01a_placeholder.launch").read_text()
        self.assertIn('<arg name="mode" default="placeholder" />', launch)
        self.assertIn('type="perf01a_placeholder_node.py"', launch)
        self.assertIn('<param name="mode" value="$(arg mode)" />', launch)


if __name__ == "__main__":
    unittest.main()
