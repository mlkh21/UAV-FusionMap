"""4D-Radar-Diffusion 研究后端接入前置检查。

该模块只检查路径、配置、输入契约和依赖状态，不导入研究模型、不加载权重，
也不执行生成。当前仓库没有可调用的研究适配器，因此检查结果不会替代后端实现。
"""
import argparse
import json
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .input_contract import FORBIDDEN_INPUT_KEYS


UAV_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESEARCH_ROOT = UAV_ROOT.parent / "4D-Radar-Diffusion"
DEFAULT_PYTHON = Path("/home/zxj/anaconda3/envs/Radar-Diffusion/bin/python")
REQUIRED_BUNDLE_KEYS = frozenset({"header", "radar", "infrared", "state", "context"})
DEFAULT_CALIBRATION_FILES = (
    "calib_radar_to_livox.txt",
    "calib_radar_to_thermal.txt",
    "calib_livox_to_thermal.txt",
    "calib_cam_thermal.txt",
)
NORMALIZATION_PROTOCOLS = frozenset({"radar_normalization_v1", "radar_normalization_v2"})


@dataclass(frozen=True)
class ResearchPreflightConfig:
    research_root: Path = DEFAULT_RESEARCH_ROOT
    launcher: Optional[Path] = None
    checkpoint_paths: Tuple[Path, ...] = ()
    threshold_artifact: Optional[Path] = None
    normalization_spec: Optional[Path] = None
    calibration_dir: Optional[Path] = None
    coordinate_contract: Optional[Path] = None
    input_contract: Path = UAV_ROOT / "configs/research_backend_input_contract.json"
    backend_adapter: Path = UAV_ROOT / "perception/ufm_perception/research_backend.py"
    python_executable: Path = DEFAULT_PYTHON
    required_python_modules: Tuple[str, ...] = ("numpy", "torch", "yaml")
    required_calibration_files: Tuple[str, ...] = DEFAULT_CALIBRATION_FILES
    model_type: str = "ldm"

    def resolved(self):
        root = Path(self.research_root)
        launcher = self.launcher or root / "diffusion_consistency_radar/launch/inference_ldm.sh"
        checkpoints = self.checkpoint_paths or (
            root / "Result/train_results/formal_v2_80m_86p8_v1/vae/vae_best.pt",
            root / "Result/train_results/formal_v2_80m_86p8_v1/ldm/ldm_best.pt",
        )
        threshold = self.threshold_artifact or (
            root / "Result/train_results/formal_v2_80m_86p8_v1/ldm/occupancy_threshold.json"
        )
        calibration = self.calibration_dir or (root / "Data/config")
        coordinate = self.coordinate_contract
        return self.__class__(
            research_root=root, launcher=Path(launcher), checkpoint_paths=tuple(map(Path, checkpoints)),
            threshold_artifact=Path(threshold), normalization_spec=(
                Path(self.normalization_spec) if self.normalization_spec else None),
            calibration_dir=Path(calibration), coordinate_contract=(
                Path(coordinate) if coordinate else None), input_contract=Path(self.input_contract),
            backend_adapter=Path(self.backend_adapter), python_executable=Path(self.python_executable),
            required_python_modules=tuple(self.required_python_modules),
            required_calibration_files=tuple(self.required_calibration_files), model_type=self.model_type,
        )


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk_keys(child)


def validate_research_input(bundle):
    """验证研究 forward 边界，只允许 Radar+IR 及状态/变换上下文。"""
    if not isinstance(bundle, dict):
        raise ValueError("research input must be a mapping")
    forbidden = sorted(FORBIDDEN_INPUT_KEYS.intersection(_walk_keys(bundle)))
    if forbidden:
        raise ValueError("research input contains training-only fields: " + ",".join(forbidden))
    missing = sorted(REQUIRED_BUNDLE_KEYS.difference(bundle))
    if missing:
        raise ValueError("research input missing SensorBundle fields: " + ",".join(missing))
    header = bundle["header"]
    radar = bundle["radar"]
    infrared = bundle["infrared"]
    context = bundle["context"]
    if header.get("status") not in ("valid", "degraded"):
        raise ValueError("research input status is not usable")
    if radar.get("header", {}).get("frame_id") != "radar":
        raise ValueError("research Radar frame must be radar")
    if infrared.get("header", {}).get("frame_id") != "thermal_optical":
        raise ValueError("research IR frame must be thermal_optical")
    if context.get("source_frame_id") != "radar" or context.get("mapping_frame_id") != "odom":
        raise ValueError("research input requires radar to odom context")
    return True


def _check_coordinate_contract(path):
    if path is None:
        return "coordinate_contract_unbound"
    if not path.is_file():
        return "coordinate_contract_missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "coordinate_contract_invalid:" + type(exc).__name__
    matrix = value.get("T_target_source")
    if (value.get("source_frame") != "model_lidar" or
            value.get("target_frame") not in ("radar", "base_link") or
            value.get("status") != "verified" or
            not isinstance(matrix, list) or len(matrix) != 16 or
            any(not isinstance(item, (int, float)) or not math.isfinite(item)
                for item in matrix) or
            matrix[12:] != [0, 0, 0, 1]):
        return "coordinate_contract_invalid"
    return None


