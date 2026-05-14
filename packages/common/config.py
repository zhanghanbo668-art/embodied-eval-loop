"""Config helpers."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Return the repository root from the current file location."""
    return Path(__file__).resolve().parents[2]


def resolve_repo_path(path: str | Path) -> Path:
    """Resolve *path* relative to the repository root when needed."""
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root() / candidate


def display_path(path: str | Path) -> str:
    """Return a stable repo-relative display path when possible."""
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()
    root = repo_root()
    try:
        relative = os.path.relpath(str(candidate), str(root))
        return Path(relative).as_posix()
    except ValueError:
        return candidate.as_posix()
    except OSError:
        return candidate.as_posix()
