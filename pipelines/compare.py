"""CLI entry point for comparison cases."""

from __future__ import annotations

import argparse
import json

from packages.reporting.comparison import build_comparison_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a comparison report from a case config.")
    parser.add_argument("--config", required=True, help="Path to the comparison case YAML config.")
    args = parser.parse_args()

    result = build_comparison_report(args.config)
    print(json.dumps({"comparison_report": str(result)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