def _check_normalization_spec(path):
    if path is None:
        return "research_normalization_missing_or_unbound"
    if not path.is_file():
        return "research_normalization_missing_or_unbound"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "research_normalization_invalid:" + type(exc).__name__
    if not isinstance(value, dict) or value.get("protocol") not in NORMALIZATION_PROTOCOLS:
        return "research_normalization_invalid"
    if value.get("formal") is not True:
        return "research_normalization_not_formal"
    if (not isinstance(value.get("training_scenes"), list) or
            not value["training_scenes"] or
            any(not isinstance(scene, str) or not scene for scene in value["training_scenes"])):
        return "research_normalization_invalid_training_scenes"
    target_size = value.get("target_size")
    if (not isinstance(target_size, list) or len(target_size) != 3 or
            any(type(item) is not int or item <= 0 for item in target_size)):
        return "research_normalization_invalid_grid"
    for name in ("source_pc_range", "model_pc_range"):
        bounds = value.get(name)
        if (not isinstance(bounds, list) or len(bounds) != 6 or
                any(isinstance(item, bool) or not isinstance(item, (int, float)) or
                    not math.isfinite(float(item)) for item in bounds) or
                any(bounds[index] >= bounds[index + 3] for index in range(3))):
            return "research_normalization_invalid_grid"
    source = value["source_pc_range"]
    model = value["model_pc_range"]
    if any(model[index] < source[index] or model[index + 3] > source[index + 3]
           for index in range(3)):
        return "research_normalization_invalid_grid"
    intensity = value.get("intensity")
    doppler = value.get("doppler")
    variance = value.get("variance")
    if not isinstance(intensity, dict) or not isinstance(doppler, dict) or not isinstance(variance, dict):
        return "research_normalization_invalid"
    if value["protocol"] == "radar_normalization_v1":
        if intensity.get("transform") != "log1p_robust_zscore":
            return "research_normalization_invalid_intensity"
        if not all(key in intensity for key in ("log_median", "log_iqr", "clip")):
            return "research_normalization_invalid_intensity"
    else:
        if (intensity.get("transform") != "identity_robust_zscore" or
                intensity.get("quantity") != "signal_to_noise_ratio" or
                intensity.get("unit") != "dB" or
                not all(key in intensity for key in ("median", "iqr", "clip"))):
            return "research_normalization_invalid_intensity"
    scale_mps = doppler.get("scale_mps")
    if (doppler.get("transform") != "symmetric_physical_scale" or
            isinstance(scale_mps, bool) or not isinstance(scale_mps, (int, float)) or
            not math.isfinite(float(scale_mps)) or scale_mps <= 0 or
            doppler.get("clip") != [-1.0, 1.0] or
            variance.get("transform") != "identity"):
        return "research_normalization_invalid_channels"
    return None


def _check_threshold_artifact(path, model_type):
    if path is None or not path.is_file():
        return "research_threshold_missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "research_threshold_invalid:" + type(exc).__name__
    threshold = value.get("selected_threshold") if isinstance(value, dict) else None
    digest = value.get("checkpoint_sha256") if isinstance(value, dict) else None
    expected_stage = "cd" if model_type == "cd" else "ldm"
    if (not isinstance(value, dict) or
            value.get("protocol") != "occupancy_threshold_validation_artifact_v2" or
            value.get("checkpoint_protocol") != "formal_chain_v2" or
            value.get("stage") != expected_stage or
            not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or
            not math.isfinite(float(threshold)) or not 0.0 < float(threshold) < 1.0 or
            not isinstance(digest, str) or len(digest) != 64 or
            any(character not in "0123456789abcdef" for character in digest)):
        return "research_threshold_invalid"
    return None


def _check_calibration_files(directory, filenames):
    if not directory.is_dir():
        return "research_calibration_missing"
    missing = []
    for filename in filenames:
        path = directory / filename
        if path.is_symlink() or not path.is_file():
            missing.append(filename)
    if missing:
        return "research_calibration_files_missing:" + ",".join(missing)
    return None


def _discover_artifact_candidates(root):
    result_root = root / "Result/train_results"
    if not result_root.is_dir():
        return []
    candidates = []
    for directory in sorted(path for path in result_root.iterdir() if path.is_dir()):
        stage_paths = {
            "vae": directory / "vae/vae_best.pt",
            "ldm": directory / "ldm/ldm_best.pt",
            "cd": directory / "cd/cd_best.pt",
            "ldm_threshold": directory / "ldm/occupancy_threshold.json",
            "cd_threshold": directory / "cd/occupancy_threshold.json",
        }
        present = sorted(name for name, path in stage_paths.items() if path.is_file())
        if present:
            candidates.append({"name": directory.name, "artifacts": present})
    return candidates


