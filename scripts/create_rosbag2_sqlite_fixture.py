"""Create a tiny ROSBag2-style SQLite fixture for backend tests and demos."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.common.io import ensure_dir

FIXTURE_ROOT = REPO_ROOT / "data" / "rosbags" / "softrobotics_sqlite_case"
DB_PATH = FIXTURE_ROOT / "rosbag2_fixture.db3"

TOPICS = {
    "rgb": (1, "/camera/color/image_raw", "sensor_msgs/msg/Image"),
    "state": (2, "/soft_robot/state", "soft_robot_msgs/msg/State"),
    "action": (3, "/soft_robot/command", "soft_robot_msgs/msg/Command"),
    "pressure": (4, "/soft_robot/pressure", "sensor_msgs/msg/FluidPressure"),
    "instruction": (5, "/task_instruction", "std_msgs/msg/String"),
    "episode_marker": (6, "/episode_marker", "std_msgs/msg/String"),
}

EPISODES = [
    {
        "episode_id": "SQLITE_ROSBAG_EP_0001",
        "task": "soft_grasp_adjustment",
        "instruction": "increase pressure until stable contact is achieved",
        "num_steps": 8,
        "reference_success": True,
        "reference_completion_ratio": 0.9,
        "reference_action_latency_ms": 58,
        "start_time_ms": 2_000_000,
    },
    {
        "episode_id": "SQLITE_ROSBAG_EP_0002",
        "task": "soft_reach_alignment",
        "instruction": "align the actuator with the target contour",
        "num_steps": 9,
        "reference_success": False,
        "reference_completion_ratio": 0.48,
        "reference_action_latency_ms": 76,
        "start_time_ms": 2_100_000,
    },
]


def main() -> None:
    ensure_dir(FIXTURE_ROOT)
    if DB_PATH.exists():
        DB_PATH.unlink()

    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            CREATE TABLE topics(
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                serialization_format TEXT NOT NULL,
                offered_qos_profiles TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE messages(
                id INTEGER PRIMARY KEY,
                topic_id INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                data BLOB NOT NULL
            )
            """
        )
        for topic_id, topic_name, message_type in TOPICS.values():
            connection.execute(
                """
                INSERT INTO topics(id, name, type, serialization_format, offered_qos_profiles)
                VALUES (?, ?, ?, ?, ?)
                """,
                (topic_id, topic_name, message_type, "json", ""),
            )

        message_id = 1
        for episode in EPISODES:
            message_id = _insert_episode(connection, message_id, episode)
        connection.commit()

    print(DB_PATH)


def _insert_episode(connection: sqlite3.Connection, message_id: int, episode: dict[str, object]) -> int:
    step_period_ms = 125
    start_ms = int(episode["start_time_ms"])
    steps = int(episode["num_steps"])
    end_ms = start_ms + (steps - 1) * step_period_ms
    progress_target = float(episode["reference_completion_ratio"])

    message_id = _insert_message(
        connection,
        message_id,
        "episode_marker",
        start_ms,
        {
            "event": "start",
            **episode,
        },
    )
    for step in range(steps):
        timestamp_ms = start_ms + step * step_period_ms
        progress = round(((step + 1) / steps) * progress_target, 4)
        message_id = _insert_message(
            connection,
            message_id,
            "rgb",
            timestamp_ms,
            {
                "frame_id": f"{episode['episode_id']}_rgb_{step:04d}",
                "encoding": "rgb8",
            },
        )
        message_id = _insert_message(
            connection,
            message_id,
            "state",
            timestamp_ms,
            {
                "progress": progress,
                "stiffness": round(0.35 + progress * 0.4, 4),
                "contact": progress > 0.25,
            },
        )
        message_id = _insert_message(
            connection,
            message_id,
            "action",
            timestamp_ms,
            {
                "command": _action_token(str(episode["task"]), step),
                "target_pressure": round(10.0 + progress * 40.0, 4),
            },
        )
        message_id = _insert_message(
            connection,
            message_id,
            "pressure",
            timestamp_ms,
            {"kpa": round(20.0 + progress * 55.0, 4)},
        )
        message_id = _insert_message(
            connection,
            message_id,
            "instruction",
            timestamp_ms,
            {"text": episode["instruction"]},
        )

    return _insert_message(
        connection,
        message_id,
        "episode_marker",
        end_ms,
        {
            "event": "end",
            **episode,
            "end_time_ms": end_ms,
        },
    )


def _insert_message(
    connection: sqlite3.Connection,
    message_id: int,
    topic_alias: str,
    timestamp_ms: int,
    payload: dict[str, object],
) -> int:
    topic_id = TOPICS[topic_alias][0]
    connection.execute(
        "INSERT INTO messages(id, topic_id, timestamp, data) VALUES (?, ?, ?, ?)",
        (message_id, topic_id, timestamp_ms * 1_000_000, json.dumps(payload, sort_keys=True).encode("utf-8")),
    )
    return message_id + 1


def _action_token(task_id: str, step: int) -> str:
    templates = {
        "soft_grasp_adjustment": ["sense", "approach", "pressurize", "stabilize"],
        "soft_reach_alignment": ["sense", "align", "micro_adjust", "hold"],
    }
    values = templates.get(task_id, ["observe", "plan", "act", "stabilize"])
    return values[step % len(values)]


if __name__ == "__main__":
    main()
