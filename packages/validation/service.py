"""Validation service for normalized embodied datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.common.config import display_path, resolve_repo_path
from packages.common.io import dump_json, load_json, load_jsonl


@dataclass(slots=True)
class ValidationResult:
    """Validation summary for one normalized dataset."""

    dataset_root: Path
    status: str
    error_count: int
    warning_count: int
    report_path: Path
    checks: list[dict[str, Any]]


def validate_dataset(dataset_root: str | Path, write_report: bool = True) -> ValidationResult:
    """Validate a normalized dataset artifact folder."""
    root = resolve_repo_path(dataset_root)
    checks: list[dict[str, Any]] = []
    manifest_path = root / "dataset_manifest.json"
    episodes_jsonl_path = root / "episodes.jsonl"
    manifest = _load_required_json(manifest_path, checks, "dataset_manifest")
    episodes_jsonl = _load_required_jsonl(episodes_jsonl_path, checks, "episodes_jsonl")

    if isinstance(manifest, dict):
        episodes = manifest.get("episodes", [])
        if not isinstance(episodes, list):
            _add(checks, "error", "manifest_episodes_type", manifest_path, "manifest episodes must be a list")
            episodes = []
        if len(episodes) != int(manifest.get("episode_count", -1)):
            _add(checks, "error", "episode_count_mismatch", manifest_path, "episode_count does not match episodes list")
        if episodes_jsonl is not None and len(episodes_jsonl) != len(episodes):
            _add(checks, "error", "episodes_jsonl_count_mismatch", episodes_jsonl_path, "episodes.jsonl count differs from manifest")
        for episode in episodes:
            if isinstance(episode, dict):
                _validate_episode(root, episode, checks)

    quality_path = root / "quality_report.json"
    if quality_path.exists():
        quality = load_json(quality_path)
        if not isinstance(quality, dict):
            _add(checks, "error", "quality_report_type", quality_path, "quality_report must be a mapping")
        elif int(quality.get("fail_count", 0)) > 0:
            _add(checks, "warning", "quality_failures_present", quality_path, "quality_report contains failed episodes")
    else:
        _add(checks, "warning", "quality_report_missing", quality_path, "quality_report.json is absent")

    error_count = sum(1 for check in checks if check["severity"] == "error")
    warning_count = sum(1 for check in checks if check["severity"] == "warning")
    status = "pass" if error_count == 0 else "fail"
    report = {
        "dataset_root": display_path(root),
        "status": status,
        "error_count": error_count,
        "warning_count": warning_count,
        "checks": checks,
    }
    report_path = root / "validation_report.json"
    if write_report:
        dump_json(report_path, report)
    return ValidationResult(
        dataset_root=root,
        status=status,
        error_count=error_count,
        warning_count=warning_count,
        report_path=report_path,
        checks=checks,
    )


def _validate_episode(dataset_root: Path, episode: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    episode_id = str(episode.get("episode_id", ""))
    if not episode_id:
        _add(checks, "error", "episode_id_missing", dataset_root, "episode is missing episode_id")
        return
    episode_root = _episode_root(dataset_root, episode)
    episode_json = episode_root / "episode.json"
    _require_file(checks, "episode_json", episode_json)
    _require_file(checks, "events", episode_root / "events.jsonl")
    _require_file(checks, "plan_trace", episode_root / "plan_trace.jsonl")
    _validate_ref(episode_root, episode.get("action_ref"), checks, "action_ref")
    _validate_ref(episode_root, episode.get("state_ref"), checks, "state_ref")
    for index, ref in enumerate(episode.get("observation_refs", [])):
        _validate_ref(episode_root, ref, checks, f"observation_ref_{index}")
    metadata = episode.get("metadata", {})
    if isinstance(metadata, dict) and isinstance(metadata.get("quality"), dict):
        quality_ref = episode_root / str(metadata["quality"].get("quality_ref", "quality.json"))
        _require_file(checks, "quality", quality_ref)


def _validate_ref(episode_root: Path, ref: Any, checks: list[dict[str, Any]], check_name: str) -> None:
    if not isinstance(ref, dict) or not ref.get("path"):
        _add(checks, "warning", f"{check_name}_missing", episode_root, f"{check_name} is missing")
        return
    _require_file(checks, check_name, episode_root / str(ref["path"]))


def _episode_root(dataset_root: Path, episode: dict[str, Any]) -> Path:
    artifact_root = episode.get("artifact_root")
    if artifact_root:
        candidate = Path(str(artifact_root))
        return candidate if candidate.is_absolute() else resolve_repo_path(candidate)
    return dataset_root / "episodes" / str(episode["episode_id"])


def _load_required_json(path: Path, checks: list[dict[str, Any]], check_name: str) -> Any:
    if not path.exists():
        _add(checks, "error", f"{check_name}_missing", path, f"{path.name} is missing")
        return None
    try:
        return load_json(path)
    except ValueError as exc:
        _add(checks, "error", f"{check_name}_invalid_json", path, str(exc))
        return None


def _load_required_jsonl(path: Path, checks: list[dict[str, Any]], check_name: str) -> list[dict[str, Any]] | None:
    if not path.exists():
        _add(checks, "error", f"{check_name}_missing", path, f"{path.name} is missing")
        return None
    try:
        return load_jsonl(path)
    except ValueError as exc:
        _add(checks, "error", f"{check_name}_invalid_jsonl", path, str(exc))
        return None


def _require_file(checks: list[dict[str, Any]], check_name: str, path: Path) -> None:
    if not path.exists():
        _add(checks, "error", f"{check_name}_missing", path, f"missing {check_name}")


def _add(checks: list[dict[str, Any]], severity: str, check: str, path: Path, message: str) -> None:
    checks.append(
        {
            "severity": severity,
            "check": check,
            "path": display_path(path),
            "message": message,
        }
    )
