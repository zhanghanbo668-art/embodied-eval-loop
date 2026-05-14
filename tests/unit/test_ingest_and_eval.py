"""Unit-style coverage for ingest and evaluation services."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.adapters_rosbags import load_rosbag_reader
from packages.common.config import resolve_repo_path
from packages.common.io import load_json, load_yaml
from packages.eval_runner.service import compare_runs, run_evaluation
from packages.ingest.service import ingest_dataset
from scripts.create_rosbag2_cdr_fixture import main as create_rosbag2_cdr_fixture
from scripts.create_rosbag2_sqlite_fixture import main as create_rosbag2_sqlite_fixture


@pytest.fixture(scope="module")
def cdr_rosbag_fixture() -> None:
    create_rosbag2_cdr_fixture()


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


def test_rosbags_cdr_reader_exposes_decoded_topics_and_messages(cdr_rosbag_fixture: None) -> None:
    pytest.importorskip("rosbags")
    config = load_yaml(resolve_repo_path("configs/datasets/softrobotics_rosbag_cdr.yaml"))
    reader = load_rosbag_reader(resolve_repo_path(config["root"]), config)
    topics = {topic.alias: topic for topic in reader.topics()}
    episodes = reader.episodes()
    rgb_messages = list(reader.messages("rgb", episodes[0].episode_id))
    action_messages = list(reader.messages("action", episodes[0].episode_id))
    state_messages = list(reader.messages("state", episodes[0].episode_id))

    assert topics["rgb"].message_type == "sensor_msgs/msg/Image"
    assert topics["state"].message_type == "sensor_msgs/msg/JointState"
    assert episodes[0].episode_id == "CDR_ROSBAG_EP_0001"
    assert len(rgb_messages) == 6
    assert rgb_messages[0].payload["frame_id"].startswith("CDR_ROSBAG_EP_0001")
    assert action_messages[0].payload["command"] == "sense"
    assert state_messages[-1].payload["progress"] == pytest.approx(0.88)


def test_ingest_rosbags_cdr_and_mcap_configs(cdr_rosbag_fixture: None) -> None:
    pytest.importorskip("rosbags")
    cdr = ingest_dataset("configs/datasets/softrobotics_rosbag_cdr.yaml")
    mcap = ingest_dataset("configs/datasets/softrobotics_rosbag_mcap.yaml")

    assert cdr.dataset_id == "softrobotics_rosbag_cdr_v1"
    assert cdr.episode_count == 2
    assert mcap.dataset_id == "softrobotics_rosbag_mcap_v1"
    assert mcap.episode_count == 2

    cdr_quality = load_json("outputs/datasets/softrobotics_rosbag_cdr_v1/quality_report.json")
    mcap_quality = load_json("outputs/datasets/softrobotics_rosbag_mcap_v1/quality_report.json")
    action_stream = load_json("outputs/datasets/softrobotics_rosbag_cdr_v1/episodes/CDR_ROSBAG_EP_0001/streams/action.json")

    assert cdr_quality["pass_count"] == 2
    assert cdr_quality["episodes"][0]["stream_counts"]["rgb"] == 6
    assert mcap_quality["pass_count"] == 2
    assert action_stream[0]["action"] == "sense"


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
