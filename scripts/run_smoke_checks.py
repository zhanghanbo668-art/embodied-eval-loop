"""Run lightweight smoke checks without requiring pytest."""

from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.analysis.service import analyze_run
from packages.common.io import load_json
from packages.eval_runner.service import compare_runs, run_evaluation
from packages.exporters import export_dataset
from packages.ingest.service import ingest_dataset
from packages.replay.service import build_replay_artifacts
from packages.registry.service import export_registry_snapshot, registry_snapshot
from packages.reporting.comparison import build_comparison_report
from packages.reporting.service import build_report
from packages.validation import validate_dataset
from scripts.create_rosbag2_cdr_fixture import main as create_rosbag2_cdr_fixture
from scripts.create_rosbag2_sqlite_fixture import main as create_rosbag2_sqlite_fixture


def main() -> None:
    create_rosbag2_sqlite_fixture()
    create_rosbag2_cdr_fixture()
    libero = ingest_dataset("configs/datasets/libero_debug.yaml")
    rosbag = ingest_dataset("configs/datasets/softrobotics_rosbag.yaml")
    rosbag_sqlite = ingest_dataset("configs/datasets/softrobotics_rosbag_sqlite.yaml")
    rosbag_cdr = ingest_dataset("configs/datasets/softrobotics_rosbag_cdr.yaml")
    rosbag_mcap = ingest_dataset("configs/datasets/softrobotics_rosbag_mcap.yaml")
    assert libero.episode_count == 3
    assert rosbag.episode_count == 2
    assert rosbag_sqlite.episode_count == 2
    assert rosbag_cdr.episode_count == 2
    assert rosbag_mcap.episode_count == 2
    sqlite_validation = validate_dataset("outputs/datasets/softrobotics_rosbag_sqlite_v1")
    sqlite_export = export_dataset("outputs/datasets/softrobotics_rosbag_sqlite_v1", export_format="lerobot_stub")
    sqlite_hdf5 = export_dataset("outputs/datasets/softrobotics_rosbag_sqlite_v1", export_format="hdf5_stub")

    cached = run_evaluation("configs/eval/libero_cached_eval.yaml")
    perturbed = run_evaluation("configs/eval/libero_perturbed_eval.yaml")
    rosbag_eval = run_evaluation("configs/eval/softrobotics_rosbag_eval.yaml")
    assert cached.metrics["success_rate"] == 0.6667
    assert perturbed.metrics["success_rate"] == 0.3333
    assert rosbag_eval.metrics["episode_count"] == 2

    analysis = analyze_run("outputs/runs/libero_cached_eval", "configs/eval/failure_taxonomy_v0.yaml")
    rosbag_analysis = analyze_run("outputs/runs/softrobotics_rosbag_eval", "configs/eval/failure_taxonomy_v0.yaml")
    replay = build_replay_artifacts("outputs/runs/libero_cached_eval", top_k=2)
    rosbag_replay = build_replay_artifacts("outputs/runs/softrobotics_rosbag_eval", top_k=2)
    report = build_report("outputs/runs/libero_cached_eval")
    rosbag_report = build_report("outputs/runs/softrobotics_rosbag_eval")
    comparison_report = build_comparison_report("configs/cases/libero_comparison_case.yaml")
    comparison = compare_runs("outputs/runs/libero_cached_eval", "outputs/runs/libero_perturbed_eval")
    snapshot = registry_snapshot()
    snapshot_path = export_registry_snapshot()
    episode_bundle = load_json("outputs/datasets/libero_debug_v1/episodes/LIBERO_EP_0001/episode.json")
    rosbag_quality = load_json("outputs/datasets/softrobotics_rosbag_v1/quality_report.json")
    rosbag_episode_quality = load_json("outputs/datasets/softrobotics_rosbag_v1/episodes/ROSBAG_EP_0001/quality.json")
    rosbag_sqlite_quality = load_json("outputs/datasets/softrobotics_rosbag_sqlite_v1/quality_report.json")
    rosbag_cdr_quality = load_json("outputs/datasets/softrobotics_rosbag_cdr_v1/quality_report.json")
    rosbag_mcap_quality = load_json("outputs/datasets/softrobotics_rosbag_mcap_v1/quality_report.json")
    rosbag_replay_summary = load_json("outputs/runs/softrobotics_rosbag_eval/replays/ROSBAG_EP_0002/summary.json")
    run_manifest = load_json("outputs/runs/libero_cached_eval/run.json")
    replay_summary = load_json("outputs/runs/libero_cached_eval/replays/LIBERO_EP_0003/summary.json")

    assert analysis.failure_count >= 1
    assert rosbag_analysis.failure_count >= 1
    assert replay["replay_count"] >= 1
    assert rosbag_replay["replay_count"] >= 1
    assert comparison["delta"]["success_rate"] == -0.3334
    assert Path(report).exists()
    assert Path(rosbag_report).exists()
    assert Path(comparison_report).exists()
    assert Path(snapshot_path).exists()
    assert snapshot["datasets"]
    assert snapshot["runs"]
    assert snapshot["comparisons"]
    assert episode_bundle["events_ref"]["path"] == "events.jsonl"
    assert episode_bundle["plan_trace_ref"]["path"] == "plan_trace.jsonl"
    assert Path("outputs/datasets/libero_debug_v1/episodes/LIBERO_EP_0001/streams/action.json").exists()
    assert rosbag_quality["pass_count"] == 2
    assert rosbag_sqlite_quality["pass_count"] == 2
    assert rosbag_sqlite_quality["episodes"][0]["stream_counts"]["rgb"] == 8
    assert rosbag_cdr_quality["pass_count"] == 2
    assert rosbag_cdr_quality["episodes"][0]["stream_counts"]["rgb"] == 6
    assert rosbag_mcap_quality["pass_count"] == 2
    assert sqlite_validation.status == "pass"
    assert sqlite_export.episode_count == 2
    assert Path(sqlite_export.optional_artifacts["lerobot_metadata"]).exists()
    assert Path(sqlite_hdf5.optional_artifacts["hdf5_metadata"]).exists()
    assert rosbag_episode_quality["reference_stream"] == "rgb"
    assert Path("outputs/datasets/softrobotics_rosbag_v1/episodes/ROSBAG_EP_0001/streams/pressure.json").exists()
    assert rosbag_replay_summary["quality"]["status"] == "pass"
    assert run_manifest["status"] == "completed"
    assert run_manifest["config_hash"]
    assert replay_summary["event_count"] >= 1
    assert replay_summary["plan_segments"]

    print("Smoke checks passed.")


if __name__ == "__main__":
    main()
