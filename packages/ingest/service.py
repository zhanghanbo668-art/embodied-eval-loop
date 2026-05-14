"""Dataset ingest implementation for the software-only embodied eval stack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from packages.adapters_rosbags import RosbagReader, TimestampedMessage, load_rosbag_reader
from packages.common.config import display_path, resolve_repo_path
from packages.common.io import dump_json, dump_jsonl, ensure_dir, load_json, load_yaml
from packages.registry.service import register_dataset
from packages.schemas.models import ArtifactRef, DatasetManifest, EpisodeRecord, IngestResult

ACTION_TEMPLATES: dict[str, list[str]] = {
    "pick_place": ["reach", "align", "grasp", "lift", "transfer", "place", "settle"],
    "drawer_open": ["reach", "hook", "pull", "stabilize"],
    "soft_grasp_adjustment": ["sense", "approach", "pressurize", "stabilize"],
    "soft_reach_alignment": ["sense", "align", "micro_adjust", "hold"],
}


def load_dataset_config(config_path: str | Path) -> dict[str, Any]:
    """Load a dataset YAML config from disk."""
    return load_yaml(resolve_repo_path(config_path))


def _source_root_from_config(config: dict[str, Any]) -> Path:
    root = config.get("root")
    if not root:
        raise ValueError("Dataset config must define 'root'.")
    return resolve_repo_path(root)


def _output_root(dataset_id: str) -> Path:
    return resolve_repo_path(f"outputs/datasets/{dataset_id}")


def _build_episode_dir(root: Path, episode_id: str) -> Path:
    return ensure_dir(root / "episodes" / episode_id)


def _step_period_ms(source_type: str) -> int:
    if source_type == "rosbag2":
        return 125
    return 100


def _episode_window_ms(episode_index: int, step_count: int, source_type: str) -> tuple[int, int]:
    step_period_ms = _step_period_ms(source_type)
    start_time_ms = 1_000_000 + (episode_index * 100_000)
    end_time_ms = start_time_ms + max(step_count - 1, 0) * step_period_ms
    return start_time_ms, end_time_ms


def _phase_name(step: int, step_count: int) -> str:
    if step_count <= 1:
        return "complete"
    progress = step / max(step_count - 1, 1)
    if progress < 0.2:
        return "observe"
    if progress < 0.45:
        return "approach"
    if progress < 0.7:
        return "execute"
    if progress < 0.95:
        return "stabilize"
    return "complete"


def _action_tokens(episode: EpisodeRecord) -> list[str]:
    template = ACTION_TEMPLATES.get(episode.task_id)
    if template:
        return template
    verbs = [token.strip(".,") for token in episode.instruction.lower().split() if len(token) > 3]
    if verbs:
        return verbs[:4]
    return ["observe", "plan", "act", "stabilize"]


def _build_action_trace(episode: EpisodeRecord) -> list[dict[str, Any]]:
    step_period_ms = _step_period_ms(episode.source_type)
    tokens = _action_tokens(episode)
    trace: list[dict[str, Any]] = []
    for step in range(max(episode.num_steps, 1)):
        trace.append(
            {
                "step": step,
                "timestamp_ms": episode.start_time_ms + (step * step_period_ms),
                "phase": _phase_name(step, max(episode.num_steps, 1)),
                "action": tokens[step % len(tokens)],
            }
        )
    return trace


def _build_state_trace(episode: EpisodeRecord) -> list[dict[str, Any]]:
    step_period_ms = _step_period_ms(episode.source_type)
    target_completion = float(episode.metadata.get("reference_completion_ratio", 1.0))
    trace: list[dict[str, Any]] = []
    for step in range(max(episode.num_steps, 1)):
        progress = round(min(target_completion, ((step + 1) / max(episode.num_steps, 1)) * target_completion), 4)
        trace.append(
            {
                "step": step,
                "timestamp_ms": episode.start_time_ms + (step * step_period_ms),
                "phase": _phase_name(step, max(episode.num_steps, 1)),
                "progress": progress,
                "is_terminal": step == max(episode.num_steps, 1) - 1,
            }
        )
    return trace


def _build_observation_trace(stream_name: str, episode: EpisodeRecord) -> list[dict[str, Any]]:
    step_period_ms = _step_period_ms(episode.source_type)
    rows: list[dict[str, Any]] = []
    for step in range(max(episode.num_steps, 1)):
        rows.append(
            {
                "step": step,
                "timestamp_ms": episode.start_time_ms + (step * step_period_ms),
                "stream": stream_name,
                "frame_id": f"{episode.episode_id}_{stream_name}_{step:04d}",
                "phase": _phase_name(step, max(episode.num_steps, 1)),
            }
        )
    return rows


def _build_plan_trace(episode: EpisodeRecord) -> list[dict[str, Any]]:
    steps = max(episode.num_steps, 1)
    split_a = max(1, steps // 3)
    split_b = max(split_a + 1, (2 * steps) // 3)
    plan_steps = [
        ("parse_instruction", 0, split_a - 1),
        ("execute_skill", split_a, split_b - 1),
        ("stabilize_outcome", split_b, steps - 1),
    ]
    return [
        {
            "segment": index,
            "label": label,
            "start_step": start_step,
            "end_step": end_step,
            "instruction": episode.instruction,
            "task_id": episode.task_id,
        }
        for index, (label, start_step, end_step) in enumerate(plan_steps)
        if start_step <= end_step
    ]


def _build_event_timeline(
    episode: EpisodeRecord,
    action_trace: list[dict[str, Any]],
    state_trace: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "timestamp_ms": episode.start_time_ms,
            "type": "episode_start",
            "episode_id": episode.episode_id,
            "task_id": episode.task_id,
            "instruction": episode.instruction,
        }
    ]
    for action_row, state_row in zip(action_trace, state_trace):
        events.append(
            {
                "timestamp_ms": action_row["timestamp_ms"],
                "type": "step",
                "step": action_row["step"],
                "phase": action_row["phase"],
                "action": action_row["action"],
                "progress": state_row["progress"],
            }
        )
    events.append(
        {
            "timestamp_ms": episode.end_time_ms,
            "type": "episode_end",
            "episode_id": episode.episode_id,
            "success_reference": bool(episode.metadata.get("reference_success", True)),
            "completion_reference": float(episode.metadata.get("reference_completion_ratio", 1.0)),
        }
    )
    return events


def _normalize_libero(config: dict[str, Any]) -> list[EpisodeRecord]:
    source_root = _source_root_from_config(config)
    episodes_file = source_root / "episodes.json"
    if not episodes_file.exists():
        raise FileNotFoundError(f"Expected LIBERO sample file at {episodes_file}")
    raw_episodes = load_json(episodes_file)
    if not isinstance(raw_episodes, list):
        raise ValueError(f"Expected a list of episodes in {episodes_file}")

    dataset_id = str(config["output_dataset_id"])
    instruction_field = str(config.get("instruction_field", "language"))
    task_field = str(config.get("task_field", "task"))
    episode_id_field = str(config.get("episode_id_field", "episode_id"))
    observation_streams = list(config.get("observation_streams", []))
    action_field = str(config.get("action_field", "action"))

    episodes: list[EpisodeRecord] = []
    for raw_index, raw in enumerate(raw_episodes):
        if not isinstance(raw, dict):
            continue
        episode_id = str(raw.get(episode_id_field, f"{dataset_id}_{len(episodes):04d}"))
        start_time_ms, end_time_ms = _episode_window_ms(raw_index, int(raw.get("num_steps", 0)), "libero")
        refs = [
            ArtifactRef(kind="observation_stream", path=f"streams/{name}.json", description=name)
            for name in observation_streams
        ]
        episodes.append(
            EpisodeRecord(
                episode_id=episode_id,
                dataset_id=dataset_id,
                task_id=str(raw.get(task_field, "unknown_task")),
                instruction=str(raw.get(instruction_field, "")),
                source_type="libero",
                source_uri=str(episodes_file),
                num_steps=int(raw.get("num_steps", 0)),
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                observation_refs=refs,
                action_ref=ArtifactRef(kind="action_stream", path=f"streams/{action_field}.json"),
                state_ref=ArtifactRef(kind="state_stream", path="streams/state.json"),
                events_ref=ArtifactRef(kind="event_timeline", path="events.jsonl"),
                plan_trace_ref=ArtifactRef(kind="plan_trace", path="plan_trace.jsonl"),
                metadata={
                    "reference_success": bool(raw.get("reference_success", True)),
                    "reference_completion_ratio": float(raw.get("reference_completion_ratio", 1.0)),
                    "reference_action_latency_ms": int(raw.get("reference_action_latency_ms", 0)),
                    "split": config.get("split"),
                    "source_episode_index": raw_index,
                    "normalization_source": "metadata_scaffold",
                },
            )
        )
    return episodes


def _normalize_rosbag(config: dict[str, Any], reader: RosbagReader | None = None) -> list[EpisodeRecord]:
    source_root = _source_root_from_config(config)
    reader = reader or load_rosbag_reader(source_root, config)
    dataset_id = str(config["output_dataset_id"])
    topics = {info.alias: info for info in reader.topics()}
    observation_streams = [
        alias for alias in topics.keys() if alias not in {"action", "instruction", "state", "episode_marker"}
    ]

    episodes: list[EpisodeRecord] = []
    for source_episode in reader.episodes():
        refs = [
            ArtifactRef(
                kind="ros_topic",
                path=f"streams/{topic_name}.json",
                description=topics[topic_name].name,
            )
            for topic_name in observation_streams
        ]
        episodes.append(
            EpisodeRecord(
                episode_id=source_episode.episode_id,
                dataset_id=dataset_id,
                task_id=source_episode.task_id,
                instruction=source_episode.instruction,
                source_type="rosbag2",
                source_uri=str(source_root),
                num_steps=source_episode.num_steps,
                start_time_ms=source_episode.start_time_ms,
                end_time_ms=source_episode.end_time_ms,
                observation_refs=refs,
                action_ref=ArtifactRef(
                    kind="ros_topic",
                    path="streams/action.json",
                    description=topics.get("action").name if topics.get("action") else "/unknown/action",
                ),
                state_ref=ArtifactRef(
                    kind="ros_topic",
                    path="streams/state.json",
                    description=topics.get("state").name if topics.get("state") else "/unknown/state",
                ),
                events_ref=ArtifactRef(kind="event_timeline", path="events.jsonl"),
                plan_trace_ref=ArtifactRef(kind="plan_trace", path="plan_trace.jsonl"),
                metadata={
                    **source_episode.metadata,
                    "sync": config.get("sync", {}),
                    "normalization_source": "rosbag_reader",
                    "reader": config.get("reader", "metadata"),
                    "topics": {
                        alias: {
                            "name": info.name,
                            "message_type": info.message_type,
                            "required": info.required,
                        }
                        for alias, info in topics.items()
                    },
                },
            )
        )
    return episodes


def _nearest_message(
    reference_timestamp_ms: int,
    messages: list[TimestampedMessage],
    tolerance_ms: int,
) -> tuple[TimestampedMessage | None, int | None]:
    if not messages:
        return None, None
    nearest = min(messages, key=lambda message: abs(message.timestamp_ms - reference_timestamp_ms))
    delta_ms = abs(nearest.timestamp_ms - reference_timestamp_ms)
    if delta_ms > tolerance_ms:
        return None, delta_ms
    return nearest, delta_ms


def _aligned_ros_streams(
    episode: EpisodeRecord,
    reader: RosbagReader,
    config: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    sync_config = config.get("sync", {})
    tolerance_ms = int(sync_config.get("tolerance_ms", 50))
    reference_alias = str(sync_config.get("reference_stream", "state"))
    topics = {info.alias: info for info in reader.topics()}
    required_aliases = {str(alias) for alias in config.get("required_topics", ["state", "action"])}
    stream_messages = {
        alias: list(reader.messages(alias, episode.episode_id))
        for alias in topics.keys()
        if alias != "episode_marker"
    }
    reference_messages = stream_messages.get(reference_alias) or stream_messages.get("state") or []

    issues: list[dict[str, Any]] = []
    for alias in required_aliases:
        if alias not in topics:
            issues.append({"severity": "error", "type": "missing_required_topic", "topic": alias})
        elif not stream_messages.get(alias):
            issues.append({"severity": "error", "type": "empty_required_topic", "topic": alias})

    aligned: dict[str, list[dict[str, Any]]] = {alias: [] for alias in stream_messages.keys()}
    if not reference_messages:
        issues.append({"severity": "error", "type": "missing_reference_stream", "topic": reference_alias})
        return aligned, _quality_payload(episode, stream_messages, issues, tolerance_ms, reference_alias)

    for step, reference in enumerate(reference_messages):
        for alias, messages in stream_messages.items():
            match, delta_ms = _nearest_message(reference.timestamp_ms, messages, tolerance_ms)
            if match is None:
                issues.append(
                    {
                        "severity": "warning",
                        "type": "stale_or_missing_sample",
                        "topic": alias,
                        "step": step,
                        "reference_timestamp_ms": reference.timestamp_ms,
                        "nearest_delta_ms": delta_ms,
                    }
                )
                continue
            row = {
                "step": step,
                "timestamp_ms": match.timestamp_ms,
                "aligned_to_ms": reference.timestamp_ms,
                "delta_ms": delta_ms,
                "topic": alias,
                **match.payload,
            }
            aligned[alias].append(row)

    return aligned, _quality_payload(episode, stream_messages, issues, tolerance_ms, reference_alias, aligned)


def _quality_payload(
    episode: EpisodeRecord,
    stream_messages: dict[str, list[TimestampedMessage]],
    issues: list[dict[str, Any]],
    tolerance_ms: int,
    reference_alias: str,
    aligned: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    aligned = aligned or {}
    stream_counts = {alias: len(messages) for alias, messages in stream_messages.items()}
    aligned_counts = {alias: len(rows) for alias, rows in aligned.items()}
    max_gap_ms = 0
    for messages in stream_messages.values():
        ordered = sorted(messages, key=lambda message: message.timestamp_ms)
        gaps = [
            ordered[index + 1].timestamp_ms - ordered[index].timestamp_ms
            for index in range(len(ordered) - 1)
        ]
        if gaps:
            max_gap_ms = max(max_gap_ms, max(gaps))
    status = "pass" if not any(issue["severity"] == "error" for issue in issues) else "fail"
    return {
        "episode_id": episode.episode_id,
        "status": status,
        "reference_stream": reference_alias,
        "tolerance_ms": tolerance_ms,
        "stream_counts": stream_counts,
        "aligned_counts": aligned_counts,
        "max_gap_ms": max_gap_ms,
        "issues": issues,
    }


def _build_ros_event_timeline(
    episode: EpisodeRecord,
    action_trace: list[dict[str, Any]],
    state_trace: list[dict[str, Any]],
    quality: dict[str, Any],
) -> list[dict[str, Any]]:
    events = _build_event_timeline(episode, action_trace, state_trace)
    for issue in quality.get("issues", []):
        if not isinstance(issue, dict):
            continue
        events.append(
            {
                "timestamp_ms": issue.get("reference_timestamp_ms", episode.start_time_ms),
                "type": "quality_issue",
                "severity": issue.get("severity"),
                "issue_type": issue.get("type"),
                "topic": issue.get("topic"),
                "step": issue.get("step"),
            }
        )
    return sorted(events, key=lambda event: int(event.get("timestamp_ms", episode.start_time_ms)))


def _materialize_episode_artifacts(
    output_root: Path,
    episodes: list[EpisodeRecord],
    config: dict[str, Any] | None = None,
    rosbag_reader: RosbagReader | None = None,
) -> dict[str, Any] | None:
    dataset_quality: list[dict[str, Any]] = []
    for episode in episodes:
        episode_dir = _build_episode_dir(output_root, episode.episode_id)
        streams_dir = ensure_dir(episode_dir / "streams")
        episode.artifact_root = display_path(episode_dir)

        quality: dict[str, Any] | None = None
        aligned_streams: dict[str, list[dict[str, Any]]] = {}
        if episode.source_type == "rosbag2" and rosbag_reader is not None and config is not None:
            aligned_streams, quality = _aligned_ros_streams(episode, rosbag_reader, config)
            action_trace = _rows_to_action_trace(episode, aligned_streams.get("action", []))
            state_trace = _rows_to_state_trace(episode, aligned_streams.get("state", []))
            event_timeline = _build_ros_event_timeline(episode, action_trace, state_trace, quality)
        else:
            action_trace = _build_action_trace(episode)
            state_trace = _build_state_trace(episode)
            event_timeline = _build_event_timeline(episode, action_trace, state_trace)
        plan_trace = _build_plan_trace(episode)

        if episode.action_ref:
            dump_json(streams_dir / Path(episode.action_ref.path).name, action_trace)
        if episode.state_ref:
            dump_json(streams_dir / Path(episode.state_ref.path).name, state_trace)
        for ref in episode.observation_refs:
            stream_name = Path(ref.path).stem
            observation_trace = aligned_streams.get(stream_name) or _build_observation_trace(
                ref.description or ref.kind, episode
            )
            dump_json(streams_dir / Path(ref.path).name, observation_trace)
        if episode.events_ref:
            dump_jsonl(episode_dir / episode.events_ref.path, event_timeline)
        if episode.plan_trace_ref:
            dump_jsonl(episode_dir / episode.plan_trace_ref.path, plan_trace)
        if quality:
            dump_json(episode_dir / "quality.json", quality)
            dataset_quality.append(quality)
            episode.metadata["quality"] = {
                "status": quality["status"],
                "issue_count": len(quality.get("issues", [])),
                "quality_ref": "quality.json",
            }

        dump_json(episode_dir / "episode.json", episode.model_dump(mode="json"))
        dump_json(
            episode_dir / "replay_stub.json",
            {
                "episode_id": episode.episode_id,
                "task_id": episode.task_id,
                "instruction": episode.instruction,
                "num_steps": episode.num_steps,
                "source_type": episode.source_type,
                "artifact_root": episode.artifact_root,
                "events_ref": episode.events_ref.path if episode.events_ref else None,
                "plan_trace_ref": episode.plan_trace_ref.path if episode.plan_trace_ref else None,
                "quality_ref": "quality.json" if quality else None,
                "replay_command": f"python -m pipelines.replay --run <RUN_ROOT> --top-k 1",
            },
        )
    if dataset_quality:
        summary = {
            "episode_count": len(dataset_quality),
            "pass_count": sum(1 for item in dataset_quality if item.get("status") == "pass"),
            "fail_count": sum(1 for item in dataset_quality if item.get("status") == "fail"),
            "issue_count": sum(len(item.get("issues", [])) for item in dataset_quality),
            "episodes": dataset_quality,
        }
        dump_json(output_root / "quality_report.json", summary)
        return summary
    return None


def _rows_to_action_trace(episode: EpisodeRecord, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return _build_action_trace(episode)
    trace: list[dict[str, Any]] = []
    for row in rows:
        step = int(row.get("step", len(trace)))
        trace.append(
            {
                "step": step,
                "timestamp_ms": int(row.get("timestamp_ms", episode.start_time_ms)),
                "phase": _phase_name(step, max(episode.num_steps, 1)),
                "action": str(row.get("command", row.get("action", "unknown"))),
                "target_pressure": row.get("target_pressure"),
                "delta_ms": row.get("delta_ms"),
            }
        )
    return trace


def _rows_to_state_trace(episode: EpisodeRecord, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return _build_state_trace(episode)
    trace: list[dict[str, Any]] = []
    for row in rows:
        step = int(row.get("step", len(trace)))
        trace.append(
            {
                "step": step,
                "timestamp_ms": int(row.get("timestamp_ms", episode.start_time_ms)),
                "phase": _phase_name(step, max(episode.num_steps, 1)),
                "progress": float(row.get("progress", 0.0)),
                "stiffness": row.get("stiffness"),
                "contact": row.get("contact"),
                "delta_ms": row.get("delta_ms"),
                "is_terminal": step == max(episode.num_steps, 1) - 1,
            }
        )
    return trace


def ingest_dataset(config_path: str | Path) -> IngestResult:
    """Ingest one dataset config into normalized episode artifacts and a manifest."""
    config = load_dataset_config(config_path)
    dataset_id = str(config["output_dataset_id"])
    source_type = str(config.get("source_type", "unknown"))
    source_root = _source_root_from_config(config)
    output_root = _output_root(dataset_id)
    ensure_dir(output_root)
    rosbag_reader: RosbagReader | None = None

    if source_type == "libero":
        episodes = _normalize_libero(config)
    elif source_type == "rosbag2":
        rosbag_reader = load_rosbag_reader(source_root, config)
        episodes = _normalize_rosbag(config, rosbag_reader)
    else:
        raise ValueError(f"Unsupported source_type: {source_type}")

    quality_summary = _materialize_episode_artifacts(
        output_root,
        episodes,
        config=config,
        rosbag_reader=rosbag_reader,
    )

    manifest = DatasetManifest(
        dataset_id=dataset_id,
        source_type=source_type,
        source_root=str(source_root),
        output_root=str(output_root),
        episode_count=len(episodes),
        episodes=episodes,
        metadata={
            "config": config,
            "quality_summary": quality_summary,
        },
    )

    manifest_path = dump_json(output_root / "dataset_manifest.json", manifest.model_dump(mode="json"))
    episodes_path = dump_jsonl(
        output_root / "episodes.jsonl",
        [episode.model_dump(mode="json") for episode in episodes],
    )
    register_dataset(
        dataset_id=dataset_id,
        source_type=source_type,
        source_root=str(source_root),
        output_root=str(output_root),
        episode_count=len(episodes),
        manifest_path=str(manifest_path),
        episodes_path=str(episodes_path),
    )

    return IngestResult(
        dataset_id=dataset_id,
        source_type=source_type,
        source_root=str(source_root),
        output_root=str(output_root),
        episode_count=len(episodes),
        manifest_path=str(manifest_path),
        episodes_path=str(episodes_path),
    )
