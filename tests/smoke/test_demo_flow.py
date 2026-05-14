"""Smoke tests for the MVP demo flow."""

from __future__ import annotations

from pathlib import Path

from packages.analysis.service import analyze_run
from packages.eval_runner.service import run_evaluation
from packages.ingest.service import ingest_dataset
from packages.replay.service import build_replay_artifacts
from packages.reporting.service import build_report


def test_end_to_end_demo_flow() -> None:
    ingest_dataset("configs/datasets/libero_debug.yaml")
    ingest_dataset("configs/datasets/softrobotics_rosbag.yaml")

    run_evaluation("configs/eval/libero_cached_eval.yaml")
    analyze_run("outputs/runs/libero_cached_eval", "configs/eval/failure_taxonomy_v0.yaml")
    build_replay_artifacts("outputs/runs/libero_cached_eval", top_k=3)
    report_path = build_report("outputs/runs/libero_cached_eval")

    assert Path("outputs/datasets/libero_debug_v1/dataset_manifest.json").exists()
    assert Path("outputs/datasets/softrobotics_rosbag_v1/dataset_manifest.json").exists()
    assert Path("outputs/runs/libero_cached_eval/run.json").exists()
    assert Path("outputs/runs/libero_cached_eval/analysis.json").exists()
    assert Path("outputs/runs/libero_cached_eval/replays").exists()
    assert report_path.exists()