def _check_input_contract(path):
    if not path.is_file():
        return "input_contract_missing"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "input_contract_invalid:" + type(exc).__name__
    if value.get("schema_version") != "research_backend_input_contract_v1":
        return "input_contract_invalid"
    if any(value.get(key) is not False for key in
           ("lidar_forward", "target_forward", "observed_mask_forward")):
        return "input_contract_allows_training_supervision"
    if not set(value.get("required_top_level", ())).issuperset(REQUIRED_BUNDLE_KEYS):
        return "input_contract_missing_required_fields"
    if not set(FORBIDDEN_INPUT_KEYS).issubset(set(value.get("forbidden_recursive_keys", ()) )):
        return "input_contract_missing_forbidden_fields"
    return None


def _check_python_dependencies(executable, modules):
    if not executable.is_file() or not os.access(executable, os.X_OK):
        return ["python_executable_missing"]
    code = "import importlib.util, sys; missing=[m for m in sys.argv[1:] if importlib.util.find_spec(m) is None]; print('\\n'.join(missing))"
    try:
        completed = subprocess.run([str(executable), "-c", code, *modules],
                                   capture_output=True, text=True, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return ["dependency_probe_failed:" + type(exc).__name__]
    if completed.returncode != 0:
        return ["dependency_probe_failed:exit_" + str(completed.returncode)]
    return ["python_module_missing:" + line for line in completed.stdout.splitlines() if line]


def preflight(config=None):
    """返回可序列化的检查报告；不抛出路径/依赖检查异常。"""
    config = (config or ResearchPreflightConfig()).resolved()
    checks = []
    blockers = []

    def check(name, passed, reason=None):
        checks.append(dict(name=name, passed=bool(passed), reason=(reason or "") if not passed else ""))
        if not passed and reason:
            blockers.append(reason)

    check("research_root", config.research_root.is_dir(), "research_root_missing")
    check("launcher", config.launcher.is_file(), "research_launcher_missing")
    check("inference_cli", (config.research_root / "diffusion_consistency_radar/scripts/inference.py").is_file(),
          "research_inference_cli_missing")
    check("checkpoint_chain_cli", (config.research_root / "diffusion_consistency_radar/scripts/diagnose_checkpoint_chain.py").is_file(),
          "research_checkpoint_chain_cli_missing")
    for path in config.checkpoint_paths:
        check("checkpoint:" + str(path), path.is_file(), "research_checkpoint_missing:" + str(path))
    threshold_reason = _check_threshold_artifact(config.threshold_artifact, config.model_type)
    check("threshold_artifact", threshold_reason is None, threshold_reason)
    normalization_reason = _check_normalization_spec(config.normalization_spec)
    check("normalization_spec", normalization_reason is None, normalization_reason)
    calibration_reason = _check_calibration_files(
        config.calibration_dir, config.required_calibration_files)
    check("calibration_files", calibration_reason is None, calibration_reason)
    coordinate_reason = _check_coordinate_contract(config.coordinate_contract)
    check("coordinate_contract", coordinate_reason is None, coordinate_reason)
    input_reason = _check_input_contract(config.input_contract)
    check("input_contract", input_reason is None, input_reason)
    dependency_reasons = _check_python_dependencies(config.python_executable, config.required_python_modules)
    check("python_executable", not any(reason == "python_executable_missing" for reason in dependency_reasons),
          next((reason for reason in dependency_reasons if reason == "python_executable_missing"), None))
    for reason in dependency_reasons:
        if reason != "python_executable_missing":
            check("dependency:" + reason, False, reason)
    check("research_adapter", config.backend_adapter.is_file(), "research_backend_adapter_missing")

    return dict(ready=not blockers, blockers=blockers, checks=checks,
                model_type=config.model_type, research_root=str(config.research_root),
                artifact_candidates=_discover_artifact_candidates(config.research_root))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Research backend preflight; no model execution")
    parser.add_argument("--research-root", type=Path, default=DEFAULT_RESEARCH_ROOT)
    parser.add_argument("--launcher", type=Path)
    parser.add_argument("--checkpoint", type=Path, action="append", dest="checkpoints")
    parser.add_argument("--threshold-artifact", type=Path)
    parser.add_argument("--normalization-spec", type=Path)
    parser.add_argument("--calibration-dir", type=Path)
    parser.add_argument("--coordinate-contract", type=Path)
    parser.add_argument("--model-type", choices=("ldm", "cd"), default="ldm")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = preflight(ResearchPreflightConfig(
        research_root=args.research_root,
        launcher=args.launcher,
        checkpoint_paths=tuple(args.checkpoints or ()),
        threshold_artifact=args.threshold_artifact,
        normalization_spec=args.normalization_spec,
        calibration_dir=args.calibration_dir,
        coordinate_contract=args.coordinate_contract,
        model_type=args.model_type,
    ))
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print("research_preflight=" + ("READY" if report["ready"] else "BLOCKED"))
        for blocker in report["blockers"]:
            print("BLOCKER " + blocker)
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
