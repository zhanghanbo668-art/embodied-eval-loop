"""Replay artifact generation for the embodied evaluation stack MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packages.common.config import resolve_repo_path
from packages.common.io import dump_json, ensure_dir, load_json, load_jsonl


def _load_episode_bundle(episode: dict[str, Any]) -> dict[str, Any]:
    artifact_root = episode.get("episode_source_artifact_root") or episode.get("artifact_root")
    if not artifact_root:
        return {}
    root = Path(artifact_root)
    if not root.is_absolute():
        root = resolve_repo_path(root)
    if not root.exists():
        return {}

    payload: dict[str, Any] = {}
    for key, rel_path in (
        ("episode", "episode.json"),
        ("replay_stub", "replay_stub.json"),
        ("events", "events.jsonl"),
        ("plan_trace", "plan_trace.jsonl"),
    ):
        target = root / rel_path
        if not target.exists():
            continue
        if target.suffix == ".jsonl":
            payload[key] = load_jsonl(target)
        else:
            payload[key] = load_json(target)

    action_ref = episode.get("action_ref") or {}
    state_ref = episode.get("state_ref") or {}
    observation_refs = episode.get("observation_refs", [])

    if isinstance(action_ref, dict) and action_ref.get("path"):
        target = root / action_ref["path"]
        if target.exists():
            payload["actions"] = load_json(target)
    if isinstance(state_ref, dict) and state_ref.get("path"):
        target = root / state_ref["path"]
        if target.exists():
            payload["states"] = load_json(target)
    if isinstance(observation_refs, list):
        observations: dict[str, Any] = {}
        for ref in observation_refs:
            if not isinstance(ref, dict) or not ref.get("path"):
                continue
            target = root / str(ref["path"])
            if target.exists():
                stream_name = str(ref.get("description") or Path(str(ref["path"])).stem)
                observations[stream_name] = load_json(target)
        if observations:
            payload["observations"] = observations
    return payload


def _keyframes_from_events(events: list[dict[str, Any]], top_k: int = 3) -> list[dict[str, Any]]:
    if not events:
        return []
    if len(events) <= top_k:
        return events
    indices = sorted({0, max(0, len(events) // 2), len(events) - 1})
    return [events[index] for index in indices[:top_k]]


def _action_preview(actions: list[dict[str, Any]]) -> list[str]:
    return [str(action.get("action", "unknown")) for action in actions[:6]]


def build_replay_artifacts(run_root: str | Path, top_k: int = 10) -> dict[str, Any]:
    """Create inspectable replay summaries for the top-K ranked failures."""
    root = resolve_repo_path(run_root)
    episodes = load_jsonl(root / "episodes.jsonl")
    failures = [episode for episode in episodes if not episode.get("success", False)]
    failures = sorted(
        failures,
        key=lambda episode: (
            float(episode.get("completion_ratio", 0.0)),
            int(episode.get("action_latency_ms", 0)),
        ),
    )[:top_k]

    replay_root = ensure_dir(root / "replays")
    exported: list[dict[str, Any]] = []
    for episode in failures:
        bundle = _load_episode_bundle(episode)
        event_timeline = bundle.get("events", [])
        action_trace = bundle.get("actions", [])
        state_trace = bundle.get("states", [])
        plan_trace = bundle.get("plan_trace", [])
        episode_root = ensure_dir(replay_root / str(episode["episode_id"]))
        summary = {
            "episode_id": episode["episode_id"],
            "task_id": episode.get("task_id"),
            "instruction": episode.get("instruction"),
            "status": episode.get("status"),
            "completion_ratio": episode.get("completion_ratio"),
            "action_latency_ms": episode.get("action_latency_ms"),
            "predicted_failure_tags": episode.get("predicted_failure_tags", []),
            "source_episode_artifact_root": episode.get("episode_source_artifact_root") or episode.get("artifact_root"),
            "run_episode_artifact_root": str(root / "episodes" / str(episode["episode_id"])),
            "event_count": len(event_timeline),
            "keyframes": _keyframes_from_events(event_timeline),
            "action_preview": _action_preview(action_trace),
            "final_progress": state_trace[-1]["progress"] if state_trace else None,
            "plan_segments": [segment.get("label", "unknown") for segment in plan_trace if isinstance(segment, dict)],
        }
        dump_json(episode_root / "summary.json", summary)
        markdown = _render_markdown(summary)
        (episode_root / "summary.md").write_text(markdown, encoding="utf-8")
        exported.append(
            {
                "episode_id": episode["episode_id"],
                "summary_json": str(episode_root / "summary.json"),
                "summary_md": str(episode_root / "summary.md"),
            }
        )

    index = {
        "run_root": str(root),
        "replay_count": len(exported),
        "episodes": exported,
    }
    dump_json(replay_root / "index.json", index)
    return index


def _render_markdown(summary: dict[str, Any]) -> str:
    tags = ", ".join(summary.get("predicted_failure_tags", [])) or "none"
    keyframes = summary.get("keyframes", [])
    keyframe_lines = (
        [
            f"- t={item.get('timestamp_ms', 'n/a')} | phase=`{item.get('phase', item.get('type', 'unknown'))}` | action=`{item.get('action', 'n/a')}` | progress=`{item.get('progress', 'n/a')}`"
            for item in keyframes
            if isinstance(item, dict)
        ]
        or ["- none"]
    )
    plan_segments = ", ".join(summary.get("plan_segments", [])) or "none"
    action_preview = ", ".join(summary.get("action_preview", [])) or "none"
    return "\n".join(
        [
            f"# Replay Summary: {summary['episode_id']}",
            "",
            f"- Task: `{summary.get('task_id', 'unknown')}`",
            f"- Status: `{summary.get('status', 'unknown')}`",
            f"- Completion ratio: `{summary.get('completion_ratio', 0.0)}`",
            f"- Action latency ms: `{summary.get('action_latency_ms', 0)}`",
            f"- Failure tags: `{tags}`",
            f"- Event count: `{summary.get('event_count', 0)}`",
            f"- Final progress: `{summary.get('final_progress', 'n/a')}`",
            f"- Plan segments: `{plan_segments}`",
            f"- Action preview: `{action_preview}`",
            f"- Source episode root: `{summary.get('source_episode_artifact_root', 'n/a')}`",
            f"- Run episode root: `{summary.get('run_episode_artifact_root', 'n/a')}`",
            "",
            "## Instruction",
            "",
            str(summary.get("instruction", "")),
            "",
            "## Keyframes",
            "",
            *keyframe_lines,
        ]
    )
