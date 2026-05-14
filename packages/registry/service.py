"""Simple SQLite-backed local registry."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from packages.common.config import display_path, resolve_repo_path
from packages.common.io import dump_json

DB_PATH = resolve_repo_path("outputs/registry.sqlite3")
SNAPSHOT_PATH = resolve_repo_path("outputs/registry_snapshot.json")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    _ensure_schema(connection)
    return connection


def _ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            dataset_id TEXT PRIMARY KEY,
            source_type TEXT NOT NULL,
            source_root TEXT NOT NULL,
            output_root TEXT NOT NULL,
            episode_count INTEGER NOT NULL,
            manifest_path TEXT NOT NULL,
            episodes_path TEXT
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_name TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            mode TEXT NOT NULL,
            policy_name TEXT NOT NULL,
            policy_adapter TEXT NOT NULL,
            output_root TEXT NOT NULL,
            episode_count INTEGER NOT NULL,
            metrics_path TEXT NOT NULL,
            report_path TEXT
        );

        CREATE TABLE IF NOT EXISTS comparisons (
            case_name TEXT PRIMARY KEY,
            baseline_run TEXT NOT NULL,
            candidate_run TEXT NOT NULL,
            output_root TEXT NOT NULL,
            report_path TEXT NOT NULL
        );
        """
    )
    _ensure_column(connection, "datasets", "episodes_path", "TEXT")
    connection.commit()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    """Add a missing column to an existing table for lightweight schema migration."""
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {str(row[1]) for row in rows}
    if column not in existing:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def register_dataset(
    *,
    dataset_id: str,
    source_type: str,
    source_root: str,
    output_root: str,
    episode_count: int,
    manifest_path: str,
    episodes_path: str | None = None,
) -> None:
    """Upsert one dataset record into the local registry."""
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO datasets(dataset_id, source_type, source_root, output_root, episode_count, manifest_path, episodes_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id) DO UPDATE SET
                source_type=excluded.source_type,
                source_root=excluded.source_root,
                output_root=excluded.output_root,
                episode_count=excluded.episode_count,
                manifest_path=excluded.manifest_path,
                episodes_path=excluded.episodes_path
            """,
            (
                dataset_id,
                source_type,
                display_path(source_root),
                display_path(output_root),
                episode_count,
                display_path(manifest_path),
                display_path(episodes_path) if episodes_path else None,
            ),
        )
        connection.commit()
    export_registry_snapshot()


def register_run(
    *,
    run_name: str,
    dataset_id: str,
    mode: str,
    policy_name: str,
    policy_adapter: str,
    output_root: str,
    episode_count: int,
    metrics_path: str,
    report_path: str | None = None,
) -> None:
    """Upsert one run record into the local registry."""
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO runs(run_name, dataset_id, mode, policy_name, policy_adapter, output_root, episode_count, metrics_path, report_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_name) DO UPDATE SET
                dataset_id=excluded.dataset_id,
                mode=excluded.mode,
                policy_name=excluded.policy_name,
                policy_adapter=excluded.policy_adapter,
                output_root=excluded.output_root,
                episode_count=excluded.episode_count,
                metrics_path=excluded.metrics_path,
                report_path=excluded.report_path
            """,
            (
                run_name,
                dataset_id,
                mode,
                policy_name,
                policy_adapter,
                display_path(output_root),
                episode_count,
                display_path(metrics_path),
                display_path(report_path) if report_path else None,
            ),
        )
        connection.commit()
    export_registry_snapshot()


def attach_run_report(*, run_name: str, report_path: str) -> None:
    """Attach or update the generated report path for a run."""
    with _connect() as connection:
        connection.execute(
            "UPDATE runs SET report_path = ? WHERE run_name = ?",
            (display_path(report_path), run_name),
        )
        connection.commit()
    export_registry_snapshot()


def register_comparison(
    *,
    case_name: str,
    baseline_run: str,
    candidate_run: str,
    output_root: str,
    report_path: str,
) -> None:
    """Upsert one comparison record into the local registry."""
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO comparisons(case_name, baseline_run, candidate_run, output_root, report_path)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(case_name) DO UPDATE SET
                baseline_run=excluded.baseline_run,
                candidate_run=excluded.candidate_run,
                output_root=excluded.output_root,
                report_path=excluded.report_path
            """,
            (
                case_name,
                display_path(baseline_run),
                display_path(candidate_run),
                display_path(output_root),
                display_path(report_path),
            ),
        )
        connection.commit()
    export_registry_snapshot()


def registry_snapshot() -> dict[str, list[dict[str, Any]]]:
    """Return a JSON-serializable snapshot of the registry contents."""
    snapshot: dict[str, list[dict[str, Any]]] = {}
    with _connect() as connection:
        for table in ("datasets", "runs", "comparisons"):
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            snapshot[table] = [dict(row) for row in rows]
    return snapshot


def export_registry_snapshot() -> Path:
    """Write the registry snapshot to disk for demo and inspection use."""
    return dump_json(SNAPSHOT_PATH, registry_snapshot())
