"""Pydantic models shared across the MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ArtifactRef(BaseModel):
    """Reference to a generated or source artifact on disk."""

    kind: str
    path: str
    description: str | None = None


class EpisodeRecord(BaseModel):
    """Normalized episode-level record used across ingest and evaluation."""

    episode_id: str
    dataset_id: str
    task_id: str
    instruction: str
    source_type: Literal["libero", "rosbag2", "unknown"] = "unknown"
    source_uri: str
    artifact_root: str | None = None
    num_steps: int = 0
    start_time_ms: int = 0
    end_time_ms: int = 0
    observation_refs: list[ArtifactRef] = Field(default_factory=list)
    action_ref: ArtifactRef | None = None
    state_ref: ArtifactRef | None = None
    events_ref: ArtifactRef | None = None
    plan_trace_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetManifest(BaseModel):
    """Dataset-level manifest produced by ingest."""

    dataset_id: str
    source_type: str
    source_root: str
    output_root: str
    episode_count: int
    episodes: list[EpisodeRecord]
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    """Run-level metadata for one evaluation job."""

    run_name: str
    mode: str
    dataset_id: str
    policy_name: str
    policy_adapter: str
    output_root: str
    episode_count: int
    source_dataset_manifest: str | None = None
    source_policy_config: str | None = None
    taxonomy_config: str | None = None
    config_hash: str | None = None
    created_at: str | None = None
    artifact_root: str | None = None
    metrics_ref: str | None = None
    status: Literal["pending", "running", "completed", "failed"] = "completed"


class FailureTag(BaseModel):
    """Tagged failure for one episode."""

    run_id: str
    episode_id: str
    tag: str
    confidence: float = 1.0
    evidence: dict[str, Any] = Field(default_factory=dict)
    annotator: str = "auto"


class IngestResult(BaseModel):
    """Summary returned by ingest entry points."""

    dataset_id: str
    source_type: str
    source_root: str
    output_root: str
    episode_count: int
    manifest_path: str
    episodes_path: str

    @property
    def output_path(self) -> Path:
        """Convenience path object for callers that want a Path."""
        return Path(self.output_root)
