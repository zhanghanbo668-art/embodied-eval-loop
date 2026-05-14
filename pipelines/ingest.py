"""CLI entry point for dataset ingest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.ingest.service import ingest_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a dataset config into normalized artifacts.")
    parser.add_argument("--config", required=True, help="Path to dataset YAML config.")
    args = parser.parse_args()

    result = ingest_dataset(Path(args.config))
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
