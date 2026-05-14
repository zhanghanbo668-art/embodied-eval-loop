"""CLI entry point for run analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.analysis.service import analyze_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a completed evaluation run.")
    parser.add_argument("--run", required=True, help="Path to the run root.")
    parser.add_argument("--taxonomy", help="Optional path to taxonomy YAML config.")
    args = parser.parse_args()

    result = analyze_run(Path(args.run), Path(args.taxonomy) if args.taxonomy else None)
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
