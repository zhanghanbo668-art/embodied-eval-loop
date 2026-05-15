# V1 Goal: ROSBag2-to-Learning-Dataset Conversion

## Objective

Upgrade the current embodied evaluation stack from a metadata-backed ROS-compatible demo into a stronger v1 system that can convert ROSBag2-style robot logs into learning-ready, replayable, and evaluation-ready episode datasets.

The goal is not to build a full robotics runtime. The goal is to make raw or semi-raw robot traces usable for embodied policy evaluation.

## Current Implementation Status

Implemented in the current v1 slice:

- ROSBag-style reader abstraction in `packages/adapters_rosbags/reader.py`.
- Metadata-backed reader for CI-friendly ROSBag2-style fixtures.
- SQLite ROSBag2 reader for standard `topics` and `messages` storage tables.
- JSON payload decoding for software-only `.db3` fixtures.
- Raw binary payload preservation in the lightweight SQLite reader.
- Optional `rosbags` backend for CDR-deserialized ROSBag2 sqlite3 and MCAP fixtures.
- Topic discovery for configured ROS aliases such as `rgb`, `state`, `action`, `pressure`, and `instruction`.
- Timestamped message iteration per topic and episode.
- Nearest-neighbor timestamp alignment with configurable tolerance.
- Per-episode `quality.json` files.
- Dataset-level `quality_report.json`.
- Aligned ROS stream artifacts under each episode folder.
- Replay summaries that include ingest quality evidence.
- Run reports that show ingest quality status for ranked failures.
- Dataset validation CLI in `pipelines.validate_dataset`.
- Learning-dataset export CLI in `pipelines.export_dataset`.
- LeRobot-style metadata stub export.
- HDF5-compatible packing-contract stub export.
- Deterministic `split_jsonl` export with reproducible train/eval assignment from `dataset_id`, `episode_id`, and split seed.
- Parquet-if-available action/state export with JSONL fallback.
- Configuration-driven regression gates for baseline-vs-candidate acceptance checks.
- Dataset-card generation for multimodal stream coverage, quality summary, and export/reproducibility metadata.
- GitHub Actions smoke workflow that installs the package, runs `pytest`, generates ROSBag2 SQLite/CDR/MCAP fixtures, ingests them, validates outputs, exports dataset views, and runs smoke checks.

Still future work:

- Broader custom ROS message decoding beyond the common message families used in fixtures.
- Split-aware Parquet and richer release-facing dataset export targets.
- Full LeRobot dataset writer with media tensors.

## One-Line Version

Build a ROSBag2-to-learning-dataset converter that parses robot log topics, aligns multimodal streams, materializes shared episode artifacts, runs quality checks, and connects the resulting dataset to replay, failure analysis, and comparison reports.

## Why This Matters

The current MVP already proves the evaluation loop:

```text
benchmark / ROS-compatible metadata -> shared episode artifacts -> evaluation -> replay -> analysis -> report
```

The next high-value step is to make the ROS side more real:

```text
ROSBag2 logs -> topic parsing -> timestamp alignment -> episode slicing -> learning dataset -> evaluation artifacts
```

This closes the gap between robotics data collection and embodied AI evaluation. It also makes the project stronger as research infrastructure because the stack no longer depends only on curated metadata examples.

## Scope

### In Scope

- ROSBag2-style dataset configuration.
- Topic discovery and topic mapping.
- A reader abstraction that can support:
  - metadata-backed fixtures for CI and development;
  - real ROSBag2 backends when dependencies are available.
- Timestamp normalization across observation, state, action, and instruction streams.
- Episode slicing from explicit markers or configurable fixed windows.
- Per-episode artifact generation:
  - `episode.json`
  - `events.jsonl`
  - `plan_trace.jsonl`
  - `streams/action.json`
  - `streams/state.json`
  - observation stream references
- Quality checks:
  - missing topics
  - stale streams
  - timestamp gaps
  - action/state length mismatch
  - impossible progress or state jumps
- Dataset export hooks for:
  - current JSON / JSONL artifact layout;
  - optional Parquet tables;
  - optional LeRobot-style export later.
- Report integration that surfaces ROS ingest quality issues in replay and failure analysis.

### Out of Scope

