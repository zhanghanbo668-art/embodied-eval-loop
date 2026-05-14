"""CLI entry point for normalized dataset validation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.validation import validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a normalized dataset root.")
    parser.add_argument("--dataset", required=True, help="Path to a normalized dataset root.")
    parser.add_argument("--no-write", action="store_true", help="Do not write validation_report.json.")
    args = parser.parse_args()

    result = validate_dataset(Path(args.dataset), write_report=not args.no_write)
    payload = {
        "dataset_root": str(result.dataset_root),
        "status": result.status,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
        "report_path": str(result.report_path),
        "checks": result.checks,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if result.status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
