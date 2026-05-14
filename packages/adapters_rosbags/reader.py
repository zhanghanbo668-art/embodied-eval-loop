"""ROSBag2-style reader abstractions.

The default reader is metadata-backed so the project remains software-only and
CI-friendly. Real ROSBag2 backends can implement the same protocol later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from packages.common.io import load_json


@dataclass(frozen=True, slots=True)
class TopicInfo:
    """Minimal topic metadata exposed by a ROSBag-style source."""

    name: str
    alias: str
    message_type: str
    required: bool = False


@dataclass(frozen=True, slots=True)
class TimestampedMessage:
    """Timestamped source message normalized for ingest."""

    topic: str
    timestamp_ms: int
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SourceEpisode:
    """Episode metadata discovered from a ROSBag-style source."""

    episode_id: str
    task_id: str
    instruction: str
    start_time_ms: int
    end_time_ms: int
    num_steps: int
    metadata: dict[str, Any]


class RosbagReader(Protocol):
    """Common interface for metadata-backed and real ROSBag2 readers."""

    def topics(self) -> list[TopicInfo]:
        """Return topics available in the source."""

    def episodes(self) -> list[SourceEpisode]:
        """Return source episode windows."""

    def messages(self, topic: str, episode_id: str | None = None) -> Iterable[TimestampedMessage]:
        """Yield timestamped messages for *topic*, optionally filtered by episode."""


class MetadataRosbagReader:
    """Deterministic ROSBag-style fixture reader.

    The reader converts lightweight metadata into timestamped topic streams.
    This gives the pipeline real topic discovery, message iteration, episode
    slicing, and alignment behavior without requiring ROS to be installed.
    """

    DEFAULT_MESSAGE_TYPES = {
        "rgb": "sensor_msgs/msg/Image",
        "state": "soft_robot_msgs/msg/State",
        "action": "soft_robot_msgs/msg/Command",
        "instruction": "std_msgs/msg/String",
        "pressure": "sensor_msgs/msg/FluidPressure",
        "joint_states": "sensor_msgs/msg/JointState",
        "episode_marker": "std_msgs/msg/String",
    }

    def __init__(self, source_root: Path, config: dict[str, Any]) -> None:
        self.source_root = source_root
        self.config = config
        self.metadata_path = source_root / str(config.get("metadata_file", "metadata.json"))
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"Expected rosbag metadata file at {self.metadata_path}")
        payload = load_json(self.metadata_path)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected mapping in rosbag metadata: {self.metadata_path}")
        self.payload = payload
        self.topic_map = {
            str(alias): str(topic)
            for alias, topic in dict(config.get("topics", {})).items()
        }
        self.required_aliases = {str(alias) for alias in config.get("required_topics", [])}
        self.optional_aliases = {str(alias) for alias in config.get("optional_topics", [])}
        self.step_period_ms = int(config.get("sync", {}).get("step_period_ms", 125))

    def topics(self) -> list[TopicInfo]:
        """Return topic aliases configured for this metadata-backed source."""
        infos: list[TopicInfo] = []
        for alias, topic_name in self.topic_map.items():
            infos.append(
                TopicInfo(
                    name=topic_name,
                    alias=alias,
                    message_type=self.DEFAULT_MESSAGE_TYPES.get(alias, "unknown"),
                    required=alias in self.required_aliases,
                )
            )
        return infos

    def episodes(self) -> list[SourceEpisode]:
        """Return source episodes with deterministic synthetic time windows."""
        raw_episodes = self.payload.get("episodes", [])
        if not isinstance(raw_episodes, list):
            raise ValueError(f"Expected 'episodes' list in rosbag metadata: {self.metadata_path}")

        source_episodes: list[SourceEpisode] = []
        for index, raw in enumerate(raw_episodes):
            if not isinstance(raw, dict):
                continue
            num_steps = int(raw.get("num_steps", 0))
            start_time_ms = int(raw.get("start_time_ms", 1_000_000 + index * 100_000))
            end_time_ms = int(raw.get("end_time_ms", start_time_ms + max(num_steps - 1, 0) * self.step_period_ms))
            source_episodes.append(
                SourceEpisode(
                    episode_id=str(raw.get("episode_id", f"ROSBAG_EP_{index + 1:04d}")),
                    task_id=str(raw.get("task", "unknown_task")),
                    instruction=str(raw.get("instruction", "")),
                    start_time_ms=start_time_ms,
                    end_time_ms=end_time_ms,
                    num_steps=num_steps,
                    metadata={
                        "reference_success": bool(raw.get("reference_success", True)),
                        "reference_completion_ratio": float(raw.get("reference_completion_ratio", 1.0)),
                        "reference_action_latency_ms": int(raw.get("reference_action_latency_ms", 0)),
                        "bag_name": self.payload.get("bag_name"),
                        "source_episode_index": index,
                    },
                )
            )
        return source_episodes

    def messages(self, topic: str, episode_id: str | None = None) -> Iterable[TimestampedMessage]:
        """Yield deterministic timestamped messages for a configured topic alias."""
        source_episodes = self.episodes()
        for episode in source_episodes:
            if episode_id and episode.episode_id != episode_id:
                continue
            if topic == "episode_marker":
                yield TimestampedMessage(
                    topic=topic,
                    timestamp_ms=episode.start_time_ms,
                    payload={"event": "start", "episode_id": episode.episode_id},
                )
                yield TimestampedMessage(
                    topic=topic,
                    timestamp_ms=episode.end_time_ms,
                    payload={"event": "end", "episode_id": episode.episode_id},
                )
                continue

            for step in range(max(episode.num_steps, 1)):
                timestamp_ms = episode.start_time_ms + step * self.step_period_ms
                yield TimestampedMessage(
                    topic=topic,
                    timestamp_ms=timestamp_ms,
                    payload=self._payload_for_topic(topic, episode, step),
                )

    def _payload_for_topic(self, topic: str, episode: SourceEpisode, step: int) -> dict[str, Any]:
        progress = round(((step + 1) / max(episode.num_steps, 1)) * episode.metadata["reference_completion_ratio"], 4)
        if topic == "rgb":
            return {
                "frame_id": f"{episode.episode_id}_rgb_{step:04d}",
                "encoding": "rgb8",
                "source_topic": self.topic_map.get(topic),
            }
        if topic == "state":
            return {
                "progress": progress,
                "stiffness": round(0.35 + progress * 0.4, 4),
                "contact": progress > 0.25,
            }
        if topic == "action":
            return {
                "command": _action_token(episode.task_id, step),
                "target_pressure": round(10.0 + progress * 40.0, 4),
            }
        if topic == "instruction":
            return {"text": episode.instruction}
        if topic == "pressure":
            return {"kpa": round(20.0 + progress * 55.0, 4)}
        if topic == "joint_states":
            return {"position": [round(progress, 4)], "velocity": [0.0]}
        return {"value": progress}


def _action_token(task_id: str, step: int) -> str:
    templates = {
        "soft_grasp_adjustment": ["sense", "approach", "pressurize", "stabilize"],
        "soft_reach_alignment": ["sense", "align", "micro_adjust", "hold"],
    }
    values = templates.get(task_id, ["observe", "plan", "act", "stabilize"])
    return values[step % len(values)]


def load_rosbag_reader(source_root: Path, config: dict[str, Any]) -> RosbagReader:
    """Instantiate the configured ROSBag-style reader."""
    reader_type = str(config.get("reader", "metadata"))
    if reader_type == "metadata":
        return MetadataRosbagReader(source_root, config)
    if reader_type == "rosbag2":
        raise NotImplementedError(
            "Real rosbag2 backend is not bundled. Use reader: metadata for CI-friendly fixtures."
        )
    raise ValueError(f"Unsupported rosbag reader: {reader_type}")
