"""Coverage for dataset export and validation services."""

from __future__ import annotations

from pathlib import Path

from packages.common.io import load_json, load_jsonl
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
    hdf5 = export_dataset("outputs/datasets/softrobotics_rosbag_sqlite_v1", export_format="hdf5_stub")

    assert validation.status == "pass"
    assert validation.error_count == 0
    assert Path(validation.report_path).exists()
    assert export.episode_count == 2
    assert Path(export.manifest_path).exists()
    assert Path(export.index_path).exists()
    assert Path(lerobot.optional_artifacts["lerobot_metadata"]).exists()
    assert Path(hdf5.optional_artifacts["hdf5_metadata"]).exists()

    manifest = load_json(export.manifest_path)
    assert manifest["format"] == "learning_jsonl"
    assert manifest["episode_count"] == 2


def test_split_jsonl_export_is_reproducible(tmp_path: Path) -> None:
    create_rosbag2_sqlite_fixture()
    ingest_dataset("configs/datasets/softrobotics_rosbag_sqlite.yaml")

    first = export_dataset(
        "outputs/datasets/softrobotics_rosbag_sqlite_v1",
        output_root=tmp_path / "split_export_a",
        export_format="split_jsonl",
        split_ratio=0.5,
        split_seed=2,
    )
    second = export_dataset(
        "outputs/datasets/softrobotics_rosbag_sqlite_v1",
        output_root=tmp_path / "split_export_b",
        export_format="split_jsonl",
        split_ratio=0.5,
        split_seed=2,
    )

    first_manifest = load_json(first.manifest_path)
    second_manifest = load_json(second.manifest_path)
    first_split_manifest = load_json(first.export_root / "split_manifest.json")

    assert first_manifest["format"] == "split_jsonl"
    assert first_manifest["split_ratio"] == 0.5
    assert first_manifest["split_seed"] == 2
    assert first_manifest["warnings"] == []
    assert Path(first.manifest_path).name == "export_manifest.json"
    assert Path(first.index_path).name == "episodes.jsonl"
    assert first_manifest["index_path"].endswith("episodes.jsonl")
    assert first_manifest["split_manifest_path"].endswith("split_manifest.json")
    assert first_manifest["optional_artifacts"]["split_manifest"].endswith("split_manifest.json")

    assert first_split_manifest["split_counts"] == {"train": 1, "eval": 1}
    assert second_manifest["split_ratio"] == 0.5
    assert second_manifest["split_seed"] == 2
    assert first_split_manifest["assignments"] == load_json(second.export_root / "split_manifest.json")["assignments"]
    assert len(first_split_manifest["assignments"]) == first.episode_count

    root_rows = load_jsonl(first.index_path)
    train_rows = load_jsonl(first.export_root / "train" / "episodes.jsonl")
    eval_rows = load_jsonl(first.export_root / "eval" / "episodes.jsonl")
    assert len(root_rows) == first.episode_count
    assert len(train_rows) == first_split_manifest["split_counts"]["train"]
    assert len(eval_rows) == first_split_manifest["split_counts"]["eval"]
    assert len(train_rows) + len(eval_rows) == first.episode_count
    assert {row["split"] for row in root_rows} == {"train", "eval"}

    for split_name in ("train", "eval"):
        split_root = first.export_root / split_name
        assert (split_root / "episodes.jsonl").exists()
        assert (split_root / "export_manifest.json").exists()
        scoped_manifest = load_json(split_root / "export_manifest.json")
        assert scoped_manifest["format"] == "split_jsonl"
        assert scoped_manifest["split"] == split_name
        assert scoped_manifest["split_ratio"] == 0.5
        assert scoped_manifest["split_seed"] == 2
        assert scoped_manifest["warnings"] == []
