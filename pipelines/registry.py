"""CLI entry point for printing the local registry snapshot."""

from __future__ import annotations

import json

from packages.registry.service import registry_snapshot


def main() -> None:
    print(json.dumps(registry_snapshot(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
