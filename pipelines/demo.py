"""Run the full MVP demo on sample artifacts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json

from packages.analysis.service import analyze_run
from packages.eval_runner.service import run_evaluation
from packages.ingest.service import ingest_dataset
from packages.replay.service import build_replay_artifacts
from packages.reporting.comparison import build_comparison_report
from packages.reporting.service import build_report


def main() -> None:
    steps = [
        ("ingest_libero", lambda: ingest_dataset("configs/datasets/libero_debug.yaml")),
        ("ingest_rosbag", lambda: ingest_dataset("configs/datasets/softrobotics_rosbag.yaml")),
        ("eval_cached", lambda: run_evaluation("configs/eval/libero_cached_eval.yaml")),
        ("eval_perturbed", lambda: run_evaluation("configs/eval/libero_perturbed_eval.yaml")),
        ("eval_rosbag", lambda: run_evaluation("configs/eval/softrobotics_rosbag_eval.yaml")),
        (
            "analyze_cached",
            lambda: analyze_run(
                "outputs/runs/libero_cached_eval",
                "configs/eval/failure_taxonomy_v0.yaml",
            ),
        ),
        (
            "analyze_perturbed",
            lambda: analyze_run(
                "outputs/runs/libero_perturbed_eval",
                "configs/eval/failure_taxonomy_v0.yaml",
            ),
        ),
        (
            "analyze_rosbag",
            lambda: analyze_run(
                "outputs/runs/softrobotics_rosbag_eval",
                "configs/eval/failure_taxonomy_v0.yaml",
            ),
        ),
        ("replay_cached", lambda: build_replay_artifacts("outputs/runs/libero_cached_eval", top_k=5)),
        ("replay_perturbed", lambda: build_replay_artifacts("outputs/runs/libero_perturbed_eval", top_k=5)),
        ("replay_rosbag", lambda: build_replay_artifacts("outputs/runs/softrobotics_rosbag_eval", top_k=5)),
        ("report_cached", lambda: build_report("outputs/runs/libero_cached_eval")),
        ("report_perturbed", lambda: build_report("outputs/runs/libero_perturbed_eval")),
        ("report_rosbag", lambda: build_report("outputs/runs/softrobotics_rosbag_eval")),
        (
            "compare_libero",
            lambda: build_comparison_report("configs/cases/libero_comparison_case.yaml"),
        ),
    ]

    results = {}
    for name, fn in steps:
        outcome = fn()
        if hasattr(outcome, "model_dump"):
            results[name] = outcome.model_dump(mode="json")
        elif is_dataclass(outcome):
            payload = asdict(outcome)
            for key, value in list(payload.items()):
                if hasattr(value, "as_posix"):
                    payload[key] = str(value)
            results[name] = payload
        elif isinstance(outcome, dict):
            results[name] = outcome
        elif hasattr(outcome, "as_posix"):
            results[name] = str(outcome)
        else:
            results[name] = str(outcome)
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
