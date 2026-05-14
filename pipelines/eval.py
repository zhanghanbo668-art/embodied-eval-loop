"""CLI entry point for evaluation runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.eval_runner.service import run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one evaluation config.")
    parser.add_argument("--config", required=True, help="Path to eval YAML config.")
    args = parser.parse_args()

    result = run_evaluation(Path(args.config))
    payload = {
        "run_root": str(result.run_root),
        "episode_count": result.episode_count,
        "metrics": result.metrics,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
