"""Helpers for enriching reporting outputs with replay artifact context."""

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

from packages.common.config import display_path
from packages.common.io import load_json


def format_tags(tags: list[str] | None) -> str:
    """Render failure tags in a compact human-readable form."""
    values = [str(tag) for tag in tags or [] if str(tag).strip()]
    return ", ".join(values) if values else "none"


def format_value(value: Any, default: str = "n/a") -> str:
    """Normalize optional values for report rendering."""
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def html_escape(value: Any) -> str:
    """Escape values for inline HTML output."""
    return html.escape(format_value(value, default=""))


def artifact_href(report_path: Path, artifact_path: str | Path | None) -> str | None:
    """Return a report-relative link target when possible."""
    if artifact_path in (None, ""):
        return None
    target = Path(artifact_path)
    try:
        relative = os.path.relpath(str(target), str(report_path.parent))
        return Path(relative).as_posix()
    except ValueError:
        return target.as_posix()
    except OSError:
        return target.as_posix()


def load_replay_lookup(run_root: Path, report_path: Path) -> dict[str, dict[str, str]]:
    """Load replay artifact paths keyed by episode ID."""
    replay_index_path = run_root / "replays" / "index.json"
    if not replay_index_path.exists():
        return {}

    replay_index = load_json(replay_index_path)
    episodes = replay_index.get("episodes", [])
    if not isinstance(episodes, list):
        return {}

    lookup: dict[str, dict[str, str]] = {}
    for item in episodes:
        if not isinstance(item, dict):
            continue
        episode_id = format_value(item.get("episode_id"), default="")
        if not episode_id:
            continue
        summary_json = item.get("summary_json")
        summary_md = item.get("summary_md")
        lookup[episode_id] = {
            "summary_json": display_path(summary_json) if summary_json else "n/a",
            "summary_md": display_path(summary_md) if summary_md else "n/a",
            "summary_json_href": artifact_href(report_path, summary_json) or "",
            "summary_md_href": artifact_href(report_path, summary_md) or "",
        }
    return lookup


def enrich_failure(
    episode: dict[str, Any],
    replay_lookup: dict[str, dict[str, str]],
    report_path: Path,
) -> dict[str, Any]:
    """Attach replay artifact metadata to a failure row."""
    enriched = dict(episode)
    replay = replay_lookup.get(format_value(episode.get("episode_id"), default=""), {})
    run_artifacts = episode.get("run_artifacts", {}) if isinstance(episode.get("run_artifacts"), dict) else {}
    enriched["failure_tags_display"] = format_tags(episode.get("predicted_failure_tags"))
    enriched["instruction_display"] = format_value(episode.get("instruction"))
    enriched["status_display"] = format_value(episode.get("status"))
    enriched["replay_summary_md"] = replay.get("summary_md", "n/a")
    enriched["replay_summary_json"] = replay.get("summary_json", "n/a")
    enriched["replay_summary_md_href"] = replay.get("summary_md_href", "")
    enriched["replay_summary_json_href"] = replay.get("summary_json_href", "")
    enriched["evaluation_json_display"] = format_value(run_artifacts.get("evaluation_json"))
    enriched["evaluation_json_href"] = artifact_href(report_path, run_artifacts.get("evaluation_json")) or ""
    return enriched
