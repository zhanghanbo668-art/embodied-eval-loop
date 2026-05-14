"""Run analysis for the embodied evaluation stack MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from packages.common.config import resolve_repo_path
from packages.common.io import dump_json, dump_jsonl, load_json, load_jsonl, load_yaml
from packages.schemas.models import FailureTag


class AnalysisResult(BaseModel):
    """Summary of one analysis pass."""

    run_root: str
    failure_count: int
    ranked_episode_ids: list[str] = Field(default_factory=list)
    failure_tags_path: str
    analysis_path: str


def _load_taxonomy(config_path: str | Path | None) -> dict[str, Any]:
    if not config_path:
        return {"tags": []}
    return load_yaml(resolve_repo_path(config_path))


def _rank_key(episode: dict[str, Any]) -> tuple[float, int]:
    return (
        float(episode.get("completion_ratio", 0.0)),
        int(episode.get("action_latency_ms", 0)),
    )


def _infer_tag(episode: dict[str, Any], taxonomy: dict[str, Any]) -> str:
    predicted = episode.get("predicted_failure_tags", [])
    if isinstance(predicted, list) and predicted:
        if predicted[0] != "ok":
            return str(predicted[0])
    available_tags = taxonomy.get("tags", [])
    if not episode.get("success", False):
        if isinstance(available_tags, list) and available_tags:
            return str(available_tags[-1])
        return "environment_or_data_issue"
    return "ok"


def analyze_run(run_root: str | Path, taxonomy_config_path: str | Path | None = None) -> AnalysisResult:
    """Analyze one completed run and emit ranked failures plus failure tags."""
    root = resolve_repo_path(run_root)
    episodes = load_jsonl(root / "episodes.jsonl")
    run_manifest = load_json(root / "run.json")
    taxonomy = _load_taxonomy(taxonomy_config_path)

    failures = [episode for episode in episodes if not episode.get("success", False)]
    ranked_failures = sorted(failures, key=_rank_key)

    tag_models: list[FailureTag] = []
    for episode in ranked_failures:
        tag = _infer_tag(episode, taxonomy)
        tag_models.append(
            FailureTag(
                run_id=str(run_manifest.get("run_name", root.name)),
                episode_id=str(episode["episode_id"]),
                tag=tag,
                confidence=0.8 if tag != "ok" else 1.0,
                evidence={
                    "completion_ratio": episode.get("completion_ratio"),
                    "action_latency_ms": episode.get("action_latency_ms"),
                    "task_id": episode.get("task_id"),
                },
            )
        )

    failure_tags_path = dump_jsonl(
        root / "failure_tags.jsonl",
        [tag.model_dump(mode="json") for tag in tag_models],
    )
    analysis_payload = {
        "run_name": run_manifest.get("run_name", root.name),
        "failure_count": len(ranked_failures),
        "ranked_episode_ids": [episode["episode_id"] for episode in ranked_failures],
        "by_tag": _count_tags(tag_models),
    }
    analysis_path = dump_json(root / "analysis.json", analysis_payload)

    return AnalysisResult(
        run_root=str(root),
        failure_count=len(ranked_failures),
        ranked_episode_ids=[episode["episode_id"] for episode in ranked_failures],
        failure_tags_path=str(failure_tags_path),
        analysis_path=str(analysis_path),
    )


def _count_tags(tag_models: list[FailureTag]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for tag in tag_models:
        counts[tag.tag] = counts.get(tag.tag, 0) + 1
    return counts
