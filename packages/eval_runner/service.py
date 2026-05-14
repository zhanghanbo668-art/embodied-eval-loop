"""Minimal evaluation runner for the embodied evaluation stack MVP."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from packages.common.config import resolve_repo_path
from packages.common.io import dump_json, dump_jsonl, ensure_dir, load_json, load_jsonl, load_yaml
from packages.eval_runner.policy_adapters import load_policy_adapter
from packages.registry.service import register_run
from packages.schemas.models import RunRecord


@dataclass(slots=True)
class EvalResult:
    """Summary of one completed evaluation run."""

    run_root: Path
    run_manifest_path: Path
    metrics_path: Path
    episodes_path: Path
    metrics: dict[str, Any]
    episode_count: int


def _load_dataset_manifest(dataset_config_path: Path) -> dict[str, Any]:
    config = load_yaml(dataset_config_path)
    dataset_id = config["output_dataset_id"]
    manifest_path = resolve_repo_path(f"outputs/datasets/{dataset_id}/dataset_manifest.json")
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Dataset manifest not found for {dataset_id}. Run ingest first: {manifest_path}"
        )
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid dataset manifest: {manifest_path}")
    return manifest


def _load_policy_config(policy_config_path: Path) -> dict[str, Any]:
    return load_yaml(policy_config_path)


def _config_hash(*payloads: dict[str, Any]) -> str:
    blob = json.dumps(payloads, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _episode_eval_dir(run_root: Path, episode_id: str) -> Path:
    return ensure_dir(run_root / "episodes" / episode_id)


def _write_episode_eval_artifact(run_root: Path, episode_result: dict[str, Any]) -> dict[str, str]:
    episode_id = str(episode_result["episode_id"])
    episode_root = _episode_eval_dir(run_root, episode_id)
    summary_path = dump_json(episode_root / "evaluation.json", episode_result)
    return {
        "evaluation_json": str(summary_path),
        "episode_run_root": str(episode_root),
    }


def _build_episode_results(episodes: list[dict[str, Any]], policy_config: dict[str, Any]) -> list[dict[str, Any]]:
    adapter = load_policy_adapter(policy_config)
    results: list[dict[str, Any]] = []
    for index, episode in enumerate(episodes):
        adapter_result = adapter.evaluate_episode(episode, index)

        result = dict(episode)
        result.update(
            {
                "status": "success" if adapter_result.success else "failure",
                "success": adapter_result.success,
                "completion_ratio": round(adapter_result.completion_ratio, 4),
                "action_latency_ms": adapter_result.action_latency_ms,
                "predicted_failure_tags": adapter_result.predicted_failure_tags,
                "adapter_metadata": adapter_result.adapter_metadata,
                "episode_source_artifact_root": episode.get("artifact_root"),
            }
        )
        results.append(result)

    return results


def _compute_metrics(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(episodes)
    success_count = sum(1 for episode in episodes if episode.get("success"))
    completion_values = [float(episode.get("completion_ratio", 0.0)) for episode in episodes]
    length_values = [int(episode.get("num_steps", 0)) for episode in episodes]
    latency_values = [int(episode.get("action_latency_ms", 0)) for episode in episodes]

    def _avg(values: list[float | int]) -> float:
        if not values:
            return 0.0
        return round(float(sum(values)) / float(len(values)), 4)

    return {
        "episode_count": count,
        "success_rate": round(success_count / count, 4) if count else 0.0,
        "episode_length": _avg(length_values),
        "completion_ratio": _avg(completion_values),
        "action_latency_ms": _avg(latency_values),
        "success_count": success_count,
        "failure_count": count - success_count,
    }


def run_evaluation(config_path: str | Path) -> EvalResult:
    """Run one config-driven evaluation over normalized dataset artifacts."""
    config_file = resolve_repo_path(config_path)
    config = load_yaml(config_file)

    dataset_manifest = _load_dataset_manifest(resolve_repo_path(config["dataset_config"]))
    policy_config = _load_policy_config(resolve_repo_path(config["policy_config"]))
    run_root = resolve_repo_path(config["output_root"])
    ensure_dir(run_root)

    episode_records = dataset_manifest.get("episodes", [])
    if not isinstance(episode_records, list):
        raise ValueError("Dataset manifest must contain a list under 'episodes'.")

    evaluated_episodes = _build_episode_results(episode_records, policy_config)
    for episode_result in evaluated_episodes:
        episode_result["run_artifacts"] = _write_episode_eval_artifact(run_root, episode_result)
    metrics = _compute_metrics(evaluated_episodes)
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    config_hash = _config_hash(config, policy_config, dataset_manifest)

    metrics_path = dump_json(run_root / "metrics.json", metrics)
    run_manifest = RunRecord(
        run_name=str(config.get("run_name", run_root.name)),
        mode=str(config.get("mode", "benchmark")),
        dataset_id=str(dataset_manifest.get("dataset_id")),
        policy_name=str(policy_config.get("name", "unknown")),
        policy_adapter=str(policy_config.get("adapter", "unknown")),
        output_root=str(run_root),
        episode_count=len(evaluated_episodes),
        source_dataset_manifest=str(resolve_repo_path(config["dataset_config"])),
        source_policy_config=str(resolve_repo_path(config["policy_config"])),
        taxonomy_config=str(config["taxonomy_config"]) if config.get("taxonomy_config") else None,
        config_hash=config_hash,
        created_at=created_at,
        artifact_root=str(run_root),
        metrics_ref=str(metrics_path),
        status="completed",
    )
    run_manifest_path = dump_json(run_root / "run.json", run_manifest.model_dump(mode="json"))
    episodes_path = dump_jsonl(run_root / "episodes.jsonl", evaluated_episodes)
    dump_json(run_root / "config_snapshot.json", config)
    register_run(
        run_name=run_manifest.run_name,
        dataset_id=run_manifest.dataset_id,
        mode=run_manifest.mode,
        policy_name=run_manifest.policy_name,
        policy_adapter=run_manifest.policy_adapter,
        output_root=str(run_root),
        episode_count=len(evaluated_episodes),
        metrics_path=str(metrics_path),
        report_path=str(run_root / "report.md") if (run_root / "report.md").exists() else None,
    )

    return EvalResult(
        run_root=run_root,
        run_manifest_path=run_manifest_path,
        metrics_path=metrics_path,
        episodes_path=episodes_path,
        metrics=metrics,
        episode_count=len(evaluated_episodes),
    )


def compare_runs(run_root_a: str | Path, run_root_b: str | Path) -> dict[str, Any]:
    """Compare aggregate metrics for two completed runs."""
    root_a = resolve_repo_path(run_root_a)
    root_b = resolve_repo_path(run_root_b)
    metrics_a = load_json(root_a / "metrics.json")
    metrics_b = load_json(root_b / "metrics.json")

    delta = {
        key: round(float(metrics_b.get(key, 0.0)) - float(metrics_a.get(key, 0.0)), 4)
        for key in ("success_rate", "episode_length", "completion_ratio", "action_latency_ms")
    }
    return {
        "baseline_run": str(root_a),
        "candidate_run": str(root_b),
        "baseline_metrics": metrics_a,
        "candidate_metrics": metrics_b,
        "delta": delta,
    }
