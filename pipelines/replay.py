"""CLI entry point for replay artifact generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.replay.service import build_replay_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Build replay artifacts for a run.")
    parser.add_argument("--run", required=True, help="Path to the run root.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of episodes to export.")
    args = parser.parse_args()

    result = build_replay_artifacts(Path(args.run), top_k=args.top_k)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
