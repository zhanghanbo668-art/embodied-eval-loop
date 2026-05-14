"""Coverage for dataset export and validation services."""

from __future__ import annotations

from pathlib import Path

from packages.common.io import load_json
from packages.exporters import export_dataset
from packages.ingest.service import ingest_dataset
from packages.validation import validate_dataset
from scripts.create_rosbag2_sqlite_fixture import main as create_rosbag2_sqlite_fixture


def test_validate_and_export_sqlite_rosbag_dataset() -> None:
    create_rosbag2_sqlite_fixture()
    ingest_dataset("configs/datasets/softrobotics_rosbag_sqlite.yaml")

    validation = validate_dataset("outputs/datasets/softrobotics_rosbag_sqlite_v1")
    export = export_dataset("outputs/datasets/softrobotics_rosbag_sqlite_v1", export_format="learning_jsonl")
    lerobot = export_dataset("outputs/datasets/softrobotics_rosbag_sqlite_v1", export_format="lerobot_stub")

    assert validation.status == "pass"
    assert validation.error_count == 0
    assert Path(validation.report_path).exists()
    assert export.episode_count == 2
    assert Path(export.manifest_path).exists()
    assert Path(export.index_path).exists()
    assert Path(lerobot.optional_artifacts["lerobot_metadata"]).exists()

    manifest = load_json(export.manifest_path)
    assert manifest["format"] == "learning_jsonl"
    assert manifest["episode_count"] == 2
