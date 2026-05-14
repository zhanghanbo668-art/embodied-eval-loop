"""CLI entry point for learning-dataset exports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.exporters import export_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a normalized dataset into a learning-dataset view.")
    parser.add_argument("--dataset", required=True, help="Path to a normalized dataset root.")
    parser.add_argument(
        "--format",
        default="learning_jsonl",
        choices=["learning_jsonl", "parquet", "lerobot_stub", "hdf5_stub"],
        help="Export format.",
    )
    parser.add_argument("--output", help="Optional output root.")
    args = parser.parse_args()

    result = export_dataset(Path(args.dataset), Path(args.output) if args.output else None, args.format)
    payload = {
        "dataset_id": result.dataset_id,
        "export_root": str(result.export_root),
        "format": result.format,
        "episode_count": result.episode_count,
        "manifest_path": str(result.manifest_path),
        "index_path": str(result.index_path),
        "optional_artifacts": result.optional_artifacts,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
