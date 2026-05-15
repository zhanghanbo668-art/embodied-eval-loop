"""CLI entry point for regression gate evaluation."""

from __future__ import annotations

import argparse
import json
import sys

from packages.reporting.gate import run_regression_gate


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a regression gate over baseline and candidate runs.")
    parser.add_argument("--config", required=True, help="Path to the regression gate YAML config.")
    args = parser.parse_args()

    result = run_regression_gate(args.config)
    payload = {
        "case_name": result.case_name,
        "status": result.status,
        "output_root": str(result.output_root),
        "report_path": str(result.report_path),
        "json_path": str(result.json_path),
        "failed_count": result.failed_count,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if result.status != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
