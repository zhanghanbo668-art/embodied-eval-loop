"""Export normalized episodes into learning-dataset style artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from packages.common.config import display_path, resolve_repo_path
from packages.common.io import dump_json, dump_jsonl, ensure_dir, load_json, load_jsonl


@dataclass(slots=True)
class ExportResult:
    """Summary for one dataset export."""

    dataset_id: str
    export_root: Path
    format: str
    episode_count: int
    manifest_path: Path
    index_path: Path
    optional_artifacts: dict[str, str]


def export_dataset(
    dataset_root: str | Path,
    output_root: str | Path | None = None,
    export_format: str = "learning_jsonl",
) -> ExportResult:
    """Export a normalized dataset into a learning-dataset view.

    Supported formats:

    - `learning_jsonl`: portable JSONL index plus per-episode stream references.
    - `parquet`: same index plus tabular action/state Parquet files when engines are available.
    - `lerobot_stub`: JSON metadata compatible with a future LeRobot-style adapter.
    - `hdf5_stub`: JSON manifest describing an HDF5-ready packing contract.
    """
    root = resolve_repo_path(dataset_root)
    manifest = load_json(root / "dataset_manifest.json")
    if not isinstance(manifest, dict):
        raise ValueError(f"Invalid dataset manifest: {root / 'dataset_manifest.json'}")
    dataset_id = str(manifest.get("dataset_id", root.name))
    target = ensure_dir(resolve_repo_path(output_root) if output_root else root / "exports" / export_format)
    episodes = _episode_export_rows(root, manifest)

    index_path = dump_jsonl(target / "episodes.jsonl", episodes)
    optional_artifacts: dict[str, str] = {}
    if export_format == "parquet":
        optional_artifacts.update(_write_parquet_exports(target, episodes))
    elif export_format == "lerobot_stub":
        optional_artifacts["lerobot_metadata"] = str(_write_lerobot_stub(target, dataset_id, episodes))
    elif export_format == "hdf5_stub":
        optional_artifacts["hdf5_metadata"] = str(_write_hdf5_stub(target, dataset_id, episodes))
    elif export_format != "learning_jsonl":
        raise ValueError(f"Unsupported export format: {export_format}")

    export_manifest = {
        "dataset_id": dataset_id,
        "source_dataset_root": display_path(root),
        "format": export_format,
        "episode_count": len(episodes),
        "index_path": display_path(index_path),
        "optional_artifacts": {
            key: display_path(value)
            for key, value in optional_artifacts.items()
        },
        "schema": {
            "episode_id": "string",
            "task_id": "string",
            "instruction": "string",
            "action_stream": "path",
            "state_stream": "path",
            "observation_streams": "mapping[path]",
            "quality": "mapping|null",
        },
    }
    manifest_path = dump_json(target / "export_manifest.json", export_manifest)
    return ExportResult(
        dataset_id=dataset_id,
        export_root=target,
        format=export_format,
        episode_count=len(episodes),
        manifest_path=manifest_path,
        index_path=index_path,
        optional_artifacts=optional_artifacts,
    )


def _episode_export_rows(dataset_root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for episode in manifest.get("episodes", []):
        if not isinstance(episode, dict):
            continue
        episode_root = _episode_root(dataset_root, episode)
        action_ref = episode.get("action_ref") or {}
        state_ref = episode.get("state_ref") or {}
        observations = {
            str(ref.get("description") or Path(str(ref.get("path"))).stem): display_path(episode_root / str(ref.get("path")))
            for ref in episode.get("observation_refs", [])
            if isinstance(ref, dict) and ref.get("path")
        }
        quality_path = episode_root / "quality.json"
        rows.append(
            {
                "episode_id": episode.get("episode_id"),
                "dataset_id": episode.get("dataset_id"),
                "task_id": episode.get("task_id"),
                "instruction": episode.get("instruction"),
                "source_type": episode.get("source_type"),
                "num_steps": episode.get("num_steps"),
                "start_time_ms": episode.get("start_time_ms"),
                "end_time_ms": episode.get("end_time_ms"),
                "action_stream": display_path(episode_root / str(action_ref.get("path"))) if action_ref.get("path") else None,
                "state_stream": display_path(episode_root / str(state_ref.get("path"))) if state_ref.get("path") else None,
                "observation_streams": observations,
                "events": display_path(episode_root / "events.jsonl"),
                "plan_trace": display_path(episode_root / "plan_trace.jsonl"),
                "quality": load_json(quality_path) if quality_path.exists() else None,
                "metadata": episode.get("metadata", {}),
            }
        )
    return rows


def _episode_root(dataset_root: Path, episode: dict[str, Any]) -> Path:
    artifact_root = episode.get("artifact_root")
    if artifact_root:
        candidate = Path(str(artifact_root))
        return candidate if candidate.is_absolute() else resolve_repo_path(candidate)
    return dataset_root / "episodes" / str(episode["episode_id"])


def _write_parquet_exports(target: Path, episodes: list[dict[str, Any]]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    action_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    for episode in episodes:
        action_rows.extend(_stream_rows(episode, "action_stream"))
        state_rows.extend(_stream_rows(episode, "state_stream"))

    artifacts["actions_jsonl"] = str(dump_jsonl(target / "actions.jsonl", action_rows))
    artifacts["states_jsonl"] = str(dump_jsonl(target / "states.jsonl", state_rows))
    try:
        if action_rows:
            action_path = target / "actions.parquet"
            pd.DataFrame(action_rows).to_parquet(action_path, index=False)
            artifacts["actions_parquet"] = str(action_path)
        if state_rows:
            state_path = target / "states.parquet"
            pd.DataFrame(state_rows).to_parquet(state_path, index=False)
            artifacts["states_parquet"] = str(state_path)
    except (ImportError, ValueError) as exc:
        artifacts["parquet_warning"] = f"Parquet engine unavailable: {exc}"
    return artifacts


def _stream_rows(episode: dict[str, Any], stream_key: str) -> list[dict[str, Any]]:
    path = episode.get(stream_key)
    if not path:
        return []
    stream_path = resolve_repo_path(path)
    if not stream_path.exists():
        return []
    records = load_json(stream_path)
    if not isinstance(records, list):
        return []
    rows: list[dict[str, Any]] = []
    for record in records:
        if isinstance(record, dict):
            rows.append(
                {
                    "episode_id": episode.get("episode_id"),
                    "task_id": episode.get("task_id"),
                    **record,
                }
            )
    return rows


def _write_lerobot_stub(target: Path, dataset_id: str, episodes: list[dict[str, Any]]) -> Path:
    metadata = {
        "codebase": "embodied-eval-loop",
        "dataset_id": dataset_id,
        "episode_count": len(episodes),
        "features": {
            "observation": "external stream references",
            "action": "action_stream",
            "state": "state_stream",
            "language_instruction": "instruction",
        },
        "episodes": [
            {
                "episode_id": episode.get("episode_id"),
                "task_id": episode.get("task_id"),
                "num_steps": episode.get("num_steps"),
            }
            for episode in episodes
        ],
    }
    return dump_json(target / "lerobot_dataset.json", metadata)


def _write_hdf5_stub(target: Path, dataset_id: str, episodes: list[dict[str, Any]]) -> Path:
    metadata = {
        "dataset_id": dataset_id,
        "container": "hdf5_stub",
        "intended_layout": {
            "/episodes/<episode_id>/action": "float or structured action tensor",
            "/episodes/<episode_id>/state": "state tensor",
            "/episodes/<episode_id>/observation/rgb": "external media ref or packed tensor",
            "/episodes/<episode_id>/instruction": "utf-8 string",
            "/episodes/<episode_id>/quality": "json-serializable attributes",
        },
        "episodes": [
            {
                "episode_id": episode.get("episode_id"),
                "num_steps": episode.get("num_steps"),
                "task_id": episode.get("task_id"),
            }
            for episode in episodes
        ],
        "note": "This stub defines a stable HDF5 packing contract before adding a binary writer dependency.",
    }
    return dump_json(target / "hdf5_dataset.json", metadata)
