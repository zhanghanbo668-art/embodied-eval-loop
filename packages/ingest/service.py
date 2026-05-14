"""Dataset ingest implementation for the software-only embodied eval stack."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


def _normalize_rosbag(config: dict[str, Any]) -> list[EpisodeRecord]:
    source_root = _source_root_from_config(config)
    metadata_file = source_root / "metadata.json"
    if not metadata_file.exists():
        raise FileNotFoundError(f"Expected rosbag metadata file at {metadata_file}")
    payload = load_json(metadata_file)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected mapping in rosbag metadata: {metadata_file}")
    raw_episodes = payload.get("episodes", [])
    if not isinstance(raw_episodes, list):
        raise ValueError(f"Expected 'episodes' list in rosbag metadata: {metadata_file}")

    dataset_id = str(config["output_dataset_id"])
    topics = config.get("topics", {})
    observation_streams = [name for name in topics.keys() if name not in {"action", "instruction", "state"}]

    episodes: list[EpisodeRecord] = []
    for raw_index, raw in enumerate(raw_episodes):
        if not isinstance(raw, dict):
            continue
        episode_id = str(raw.get("episode_id", f"{dataset_id}_{len(episodes):04d}"))
        start_time_ms, end_time_ms = _episode_window_ms(raw_index, int(raw.get("num_steps", 0)), "rosbag2")
        refs = [
            ArtifactRef(kind="ros_topic", path=f"streams/{topic_name}.json", description=str(topics.get(topic_name)))
            for topic_name in observation_streams
        ]
        episodes.append(
            EpisodeRecord(
                episode_id=episode_id,
                dataset_id=dataset_id,
                task_id=str(raw.get("task", "unknown_task")),
                instruction=str(raw.get("instruction", "")),
                source_type="rosbag2",
                source_uri=str(metadata_file),
                num_steps=int(raw.get("num_steps", 0)),
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                observation_refs=refs,
                action_ref=ArtifactRef(
                    kind="ros_topic",
                    path="streams/action.json",
                    description=str(topics.get("action", "/unknown/action")),
                ),
                state_ref=ArtifactRef(
                    kind="ros_topic",
                    path="streams/state.json",
                    description=str(topics.get("state", "/unknown/state")),
                ),
                events_ref=ArtifactRef(kind="event_timeline", path="events.jsonl"),
                plan_trace_ref=ArtifactRef(kind="plan_trace", path="plan_trace.jsonl"),
                metadata={
                    "reference_success": bool(raw.get("reference_success", True)),
                    "reference_completion_ratio": float(raw.get("reference_completion_ratio", 1.0)),
                    "reference_action_latency_ms": int(raw.get("reference_action_latency_ms", 0)),
                    "bag_name": payload.get("bag_name"),
                    "sync": config.get("sync", {}),
                    "source_episode_index": raw_index,
                    "normalization_source": "metadata_scaffold",
                },
            )
        )
    return episodes


def _materialize_episode_artifacts(output_root: Path, episodes: list[EpisodeRecord]) -> None:
    for episode in episodes:
        episode_dir = _build_episode_dir(output_root, episode.episode_id)
        streams_dir = ensure_dir(episode_dir / "streams")
        episode.artifact_root = display_path(episode_dir)

        action_trace = _build_action_trace(episode)
        state_trace = _build_state_trace(episode)
        event_timeline = _build_event_timeline(episode, action_trace, state_trace)
        plan_trace = _build_plan_trace(episode)

        if episode.action_ref:
            dump_json(streams_dir / Path(episode.action_ref.path).name, action_trace)
        if episode.state_ref:
            dump_json(streams_dir / Path(episode.state_ref.path).name, state_trace)
        for ref in episode.observation_refs:
            observation_trace = _build_observation_trace(ref.description or ref.kind, episode)
            dump_json(streams_dir / Path(ref.path).name, observation_trace)
        if episode.events_ref:
            dump_jsonl(episode_dir / episode.events_ref.path, event_timeline)
        if episode.plan_trace_ref:
            dump_jsonl(episode_dir / episode.plan_trace_ref.path, plan_trace)

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
                "replay_command": f"python -m pipelines.replay --run <RUN_ROOT> --top-k 1",
            },
        )


def ingest_dataset(config_path: str | Path) -> IngestResult:
    """Ingest one dataset config into normalized episode artifacts and a manifest."""
    config = load_dataset_config(config_path)
    dataset_id = str(config["output_dataset_id"])
    source_type = str(config.get("source_type", "unknown"))
    source_root = _source_root_from_config(config)
    output_root = _output_root(dataset_id)
    ensure_dir(output_root)

    if source_type == "libero":
        episodes = _normalize_libero(config)
    elif source_type == "rosbag2":
        episodes = _normalize_rosbag(config)
    else:
        raise ValueError(f"Unsupported source_type: {source_type}")

    _materialize_episode_artifacts(output_root, episodes)

    manifest = DatasetManifest(
        dataset_id=dataset_id,
        source_type=source_type,
        source_root=str(source_root),
        output_root=str(output_root),
        episode_count=len(episodes),
        episodes=episodes,
        metadata={
            "config": config,
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
