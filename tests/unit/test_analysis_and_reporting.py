"""Unit-style coverage for analysis and report generation."""

from __future__ import annotations

from pathlib import Path

from packages.analysis.service import analyze_run
from packages.ingest.service import ingest_dataset
from packages.eval_runner.service import run_evaluation
from packages.replay.service import build_replay_artifacts
from packages.reporting.comparison import build_comparison_report
from packages.reporting.dataset_card import build_dataset_card
from packages.reporting.gate import run_regression_gate
from packages.reporting.service import build_report
from scripts.create_rosbag2_sqlite_fixture import main as create_rosbag2_sqlite_fixture


def test_analysis_replay_and_reports() -> None:
    create_rosbag2_sqlite_fixture()
    ingest_dataset("configs/datasets/libero_debug.yaml")
    ingest_dataset("configs/datasets/softrobotics_rosbag_sqlite.yaml")
    run_evaluation("configs/eval/libero_cached_eval.yaml")
    run_evaluation("configs/eval/libero_perturbed_eval.yaml")

    analysis = analyze_run("outputs/runs/libero_cached_eval", "configs/eval/failure_taxonomy_v0.yaml")
    replay = build_replay_artifacts("outputs/runs/libero_cached_eval", top_k=2)
    report_path = build_report("outputs/runs/libero_cached_eval")
    comparison_path = build_comparison_report("configs/cases/libero_comparison_case.yaml")
    dataset_card = build_dataset_card("outputs/datasets/softrobotics_rosbag_sqlite_v1")
    pass_gate = run_regression_gate("configs/cases/libero_regression_gate_pass.yaml")
    fail_gate = run_regression_gate("configs/cases/libero_regression_gate_fail.yaml")

    assert analysis.failure_count >= 1
    assert Path(analysis.failure_tags_path).exists()
    assert replay["replay_count"] >= 1
    assert report_path.exists()
    assert comparison_path.exists()
    assert dataset_card.markdown_path.exists()
    assert dataset_card.json_path.exists()
    assert pass_gate.status == "pass"
    assert pass_gate.failed_count == 0
    assert pass_gate.report_path.exists()
    assert fail_gate.status == "fail"
    assert fail_gate.failed_count >= 1
    assert fail_gate.json_path.exists()
