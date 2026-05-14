"""Unit-style coverage for ingest and evaluation services."""

from __future__ import annotations

from pathlib import Path

from packages.adapters_rosbags import load_rosbag_reader
from packages.common.config import resolve_repo_path
from packages.common.io import load_json, load_yaml
from packages.eval_runner.service import compare_runs, run_evaluation
from packages.ingest.service import ingest_dataset
from scripts.create_rosbag2_sqlite_fixture import main as create_rosbag2_sqlite_fixture


def test_metadata_rosbag_reader_exposes_topics_and_messages() -> None:
    config = load_yaml(resolve_repo_path("configs/datasets/softrobotics_rosbag.yaml"))
    reader = load_rosbag_reader(resolve_repo_path(config["root"]), config)
    topics = {topic.alias: topic for topic in reader.topics()}
    episodes = reader.episodes()
    rgb_messages = list(reader.messages("rgb", episodes[0].episode_id))

    assert topics["rgb"].name == "/camera/color/image_raw"
    assert topics["state"].required is True
    assert episodes[0].episode_id == "ROSBAG_EP_0001"
    assert len(rgb_messages) == episodes[0].num_steps
    assert rgb_messages[0].payload["frame_id"].startswith("ROSBAG_EP_0001")


def test_sqlite_rosbag_reader_exposes_topics_episodes_and_messages() -> None:
    create_rosbag2_sqlite_fixture()
    config = load_yaml(resolve_repo_path("configs/datasets/softrobotics_rosbag_sqlite.yaml"))
    reader = load_rosbag_reader(resolve_repo_path(config["root"]), config)
    topics = {topic.alias: topic for topic in reader.topics()}
    episodes = reader.episodes()
    rgb_messages = list(reader.messages("rgb", episodes[0].episode_id))

    assert topics["rgb"].message_type == "sensor_msgs/msg/Image"
    assert episodes[0].episode_id == "SQLITE_ROSBAG_EP_0001"
    assert episodes[0].num_steps == 8
    assert len(rgb_messages) == 8
    assert rgb_messages[0].payload["frame_id"].startswith("SQLITE_ROSBAG_EP_0001")


def test_ingest_libero_and_rosbag_configs() -> None:
    create_rosbag2_sqlite_fixture()
    libero = ingest_dataset("configs/datasets/libero_debug.yaml")
    rosbag = ingest_dataset("configs/datasets/softrobotics_rosbag.yaml")
    rosbag_sqlite = ingest_dataset("configs/datasets/softrobotics_rosbag_sqlite.yaml")

    assert libero.dataset_id == "libero_debug_v1"
    assert libero.episode_count == 3
    assert Path(libero.manifest_path).exists()

    assert rosbag.dataset_id == "softrobotics_rosbag_v1"
    assert rosbag.episode_count == 2
    assert Path(rosbag.manifest_path).exists()
    assert rosbag_sqlite.dataset_id == "softrobotics_rosbag_sqlite_v1"
    assert rosbag_sqlite.episode_count == 2
    quality = load_json("outputs/datasets/softrobotics_rosbag_v1/quality_report.json")
    sqlite_quality = load_json("outputs/datasets/softrobotics_rosbag_sqlite_v1/quality_report.json")
    episode_quality = load_json("outputs/datasets/softrobotics_rosbag_v1/episodes/ROSBAG_EP_0001/quality.json")

    assert quality["episode_count"] == 2
    assert quality["pass_count"] == 2
    assert sqlite_quality["pass_count"] == 2
    assert sqlite_quality["episodes"][0]["stream_counts"]["rgb"] == 8
    assert episode_quality["stream_counts"]["rgb"] == 16
    assert Path("outputs/datasets/softrobotics_rosbag_v1/episodes/ROSBAG_EP_0001/streams/pressure.json").exists()


def test_eval_and_compare_runs() -> None:
    ingest_dataset("configs/datasets/libero_debug.yaml")

    cached = run_evaluation("configs/eval/libero_cached_eval.yaml")
    perturbed = run_evaluation("configs/eval/libero_perturbed_eval.yaml")
    comparison = compare_runs(cached.run_root, perturbed.run_root)

    assert cached.metrics["success_rate"] == 0.6667
    assert perturbed.metrics["success_rate"] == 0.3333
    assert comparison["delta"]["success_rate"] == -0.3334
    assert Path(cached.metrics_path).exists()
    assert Path(perturbed.metrics_path).exists()
