"""Dataset card generation for normalized embodied datasets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Template

from packages.common.config import display_path, resolve_repo_path
from packages.common.io import dump_json, load_json

DATASET_CARD_TEMPLATE = Template(
    """# Dataset Card: {{ dataset_id }}

## Summary

- Source type: `{{ source_type }}`
- Source root: `{{ source_root }}`
- Output root: `{{ output_root }}`
- Episode count: `{{ episode_count }}`
- Reader: `{{ reader }}`
- Validation status: `{{ validation_status }}`
- Quality status: `{{ quality_status }}`

## Tasks

{% if task_ids %}
{% for task_id in task_ids -%}
- `{{ task_id }}`
{% endfor %}
{% else %}
- No tasks recorded.
{% endif %}

## Modalities and Streams

{% if stream_rows %}
{% for row in stream_rows -%}
- `{{ row.name }}`: total_samples=`{{ row.total_samples }}` avg_per_episode=`{{ row.avg_per_episode }}` required=`{{ row.required }}`
{% endfor %}
{% else %}
- No stream summary available.
{% endif %}

## Quality

- Pass count: `{{ pass_count }}`
- Fail count: `{{ fail_count }}`
- Issue count: `{{ issue_count }}`
- Max stream gap ms: `{{ max_gap_ms }}`

## Export Views

{% if export_views %}
{% for row in export_views -%}
- `{{ row.name }}`: `{{ row.path }}`
{% endfor %}
{% else %}
- No export views found.
{% endif %}

## Split Views

{% if split_summary %}
- Ratio: `{{ split_summary.split_ratio }}`
- Seed: `{{ split_summary.split_seed }}`
- Train episodes: `{{ split_summary.split_counts.train }}`
- Eval episodes: `{{ split_summary.split_counts.eval }}`
{% if split_summary.warnings %}
{% for warning in split_summary.warnings -%}
- Warning: {{ warning }}
{% endfor %}
{% endif %}
{% else %}
- No split manifest found.
{% endif %}
"""
)


@dataclass(slots=True)
class DatasetCardResult:
    """Summary for one generated dataset card."""

    dataset_id: str
    dataset_root: Path
    markdown_path: Path
    json_path: Path


def build_dataset_card(dataset_root: str | Path) -> DatasetCardResult:
    """Generate a dataset card from normalized dataset artifacts."""
    root = resolve_repo_path(dataset_root)
    manifest = load_json(root / "dataset_manifest.json")
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid dataset manifest: {root / 'dataset_manifest.json'}")

    dataset_id = str(manifest.get("dataset_id", root.name))
    episodes = manifest.get("episodes", []) if isinstance(manifest.get("episodes"), list) else []
    validation = _load_optional_json(root / "validation_report.json")
    quality = _load_optional_json(root / "quality_report.json")
    exports = _discover_exports(root / "exports")
    split_summary = _load_optional_json(root / "exports" / "split_jsonl" / "split_manifest.json")

    stream_rows = _stream_rows(episodes, quality)
    payload = {
        "dataset_id": dataset_id,
        "source_type": str(manifest.get("source_type", "unknown")),
        "source_root": display_path(manifest.get("source_root", "")),
        "output_root": display_path(root),
        "episode_count": int(manifest.get("episode_count", len(episodes))),
        "task_ids": sorted({str(episode.get("task_id", "unknown_task")) for episode in episodes if isinstance(episode, dict)}),
        "reader": str(manifest.get("metadata", {}).get("config", {}).get("reader", "n/a")),
        "validation_status": str(validation.get("status", "missing")) if isinstance(validation, dict) else "missing",
        "quality_status": "pass" if int((quality or {}).get("fail_count", 0)) == 0 else "fail",
        "pass_count": int((quality or {}).get("pass_count", 0)),
        "fail_count": int((quality or {}).get("fail_count", 0)),
        "issue_count": int((quality or {}).get("issue_count", 0)),
        "max_gap_ms": _max_gap_ms(quality),
        "stream_rows": stream_rows,
        "export_views": exports,
        "split_summary": split_summary if isinstance(split_summary, dict) else None,
    }

    markdown_path = root / "dataset_card.md"
    markdown_path.write_text(DATASET_CARD_TEMPLATE.render(**payload), encoding="utf-8")
    json_path = dump_json(root / "dataset_card.json", payload)
    return DatasetCardResult(
        dataset_id=dataset_id,
        dataset_root=root,
        markdown_path=markdown_path,
        json_path=json_path,
    )


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = load_json(path)
    return payload if isinstance(payload, dict) else None


def _discover_exports(exports_root: Path) -> list[dict[str, str]]:
    if not exports_root.exists():
        return []
    rows: list[dict[str, str]] = []
    for child in sorted(exports_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        manifest = child / "export_manifest.json"
        split_manifest = child / "split_manifest.json"
        if manifest.exists():
            rows.append({"name": child.name, "path": display_path(manifest)})
        elif split_manifest.exists():
            rows.append({"name": child.name, "path": display_path(split_manifest)})
    return rows


def _stream_rows(episodes: list[Any], quality: dict[str, Any] | None) -> list[dict[str, Any]]:
    required_map: dict[str, bool] = {}
    for episode in episodes:
        if not isinstance(episode, dict):
            continue
        topics = episode.get("metadata", {}).get("topics", {}) if isinstance(episode.get("metadata"), dict) else {}
        if not isinstance(topics, dict):
            continue
        for alias, info in topics.items():
            if isinstance(info, dict):
                required_map[str(alias)] = bool(info.get("required", False))

    totals: dict[str, int] = {}
    quality_episodes = quality.get("episodes", []) if isinstance(quality, dict) else []
    if isinstance(quality_episodes, list):
        for item in quality_episodes:
            if not isinstance(item, dict):
                continue
            counts = item.get("stream_counts", {})
            if not isinstance(counts, dict):
                continue
            for alias, count in counts.items():
                totals[str(alias)] = totals.get(str(alias), 0) + int(count)

    episode_count = len(quality_episodes) if isinstance(quality_episodes, list) and quality_episodes else max(len(episodes), 1)
    rows: list[dict[str, Any]] = []
    for alias in sorted(set(totals) | set(required_map)):
        total = totals.get(alias, 0)
        rows.append(
            {
                "name": alias,
                "total_samples": total,
                "avg_per_episode": round(total / episode_count, 4) if episode_count else 0.0,
                "required": required_map.get(alias, False),
            }
        )
    return rows


def _max_gap_ms(quality: dict[str, Any] | None) -> int:
    quality_episodes = quality.get("episodes", []) if isinstance(quality, dict) else []
    max_gap = 0
    if isinstance(quality_episodes, list):
        for item in quality_episodes:
            if isinstance(item, dict):
                max_gap = max(max_gap, int(item.get("max_gap_ms", 0)))
    return max_gap
