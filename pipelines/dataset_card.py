"""CLI entry point for dataset card generation."""

from __future__ import annotations

import argparse
import json

from packages.reporting.dataset_card import build_dataset_card


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a dataset card from normalized dataset artifacts.")
    parser.add_argument("--dataset", required=True, help="Path to the normalized dataset root.")
    args = parser.parse_args()

    result = build_dataset_card(args.dataset)
    print(
        json.dumps(
            {
                "dataset_id": result.dataset_id,
                "dataset_root": str(result.dataset_root),
                "markdown_path": str(result.markdown_path),
                "json_path": str(result.json_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
