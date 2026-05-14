# Module Boundaries

## One-Line Positioning

Build a software-only multimodal data and evaluation loop for VLA and robot-learning workflows, centered on a unified episode representation and designed to support ingest, evaluation, replay, failure analysis, and rosbag-compatible case studies.

## Core Modules

### 1. Data ingest and time alignment

- Inputs: `rosbag/rosbag2`, benchmark trajectories, simulator logs, media files, state/action logs.
- Responsibilities: parsing, timestamp alignment, field validation, task metadata extraction, light cleaning.
- Out of scope: training, model inference, metric computation.

### 2. Unified episode schema and run registry

- Canonical records: `episode`, `run`, `artifact`, `report`.
- Canonical fields: `instruction`, `observation refs`, `action`, `robot state`, `timestamp`, `task_id`, `source`, optional `plan_trace`.
- Out of scope: front-end concerns and raw media transformation pipelines.

### 3. Policy adapter layer

- Responsibilities: expose one interface over cached policy outputs, baseline controllers, or external VLA wrappers.
- Interface sketch: `reset()`, `act(obs)`, optional `plan(ctx)`.
- Out of scope: benchmark orchestration and metrics.

### 4. Rollout and evaluation runner

- Responsibilities: run offline replay checks, benchmark slices, and software-only rosbag-backed evaluations.
- Outputs: run manifest, episode summaries, aggregate metrics, artifact links.
- Out of scope: manual annotation workflows and deep root-cause analysis.

### 5. Failure analysis and replay

- Responsibilities: filter failures, replay episodes, inspect keyframes, assign lightweight failure tags.
- Starter taxonomy: perception miss, grounding mismatch, planning error, control mismatch, environment mismatch.
- Out of scope: raw ingest and online execution.

### 6. Reporting and comparison

- Responsibilities: generate Markdown or HTML reports, compare runs, rank failure cases, summarize regression slices.
- Out of scope: data conversion and job execution.

### 7. Rosbag or simulator compatibility harness

- Responsibilities: prove the same schema and analysis path also work on ROS-compatible or simulator-generated logs.
- Out of scope: replacing a robot control stack or shipping a live demo.

## Minimal Architecture

### Storage

- Normalized episode folders with JSON, Parquet, JSONL, and media references.
- `SQLite` registry for run metadata and artifact lookup.

### Execution

- `ingest` CLI for normalization.
- `eval` CLI for benchmark or replay execution.
- `analyze` CLI for failure slicing and tagging.
- `report` CLI for report generation.

### Outputs

Every run should emit:

- `config.yaml`
- `run.json`
- `metrics.json`
- `episodes.jsonl`
- `failure_tags.jsonl`
- `report.md`

## Design Principles

1. Episode-first, versioned artifacts.
2. Thin adapters over benchmark rewrites.
3. Failure observability as a first-class output.

## Scope Discipline

- No training loop.
- No GPU requirement.
- No real-robot dependency.
- No heavy dashboard work unless the rest is already solid.
