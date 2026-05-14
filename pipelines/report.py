"""CLI entry point for report generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.reporting.service import build_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a report for a completed run.")
    parser.add_argument("--run", required=True, help="Path to the run root.")
    args = parser.parse_args()

    result = build_report(Path(args.run))
    print(json.dumps({"report_path": str(result)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
