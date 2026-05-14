"""ROSBag2-style reader abstractions.

The default reader is metadata-backed so the project remains software-only and
CI-friendly. Real ROSBag2 backends can implement the same protocol later.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
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


class SQLiteRosbag2Reader:
    """Reader for ROSBag2 SQLite storage.

    This backend understands the standard ROSBag2 SQLite tables:

    - `topics(id, name, type, serialization_format, offered_qos_profiles)`
    - `messages(id, topic_id, timestamp, data)`

    The backend can decode JSON payloads stored in `messages.data`, which keeps
    tests software-only. For binary CDR payloads from real bags, it still exposes
    topic discovery and timestamps with a raw payload marker, leaving message
    deserialization to a future ROS-aware adapter.
    """

    def __init__(self, source_root: Path, config: dict[str, Any]) -> None:
        self.source_root = source_root
        self.config = config
        self.db_path = source_root / str(config.get("database", config.get("db3", "rosbag2.db3")))
        if not self.db_path.exists():
            raise FileNotFoundError(f"Expected ROSBag2 SQLite database at {self.db_path}")
        self.topic_map = {
            str(alias): str(topic)
            for alias, topic in dict(config.get("topics", {})).items()
        }
        self.required_aliases = {str(alias) for alias in config.get("required_topics", [])}
        self.sync_config = dict(config.get("sync", {}))
        self._topics_cache: list[TopicInfo] | None = None
        self._topic_ids_by_alias: dict[str, int] | None = None

    def topics(self) -> list[TopicInfo]:
        """Return configured topics discovered in the SQLite storage."""
        if self._topics_cache is not None:
            return self._topics_cache

        db_topics = self._load_db_topics()
        infos: list[TopicInfo] = []
        topic_ids_by_alias: dict[str, int] = {}
        for alias, topic_name in self.topic_map.items():
            row = db_topics.get(topic_name)
            if row is None:
                continue
            topic_id, message_type = row
            infos.append(
                TopicInfo(
                    name=topic_name,
                    alias=alias,
                    message_type=message_type,
                    required=alias in self.required_aliases,
                )
            )
            topic_ids_by_alias[alias] = topic_id
        self._topics_cache = infos
        self._topic_ids_by_alias = topic_ids_by_alias
        return infos

    def episodes(self) -> list[SourceEpisode]:
        """Return episode windows from marker messages or config fallback."""
        markers = list(self.messages("episode_marker")) if "episode_marker" in self.topic_map else []
        episodes = self._episodes_from_markers(markers)
        if episodes:
            return episodes

        configured = self.config.get("episodes", [])
        if isinstance(configured, list) and configured:
            return [self._episode_from_config(index, raw) for index, raw in enumerate(configured) if isinstance(raw, dict)]

        start_time_ms, end_time_ms = self._message_time_bounds_ms()
        step_period_ms = int(self.sync_config.get("step_period_ms", 125))
        num_steps = max(1, int((end_time_ms - start_time_ms) / max(step_period_ms, 1)) + 1)
        return [
            SourceEpisode(
                episode_id=str(self.config.get("default_episode_id", "ROSBAG_SQLITE_EP_0001")),
                task_id=str(self.config.get("default_task_id", "unknown_task")),
                instruction=str(self.config.get("default_instruction", "")),
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                num_steps=num_steps,
                metadata={
                    "reference_success": bool(self.config.get("reference_success", True)),
                    "reference_completion_ratio": float(self.config.get("reference_completion_ratio", 1.0)),
                    "reference_action_latency_ms": int(self.config.get("reference_action_latency_ms", 0)),
                    "bag_name": self.db_path.name,
                    "source_episode_index": 0,
                },
            )
        ]

    def messages(self, topic: str, episode_id: str | None = None) -> Iterable[TimestampedMessage]:
        """Yield timestamped messages for one configured topic alias."""
        topic_ids = self._topic_ids()
        topic_id = topic_ids.get(topic)
        if topic_id is None:
            return

        window = self._episode_window(episode_id) if episode_id else None
        with closing(sqlite3.connect(self.db_path)) as connection:
            rows = connection.execute(
                """
                SELECT timestamp, data
                FROM messages
                WHERE topic_id = ?
                ORDER BY timestamp ASC
                """,
                (topic_id,),
            ).fetchall()

        for timestamp_ns, data in rows:
            timestamp_ms = _timestamp_to_ms(int(timestamp_ns))
            if window and not (window[0] <= timestamp_ms <= window[1]):
                continue
            yield TimestampedMessage(
                topic=topic,
                timestamp_ms=timestamp_ms,
                payload=_decode_sqlite_payload(data),
            )

    def _load_db_topics(self) -> dict[str, tuple[int, str]]:
        with closing(sqlite3.connect(self.db_path)) as connection:
            rows = connection.execute("SELECT id, name, type FROM topics").fetchall()
        return {str(name): (int(topic_id), str(message_type)) for topic_id, name, message_type in rows}

    def _topic_ids(self) -> dict[str, int]:
        if self._topic_ids_by_alias is None:
            self.topics()
        return self._topic_ids_by_alias or {}

    def _episodes_from_markers(self, markers: list[TimestampedMessage]) -> list[SourceEpisode]:
        by_episode: dict[str, dict[str, TimestampedMessage]] = {}
        for marker in markers:
            episode_id = str(marker.payload.get("episode_id", ""))
            event = str(marker.payload.get("event", ""))
            if not episode_id or event not in {"start", "end"}:
                continue
            by_episode.setdefault(episode_id, {})[event] = marker

        episodes: list[SourceEpisode] = []
        for index, episode_id in enumerate(sorted(by_episode)):
            pair = by_episode[episode_id]
            if "start" not in pair or "end" not in pair:
                continue
            start = pair["start"]
            end = pair["end"]
            payload = start.payload | end.payload
            step_period_ms = int(self.sync_config.get("step_period_ms", 125))
            num_steps = int(payload.get("num_steps", max(1, int((end.timestamp_ms - start.timestamp_ms) / step_period_ms) + 1)))
            episodes.append(
                SourceEpisode(
                    episode_id=episode_id,
                    task_id=str(payload.get("task", payload.get("task_id", "unknown_task"))),
                    instruction=str(payload.get("instruction", "")),
                    start_time_ms=start.timestamp_ms,
                    end_time_ms=end.timestamp_ms,
                    num_steps=num_steps,
                    metadata={
                        "reference_success": bool(payload.get("reference_success", True)),
                        "reference_completion_ratio": float(payload.get("reference_completion_ratio", 1.0)),
                        "reference_action_latency_ms": int(payload.get("reference_action_latency_ms", 0)),
                        "bag_name": self.db_path.name,
                        "source_episode_index": index,
                    },
                )
            )
        return episodes

    def _episode_from_config(self, index: int, raw: dict[str, Any]) -> SourceEpisode:
        start_time_ms = int(raw.get("start_time_ms", 0))
        end_time_ms = int(raw.get("end_time_ms", start_time_ms))
        return SourceEpisode(
            episode_id=str(raw.get("episode_id", f"ROSBAG_SQLITE_EP_{index + 1:04d}")),
            task_id=str(raw.get("task", raw.get("task_id", "unknown_task"))),
            instruction=str(raw.get("instruction", "")),
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            num_steps=int(raw.get("num_steps", 0)),
            metadata={
                "reference_success": bool(raw.get("reference_success", True)),
                "reference_completion_ratio": float(raw.get("reference_completion_ratio", 1.0)),
                "reference_action_latency_ms": int(raw.get("reference_action_latency_ms", 0)),
                "bag_name": self.db_path.name,
                "source_episode_index": index,
            },
        )

    def _episode_window(self, episode_id: str | None) -> tuple[int, int] | None:
        if episode_id is None:
            return None
        for episode in self.episodes():
            if episode.episode_id == episode_id:
                return episode.start_time_ms, episode.end_time_ms
        return None

    def _message_time_bounds_ms(self) -> tuple[int, int]:
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute("SELECT MIN(timestamp), MAX(timestamp) FROM messages").fetchone()
        if not row or row[0] is None or row[1] is None:
            return 0, 0
        return _timestamp_to_ms(int(row[0])), _timestamp_to_ms(int(row[1]))


class RosbagsRosbag2Reader:
    """Reader for real ROSBag2 directories via the optional `rosbags` package.

    This backend reads rosbag2 metadata directories and can deserialize CDR
    payloads from both sqlite3 and MCAP storage plugins when `rosbags` is
    installed. It intentionally keeps decoded payloads in the same lightweight
    dictionaries used by the rest of the pipeline.
    """

    def __init__(self, source_root: Path, config: dict[str, Any]) -> None:
        try:
            from rosbags.rosbag2 import Reader
            from rosbags.typesys import Stores, get_typestore
        except ImportError as exc:
            raise ImportError(
                "The rosbags-backed reader requires the optional dependency group: "
                "python -m pip install -e .[rosbag]"
            ) from exc

        self.source_root = source_root
        self.config = config
        self.bag_path = source_root / str(config.get("bag_path", "."))
        if not self.bag_path.exists():
            raise FileNotFoundError(f"Expected ROSBag2 directory at {self.bag_path}")
        self._reader_cls = Reader
        self.typestore = get_typestore(Stores.LATEST)
        self.topic_map = {
            str(alias): str(topic)
            for alias, topic in dict(config.get("topics", {})).items()
        }
        self.required_aliases = {str(alias) for alias in config.get("required_topics", [])}
        self.sync_config = dict(config.get("sync", {}))
        self._topics_cache: list[TopicInfo] | None = None
        self._connections_by_alias: dict[str, Any] | None = None
        self._episodes_cache: list[SourceEpisode] | None = None

    def topics(self) -> list[TopicInfo]:
        """Return configured topics discovered in the rosbag2 metadata."""
        if self._topics_cache is not None:
            return self._topics_cache

        with self._reader_cls(self.bag_path) as reader:
            connections = list(reader.connections)

        infos: list[TopicInfo] = []
        by_alias: dict[str, Any] = {}
        for alias, topic_name in self.topic_map.items():
            connection = next((conn for conn in connections if conn.topic == topic_name), None)
            if connection is None:
                continue
            infos.append(
                TopicInfo(
                    name=topic_name,
                    alias=alias,
                    message_type=str(connection.msgtype),
                    required=alias in self.required_aliases,
                )
            )
            by_alias[alias] = connection
        self._topics_cache = infos
        self._connections_by_alias = by_alias
        return infos

    def episodes(self) -> list[SourceEpisode]:
        """Return episode windows from marker messages or config fallback."""
        if self._episodes_cache is not None:
            return self._episodes_cache

        markers = list(self.messages("episode_marker")) if "episode_marker" in self.topic_map else []
        episodes = self._episodes_from_markers(markers)
        if episodes:
            self._episodes_cache = episodes
            return episodes

        configured = self.config.get("episodes", [])
        if isinstance(configured, list) and configured:
            episodes = [self._episode_from_config(index, raw) for index, raw in enumerate(configured) if isinstance(raw, dict)]
            self._episodes_cache = episodes
            return episodes

        start_time_ms, end_time_ms = self._message_time_bounds_ms()
        step_period_ms = int(self.sync_config.get("step_period_ms", 125))
        num_steps = max(1, int((end_time_ms - start_time_ms) / max(step_period_ms, 1)) + 1)
        episodes = [
            SourceEpisode(
                episode_id=str(self.config.get("default_episode_id", "ROSBAG_CDR_EP_0001")),
                task_id=str(self.config.get("default_task_id", "unknown_task")),
                instruction=str(self.config.get("default_instruction", "")),
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                num_steps=num_steps,
                metadata={
                    "reference_success": bool(self.config.get("reference_success", True)),
                    "reference_completion_ratio": float(self.config.get("reference_completion_ratio", 1.0)),
                    "reference_action_latency_ms": int(self.config.get("reference_action_latency_ms", 0)),
                    "bag_name": self.bag_path.name,
                    "source_episode_index": 0,
                },
            )
        ]
        self._episodes_cache = episodes
        return episodes

    def messages(self, topic: str, episode_id: str | None = None) -> Iterable[TimestampedMessage]:
        """Yield decoded CDR messages for one configured topic alias."""
        connection = self._connections().get(topic)
        if connection is None:
            return

        window = self._episode_window(episode_id) if episode_id else None
        with self._reader_cls(self.bag_path) as reader:
            for conn, timestamp_ns, raw in reader.messages(connections=[connection]):
                timestamp_ms = _timestamp_to_ms(int(timestamp_ns))
                if window and not (window[0] <= timestamp_ms <= window[1]):
                    continue
                yield TimestampedMessage(
                    topic=topic,
                    timestamp_ms=timestamp_ms,
                    payload=self._decode_cdr_payload(raw, str(conn.msgtype)),
                )

    def _connections(self) -> dict[str, Any]:
        if self._connections_by_alias is None:
            self.topics()
        return self._connections_by_alias or {}

    def _decode_cdr_payload(self, raw: bytes | memoryview, message_type: str) -> dict[str, Any]:
        try:
            message = self.typestore.deserialize_cdr(raw, message_type)
        except Exception:
            return {"raw_bytes": len(raw), "encoding": "cdr", "message_type": message_type}
        return _ros_message_to_payload(message, message_type)

    def _episodes_from_markers(self, markers: list[TimestampedMessage]) -> list[SourceEpisode]:
        by_episode: dict[str, dict[str, TimestampedMessage]] = {}
        for marker in markers:
            marker_payload = _parse_marker_payload(marker.payload)
            episode_id = str(marker_payload.get("episode_id", ""))
            event = str(marker_payload.get("event", ""))
            if not episode_id or event not in {"start", "end"}:
                continue
            marker = TimestampedMessage(marker.topic, marker.timestamp_ms, marker_payload)
            by_episode.setdefault(episode_id, {})[event] = marker

        episodes: list[SourceEpisode] = []
        for index, episode_id in enumerate(sorted(by_episode)):
            pair = by_episode[episode_id]
            if "start" not in pair or "end" not in pair:
                continue
            start = pair["start"]
            end = pair["end"]
            payload = start.payload | end.payload
            step_period_ms = int(self.sync_config.get("step_period_ms", 125))
            num_steps = int(payload.get("num_steps", max(1, int((end.timestamp_ms - start.timestamp_ms) / step_period_ms) + 1)))
            episodes.append(
                SourceEpisode(
                    episode_id=episode_id,
                    task_id=str(payload.get("task", payload.get("task_id", "unknown_task"))),
                    instruction=str(payload.get("instruction", "")),
                    start_time_ms=start.timestamp_ms,
                    end_time_ms=end.timestamp_ms,
                    num_steps=num_steps,
                    metadata={
                        "reference_success": bool(payload.get("reference_success", True)),
                        "reference_completion_ratio": float(payload.get("reference_completion_ratio", 1.0)),
                        "reference_action_latency_ms": int(payload.get("reference_action_latency_ms", 0)),
                        "bag_name": self.bag_path.name,
                        "source_episode_index": index,
                        "serialization": "cdr",
                    },
                )
            )
        return episodes

    def _episode_from_config(self, index: int, raw: dict[str, Any]) -> SourceEpisode:
        start_time_ms = int(raw.get("start_time_ms", 0))
        end_time_ms = int(raw.get("end_time_ms", start_time_ms))
        return SourceEpisode(
            episode_id=str(raw.get("episode_id", f"ROSBAG_CDR_EP_{index + 1:04d}")),
            task_id=str(raw.get("task", raw.get("task_id", "unknown_task"))),
            instruction=str(raw.get("instruction", "")),
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            num_steps=int(raw.get("num_steps", 0)),
            metadata={
                "reference_success": bool(raw.get("reference_success", True)),
                "reference_completion_ratio": float(raw.get("reference_completion_ratio", 1.0)),
                "reference_action_latency_ms": int(raw.get("reference_action_latency_ms", 0)),
                "bag_name": self.bag_path.name,
                "source_episode_index": index,
                "serialization": "cdr",
            },
        )

    def _episode_window(self, episode_id: str | None) -> tuple[int, int] | None:
        if episode_id is None:
            return None
        for episode in self.episodes():
            if episode.episode_id == episode_id:
                return episode.start_time_ms, episode.end_time_ms
        return None

    def _message_time_bounds_ms(self) -> tuple[int, int]:
        with self._reader_cls(self.bag_path) as reader:
            timestamps = [timestamp for _, timestamp, _ in reader.messages()]
        if not timestamps:
            return 0, 0
        return _timestamp_to_ms(min(timestamps)), _timestamp_to_ms(max(timestamps))


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
    if reader_type in {"rosbag2", "sqlite", "rosbag2_sqlite"}:
        return SQLiteRosbag2Reader(source_root, config)
    if reader_type in {"rosbags", "rosbags_rosbag2", "rosbag2_cdr", "mcap"}:
        return RosbagsRosbag2Reader(source_root, config)
    raise ValueError(f"Unsupported rosbag reader: {reader_type}")


def _timestamp_to_ms(timestamp: int) -> int:
    """Convert ROSBag2 nanosecond timestamps to milliseconds when needed."""
    if timestamp > 10_000_000_000:
        return int(timestamp / 1_000_000)
    return int(timestamp)


def _decode_sqlite_payload(data: Any) -> dict[str, Any]:
    """Decode JSON fixture payloads or preserve raw binary metadata."""
    if data is None:
        return {}
    if isinstance(data, memoryview):
        data = data.tobytes()
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return {"raw_bytes": len(data), "encoding": "cdr"}
    else:
        text = str(data)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"value": text}
    return payload if isinstance(payload, dict) else {"value": payload}


def _parse_marker_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("data"), str):
        try:
            parsed = json.loads(str(payload["data"]))
        except json.JSONDecodeError:
            return payload
        if isinstance(parsed, dict):
            return parsed
    return payload


def _ros_message_to_payload(message: Any, message_type: str) -> dict[str, Any]:
    if message_type == "std_msgs/msg/String":
        text = str(getattr(message, "data", ""))
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"data": text, "text": text}
        if isinstance(parsed, dict):
            return {"data": text, "text": text, **parsed}
        return {"data": text, "text": text, "value": parsed}
    if message_type == "sensor_msgs/msg/Image":
        data = getattr(message, "data", [])
        return {
            "frame_id": str(getattr(getattr(message, "header", None), "frame_id", "")),
            "height": int(getattr(message, "height", 0)),
            "width": int(getattr(message, "width", 0)),
            "encoding": str(getattr(message, "encoding", "")),
            "is_bigendian": int(getattr(message, "is_bigendian", 0)),
            "step_bytes": int(getattr(message, "step", 0)),
            "data_bytes": int(getattr(data, "size", len(data) if hasattr(data, "__len__") else 0)),
        }
    if message_type == "sensor_msgs/msg/JointState":
        names = list(getattr(message, "name", []))
        positions = _numeric_sequence(getattr(message, "position", []))
        payload = {
            "name": list(getattr(message, "name", [])),
            "position": positions,
            "velocity": _numeric_sequence(getattr(message, "velocity", [])),
            "effort": _numeric_sequence(getattr(message, "effort", [])),
        }
        for name, value in zip(names, positions):
            payload[str(name)] = value
        if "progress" in payload:
            payload["contact"] = float(payload["progress"]) > 0.25
        return payload
    if message_type == "sensor_msgs/msg/FluidPressure":
        return {
            "kpa": round(float(getattr(message, "fluid_pressure", 0.0)) / 1000.0, 4),
            "fluid_pressure": float(getattr(message, "fluid_pressure", 0.0)),
            "variance": float(getattr(message, "variance", 0.0)),
        }
    return _object_to_jsonable(message)


def _object_to_jsonable(value: Any) -> dict[str, Any]:
    annotations = getattr(value, "__annotations__", {})
    payload: dict[str, Any] = {}
    for key in annotations:
        if key.startswith("__"):
            continue
        payload[key] = _jsonable_value(getattr(value, key, None))
    return payload


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_jsonable_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable_value(item) for key, item in value.items()}
    if getattr(value, "__annotations__", None):
        return _object_to_jsonable(value)
    return str(value)


def _numeric_sequence(value: Any) -> list[float]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [float(item) for item in value]
