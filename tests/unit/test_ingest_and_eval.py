"""Unit-style coverage for ingest and evaluation services."""

from __future__ import annotations

from pathlib import Path

from packages.eval_runner.service import compare_runs, run_evaluation
from packages.ingest.service import ingest_dataset


def test_ingest_libero_and_rosbag_configs() -> None:
    libero = ingest_dataset("configs/datasets/libero_debug.yaml")
    rosbag = ingest_dataset("configs/datasets/softrobotics_rosbag.yaml")

    assert libero.dataset_id == "libero_debug_v1"
    assert libero.episode_count == 3
    assert Path(libero.manifest_path).exists()

    assert rosbag.dataset_id == "softrobotics_rosbag_v1"
    assert rosbag.episode_count == 2
    assert Path(rosbag.manifest_path).exists()


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
