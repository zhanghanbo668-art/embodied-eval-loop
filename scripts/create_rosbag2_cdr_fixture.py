"""Create tiny CDR-serialized ROSBag2 fixtures for backend tests and demos."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.common.io import ensure_dir

FIXTURE_ROOT = REPO_ROOT / "data" / "rosbags"
SQLITE_BAG_PATH = FIXTURE_ROOT / "softrobotics_cdr_case"
MCAP_BAG_PATH = FIXTURE_ROOT / "softrobotics_mcap_case"

EPISODES = [
    {
        "episode_id": "CDR_ROSBAG_EP_0001",
        "task": "soft_grasp_adjustment",
        "instruction": "increase pressure until stable contact is achieved",
        "num_steps": 6,
        "reference_success": True,
        "reference_completion_ratio": 0.88,
        "reference_action_latency_ms": 61,
        "start_time_ms": 3_000_000,
    },
    {
        "episode_id": "CDR_ROSBAG_EP_0002",
        "task": "soft_reach_alignment",
        "instruction": "align the actuator with the target contour",
        "num_steps": 7,
        "reference_success": False,
        "reference_completion_ratio": 0.52,
        "reference_action_latency_ms": 84,
        "start_time_ms": 3_100_000,
    },
]


def main() -> None:
    """Generate sqlite3 and MCAP rosbag2 directories with CDR payloads."""
    try:
        from rosbags.rosbag2 import StoragePlugin, Writer
        from rosbags.typesys import Stores, get_typestore
    except ImportError as exc:
        raise RuntimeError("Install optional rosbags support with: python -m pip install -e .[rosbag]") from exc

    if _fixture_ready(SQLITE_BAG_PATH) and _fixture_ready(MCAP_BAG_PATH):
        print(SQLITE_BAG_PATH)
        print(MCAP_BAG_PATH)
        return

    typestore = get_typestore(Stores.LATEST)
    _write_bag(SQLITE_BAG_PATH, StoragePlugin.SQLITE3, Writer, typestore)
    _write_bag(MCAP_BAG_PATH, StoragePlugin.MCAP, Writer, typestore)
    print(SQLITE_BAG_PATH)
    print(MCAP_BAG_PATH)


def _write_bag(path: Path, storage_plugin: object, writer_cls: object, typestore: object) -> None:
    if path.exists():
        shutil.rmtree(path)
    ensure_dir(path.parent)

    with writer_cls(path, version=9, storage_plugin=storage_plugin) as writer:
        connections = {
            "rgb": writer.add_connection("/camera/color/image_raw", "sensor_msgs/msg/Image", typestore=typestore),
            "state": writer.add_connection("/joint_states", "sensor_msgs/msg/JointState", typestore=typestore),
            "action": writer.add_connection("/soft_robot/command", "std_msgs/msg/String", typestore=typestore),
            "pressure": writer.add_connection("/soft_robot/pressure", "sensor_msgs/msg/FluidPressure", typestore=typestore),
            "instruction": writer.add_connection("/task_instruction", "std_msgs/msg/String", typestore=typestore),
            "episode_marker": writer.add_connection("/episode_marker", "std_msgs/msg/String", typestore=typestore),
        }
        for episode in EPISODES:
            _write_episode(writer, connections, typestore, episode)


def _fixture_ready(path: Path) -> bool:
    if not path.exists():
        return False
    metadata = path / "metadata.yaml"
    if not metadata.exists():
        return False
    for child in path.iterdir():
        if child.is_file() and child.name != "metadata.yaml":
            return True
    return False


def _write_episode(writer: object, connections: dict[str, object], typestore: object, episode: dict[str, object]) -> None:
    classes = typestore.types
    string_cls = classes["std_msgs/msg/String"]
    time_cls = classes["builtin_interfaces/msg/Time"]
    header_cls = classes["std_msgs/msg/Header"]
    image_cls = classes["sensor_msgs/msg/Image"]
    joint_state_cls = classes["sensor_msgs/msg/JointState"]
    pressure_cls = classes["sensor_msgs/msg/FluidPressure"]

    step_period_ms = 125
    start_ms = int(episode["start_time_ms"])
    steps = int(episode["num_steps"])
    end_ms = start_ms + (steps - 1) * step_period_ms
    target_completion = float(episode["reference_completion_ratio"])

    _write_string(writer, connections["episode_marker"], typestore, start_ms, {"event": "start", **episode})
    for step in range(steps):
        timestamp_ms = start_ms + step * step_period_ms
        progress = round(((step + 1) / steps) * target_completion, 4)
        header = header_cls(time_cls(timestamp_ms // 1000, (timestamp_ms % 1000) * 1_000_000), f"{episode['episode_id']}_rgb_{step:04d}")
        image = image_cls(
            header,
            2,
            2,
            "rgb8",
            0,
            6,
            np.array([(step + offset) % 255 for offset in range(12)], dtype=np.uint8),
        )
        writer.write(
            connections["rgb"],
            timestamp_ms * 1_000_000,
            typestore.serialize_cdr(image, "sensor_msgs/msg/Image"),
        )
        joint_state = joint_state_cls(
            header,
            ["progress", "stiffness"],
            np.array([progress, round(0.35 + progress * 0.4, 4)], dtype=np.float64),
            np.array([0.0, 0.0], dtype=np.float64),
            np.array([0.0, 0.0], dtype=np.float64),
        )
        writer.write(
            connections["state"],
            timestamp_ms * 1_000_000,
            typestore.serialize_cdr(joint_state, "sensor_msgs/msg/JointState"),
        )
        writer.write(
            connections["action"],
            timestamp_ms * 1_000_000,
            typestore.serialize_cdr(string_cls(_action_payload(str(episode["task"]), progress, step)), "std_msgs/msg/String"),
        )
        pressure = pressure_cls(header, float(20_000.0 + progress * 55_000.0), 0.0)
        writer.write(
            connections["pressure"],
            timestamp_ms * 1_000_000,
            typestore.serialize_cdr(pressure, "sensor_msgs/msg/FluidPressure"),
        )
        writer.write(
            connections["instruction"],
            timestamp_ms * 1_000_000,
            typestore.serialize_cdr(string_cls(str(episode["instruction"])), "std_msgs/msg/String"),
        )

    _write_string(writer, connections["episode_marker"], typestore, end_ms, {"event": "end", **episode, "end_time_ms": end_ms})


def _write_string(writer: object, connection: object, typestore: object, timestamp_ms: int, payload: dict[str, object]) -> None:
    string_cls = typestore.types["std_msgs/msg/String"]
    writer.write(
        connection,
        timestamp_ms * 1_000_000,
        typestore.serialize_cdr(string_cls(json.dumps(payload, sort_keys=True)), "std_msgs/msg/String"),
    )


def _action_payload(task_id: str, progress: float, step: int) -> str:
    templates = {
        "soft_grasp_adjustment": ["sense", "approach", "pressurize", "stabilize"],
        "soft_reach_alignment": ["sense", "align", "micro_adjust", "hold"],
    }
    command = templates.get(task_id, ["observe", "plan", "act", "stabilize"])[step % 4]
    return json.dumps({"command": command, "target_pressure": round(10.0 + progress * 40.0, 4)}, sort_keys=True)


if __name__ == "__main__":
    main()