- Online robot control.
- Training policies.
- GPU inference.
- Full ROS middleware replacement.
- Heavy video rendering or browser-based replay UI.
- Supporting every ROS message type in the first iteration.

## Target Inputs

Initial topic families:

```text
/camera/color/image_raw
/robot/state
/robot/action
/joint_states
/pressure_sensor
/task_instruction
/episode_marker
```

The implementation should not require all topics. The dataset config should define which topics are required and which are optional.

## Target Output Layout

```text
outputs/datasets/<dataset_id>/
  dataset_manifest.json
  episodes.jsonl
  quality_report.json
  episodes/
    <episode_id>/
      episode.json
      events.jsonl
      plan_trace.jsonl
      replay_stub.json
      quality.json
      streams/
        action.json
        state.json
        rgb.json
        pressure.json
```

## Proposed Architecture

### 1. Reader Layer

Module:

```text
packages/adapters_rosbags/
```

Responsibilities:

- expose a common interface over ROSBag2-style sources;
- return topic metadata and timestamped messages;
- keep optional heavy dependencies isolated.

Interface sketch:

```python
class RosbagReader:
    def topics(self) -> list[TopicInfo]: ...
    def messages(self, topic: str) -> Iterable[TimestampedMessage]: ...
```

### 2. Alignment Layer

Module:

```text
packages/ingest/
```

Responsibilities:

- normalize timestamps;
- align observations, state, and actions by nearest timestamp or fixed tolerance;
- emit event rows and stream artifacts.

### 3. Quality Layer

Module:

```text
packages/analysis/
```

Responsibilities:

- check ingest health before evaluation;
- write `quality.json` per episode;
- write `quality_report.json` per dataset.

### 4. Export Layer

Module:

```text
packages/ingest/
```

Responsibilities:

- keep the existing artifact layout;
- optionally add Parquet export for state/action tables;
- leave LeRobot-style export as a later adapter.

## Milestones

### Milestone 1: Rosbag Reader Abstraction

Deliverables:

- `packages/adapters_rosbags/reader.py`
- metadata-backed fixture reader
- topic metadata model
- timestamped message model
- unit tests for topic discovery and message iteration

Acceptance criteria:

- existing metadata fixture still works;
- reader returns deterministic topic/message records;
- no real ROS install is required for CI.

### Milestone 2: Timestamp Alignment and Episode Slicing

Deliverables:

- alignment helpers for nearest-neighbor stream sync;
- configurable tolerance in dataset YAML;
- episode slicing by marker or fixed window;
- aligned event timeline generation.

Acceptance criteria:

- generated episodes include aligned action/state/observation timestamps;
- stale or missing streams are detected;
- smoke script validates at least one aligned ROS-compatible episode.

### Milestone 3: Quality Reports

Deliverables:

- per-episode `quality.json`;
- dataset-level `quality_report.json`;
- quality issue summaries in run/replay reports.

Acceptance criteria:

- missing topic and stale stream checks are visible in generated reports;
- failure analysis can reference ingest quality evidence.

### Milestone 4: Learning-Dataset Export

Deliverables:

- stable JSON / JSONL dataset export;
- optional Parquet export for tabular action/state streams;
- documented conversion command.

Acceptance criteria:

- one command converts a ROSBag2-style source into a learning-ready dataset folder;
- evaluation, replay, analysis, and report commands work on the converted dataset.

## Updated Demo Story

The v1 demo should show:

1. ingest a benchmark slice;
2. ingest a ROSBag2-style source through the reader abstraction;
3. align multimodal streams into episodes;
4. run quality checks;
5. evaluate a cached or reference policy output;
6. replay a representative failure;
7. generate a report that includes both policy metrics and ingest-quality evidence.

## CV Value

This v1 upgrade strengthens the project from "evaluation scaffold" to "robotics-to-embodied-AI data infrastructure."

Suggested CV framing:

> Extended a software-only embodied evaluation stack with ROSBag2-to-learning-dataset conversion, including topic parsing, timestamp alignment, episode artifact generation, replay validation, and failure-oriented evaluation reports.

## Success Criteria

The v1 is successful when:

- a ROSBag2-style source can be converted with one CLI command;
- the output dataset uses the same episode contract as benchmark data;
- timestamp alignment and quality issues are inspectable;
- downstream eval/replay/report commands work unchanged;
- the README and case study show the full path from ROS logs to evaluation report.
