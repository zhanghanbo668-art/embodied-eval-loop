# Case Study: From ROSBag2 Logs to Embodied Policy Evaluation

## Summary

This case study shows the full purpose of the project: convert heterogeneous embodied-data sources into one reproducible evaluation and failure-analysis workflow.

The stack now covers three source styles:

- a benchmark-style LIBERO debug slice;
- a ROSBag2-style metadata fixture;
- a ROSBag2 SQLite `.db3` fixture using standard `topics` and `messages` tables.
- optional CDR-serialized ROSBag2 sqlite3 and MCAP fixtures generated through `rosbags`.

All three are mapped into the same episode artifact contract and can flow through validation, export, replay, failure analysis, and reporting.

## Research Question

Can benchmark trajectories and ROSBag2 robot logs be turned into one evaluation/control-plane workflow that produces validated learning datasets and failure-oriented reports without requiring online robot execution?

This project answers yes at the infrastructure level.

It does not claim a new model. Its contribution is the software layer that makes embodied policy experiments more reproducible, diagnosable, and comparable.

## End-to-End Reproduction

From the repository root:

```bash
python scripts/create_rosbag2_sqlite_fixture.py
python scripts/create_rosbag2_cdr_fixture.py
python -m pipelines.demo
python scripts/run_smoke_checks.py
python -m pipelines.validate_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format lerobot_stub
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format hdf5_stub
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format split_jsonl --split-ratio 0.5 --split-seed 2
```

These commands generate:

- normalized dataset artifacts;
- quality reports;
- run metrics;
- replay summaries;
- Markdown and HTML reports;
- a LeRobot-style export metadata stub;
- an HDF5-ready packing-contract stub.
- a deterministic train/eval split manifest for release-oriented learning-dataset handoff;
- CDR-decoded ROSBag2 sqlite3 and MCAP normalized datasets when the optional `rosbags` dependency is installed.

## Inputs

### Benchmark Slice

Config:

```text
configs/datasets/libero_debug.yaml
```

Sample input:

```text
data/libero/debug/episodes.json
```

### ROSBag2 Metadata Fixture

Config:

```text
configs/datasets/softrobotics_rosbag.yaml
```

Sample input:

```text
data/rosbags/softrobotics_case/metadata.json
```

### ROSBag2 SQLite Fixture

Config:

```text
configs/datasets/softrobotics_rosbag_sqlite.yaml
```

Generated input:

```text
data/rosbags/softrobotics_sqlite_case/rosbag2_fixture.db3
```

The SQLite fixture uses the standard ROSBag2 `topics` and `messages` schema and stores JSON payloads so the entire workflow stays software-only and CI-friendly.

### ROSBag2 CDR / MCAP Fixtures

Configs:

```text
configs/datasets/softrobotics_rosbag_cdr.yaml
configs/datasets/softrobotics_rosbag_mcap.yaml
```

Generated inputs:

```text
data/rosbags/softrobotics_cdr_case/
data/rosbags/softrobotics_mcap_case/
```

These fixtures store real CDR-serialized ROS messages and are read through the optional pure-Python `rosbags` backend. The sqlite3 and MCAP variants exercise the same reader interface and normalize into the same episode contract.

## Unified Artifact Contract

Each normalized episode is written as:

```text
outputs/datasets/<dataset_id>/episodes/<episode_id>/
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

At the dataset level, the stack also writes:

```text
dataset_manifest.json
episodes.jsonl
quality_report.json
validation_report.json
```

This makes ingest outputs directly usable by downstream evaluation, replay, export, and reporting commands.

## What the Current Runs Show

### Benchmark Comparison Insight

The LIBERO comparison case contrasts:

```text
outputs/runs/libero_cached_eval
outputs/runs/libero_perturbed_eval
```

The degraded run shows:

- lower success rate;
- lower completion ratio;
- higher action latency;
- representative failures tagged as control or planning-related.

This is the policy-side signal: behavior regressed under controlled perturbation.

### ROSBag2 Ingest Insight

The ROSBag2 SQLite ingest path shows:

- topic discovery from actual SQLite storage tables;
- episode slicing from marker messages;
- aligned `rgb`, `state`, `action`, `pressure`, and `instruction` streams;
- per-episode `quality.json`;
- dataset-level `quality_report.json`;
- successful validation via `pipelines.validate_dataset`.

This is the data-side signal: the stack can prove whether a failure should be interpreted as a policy issue or a data-quality issue.

### Why the Combination Matters

The important engineering point is not just that each path runs independently. The important point is that both paths now terminate in the same contracts:

- normalized episodes;
- quality evidence;
- replayable summaries;
- comparison-ready reports.

That means policy regressions and ingest-quality problems can be analyzed in one language instead of two disconnected toolchains.

## Representative Failure Story

The strongest explanation chain in the current demo is:

1. the perturbed benchmark run regresses in success and latency;
2. the comparison report surfaces a representative failed episode;
3. the replay summary shows keyframes, action preview, final progress, and failure tags;
4. the ROSBag2 ingest path shows how aligned streams and quality evidence would let the same tooling separate policy failure from logging failure.

This is exactly the kind of infrastructure a research lab needs when experiments start to accumulate multiple data sources and multiple policy variants.

## Engineering Value

This case study now demonstrates:

- benchmark ingest;
- ROSBag2 metadata ingest;
- ROSBag2 SQLite storage ingest;
- CDR-serialized ROSBag2 sqlite3 and MCAP ingest through an optional backend;
- topic discovery and timestamp alignment;
- quality reporting and validation;
- learning-dataset export surfaces;
- reproducible train/eval split export for downstream learning workflows;
- failure replay and comparison reporting.

That makes the project substantially stronger than a simple benchmark wrapper or replay demo.

## Current Boundaries

The lightweight SQLite reader currently decodes JSON payload fixtures and preserves raw metadata for unknown binary ROS messages. The optional `rosbags` reader covers CDR-deserialized sqlite3 and MCAP fixtures for the common message families used here. Broader custom message registration plus richer LeRobot/HDF5 exports are the main next steps toward a more production-like embodied data stack.
