"""Small IO helpers used across the MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import yaml


def ensure_dir(path: str | Path) -> Path:
    """Create *path* if needed and return it as a Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file into a dictionary."""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in YAML file: {path}")
    return data


def dump_json(path: str | Path, payload: Any) -> Path:
    """Write a JSON file with stable formatting."""
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, sort_keys=True)
    return target


def dump_jsonl(path: str | Path, records: Iterable[dict[str, Any]]) -> Path:
    """Write iterable *records* as JSONL."""
    target = Path(path)
    ensure_dir(target.parent)
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    return target


def load_json(path: str | Path) -> Any:
    """Read a JSON file."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dictionaries."""
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
