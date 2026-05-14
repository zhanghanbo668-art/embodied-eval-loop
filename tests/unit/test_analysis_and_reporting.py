"""Unit-style coverage for analysis and report generation."""

from __future__ import annotations

from pathlib import Path

from packages.analysis.service import analyze_run
from packages.ingest.service import ingest_dataset
from packages.eval_runner.service import run_evaluation
from packages.replay.service import build_replay_artifacts
from packages.reporting.comparison import build_comparison_report
from packages.reporting.service import build_report


def test_analysis_replay_and_reports() -> None:
    ingest_dataset("configs/datasets/libero_debug.yaml")
    run_evaluation("configs/eval/libero_cached_eval.yaml")
    run_evaluation("configs/eval/libero_perturbed_eval.yaml")

    analysis = analyze_run("outputs/runs/libero_cached_eval", "configs/eval/failure_taxonomy_v0.yaml")
    replay = build_replay_artifacts("outputs/runs/libero_cached_eval", top_k=2)
    report_path = build_report("outputs/runs/libero_cached_eval")
    comparison_path = build_comparison_report("configs/cases/libero_comparison_case.yaml")

    assert analysis.failure_count >= 1
    assert Path(analysis.failure_tags_path).exists()
    assert replay["replay_count"] >= 1
    assert report_path.exists()
    assert comparison_path.exists()
