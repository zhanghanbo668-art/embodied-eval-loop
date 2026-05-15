# Embodied Data & Evaluation Stack for VLA Policies

A software-only, CPU-first evaluation stack for embodied AI research. It ingests benchmark trajectories and ROS-compatible logs, normalizes them into shared episode artifacts, and produces reproducible replay, failure analysis, and comparison reports.

This is research infrastructure, not a model-training project or a hardware demo.

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Repository Layout](#repository-layout)
- [Quick Start](#quick-start)
- [Core Workflow](#core-workflow)
- [Shared Episode Artifacts](#shared-episode-artifacts)
- [Command Reference](#command-reference)
- [Validation and Export](#validation-and-export)
- [Reports and Demo Outputs](#reports-and-demo-outputs)
- [Testing and Validation](#testing-and-validation)
- [Research Positioning](#research-positioning)
- [Limitations](#limitations)
- [Roadmap](#roadmap)
- [License](#license)

## Why This Exists

Embodied AI experiments often break at the workflow level. Benchmark trajectories, ROS logs, cached rollouts, replay traces, and analysis scripts tend to live in different formats. That makes it difficult to reproduce runs, inspect failures, compare policies, or explain what changed.

This project turns that workflow into a small, reproducible control plane:

```text
data ingest -> schema normalization -> rollout/eval -> replay/failure analysis -> report -> targeted re-run
```

The goal is to make embodied policy behavior easier to test, diagnose, and communicate.

## Key Features

- Ingests a small benchmark-style LIBERO slice.
- Ingests ROSBag2-style cases through reader backends for metadata fixtures and SQLite `.db3` storage.
- Optionally ingests real CDR-serialized ROSBag2 sqlite3 and MCAP bags through the pure-Python `rosbags` backend.
- Normalizes both sources into a shared episode schema.
- Runs config-driven evaluations using cached or perturbed rollout adapters.
- Produces reproducible run manifests, metrics, config snapshots, and per-episode evaluation artifacts.
- Writes ROS ingest quality reports for missing topics, stale streams, alignment counts, and timestamp gaps.
- Validates normalized datasets before evaluation and exports learning-dataset views.
- Ranks failed episodes and assigns lightweight failure taxonomy tags.
- Generates replay summaries with event timelines, keyframes, action previews, and plan segments.
- Builds Markdown and HTML reports for individual runs and baseline-vs-candidate comparisons.
- Adds configuration-driven regression gates for baseline-vs-candidate acceptance checks.
- Maintains a local SQLite registry and JSON snapshot for datasets, runs, and comparisons.

## Tech Stack

- **Language**: Python 3.12+
- **Schemas**: Pydantic
- **Config**: YAML
- **Reports**: Jinja2 templates, Markdown, static HTML
- **Registry**: SQLite
- **Artifacts**: JSON, JSONL, filesystem references
- **Validation**: smoke script plus pytest-compatible test suite

## Repository Layout

```text
configs/
  datasets/              Dataset ingest configs
  policies/              Policy adapter configs
  eval/                  Evaluation and taxonomy configs
  cases/                 Comparison case configs
data/
  libero/                Small benchmark-style sample input
  rosbags/               ROSBag2-style metadata fixture
  cached_rollouts/       Cached rollout actions
docs/
  architecture/          Module boundary notes
  cv/                    Application and portfolio positioning
  roadmap/               Development roadmap
  showcase/              Demo walkthrough and case study
packages/
  analysis/              Failure ranking and tagging
  common/                Config and IO helpers
  eval_runner/           Evaluation runner and policy adapters
  exporters/             Learning-dataset exports
  ingest/                Dataset normalization
  registry/              SQLite registry service
  replay/                Replay artifact generation
  reporting/             Run and comparison reports
  schemas/               Shared Pydantic records
  validation/            Dataset validation checks
pipelines/               CLI entry points
scripts/                 Smoke validation script
tests/                   Unit and smoke tests
```

Generated outputs are written to `outputs/` and ignored by git.

## Quick Start

### 1. Create a virtual environment

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

### 2. Install the package

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

For running the pytest suite as well:

```bash
python -m pip install -e .[dev]
```

For the optional CDR/MCAP ROSBag2 backend:

```bash
python -m pip install -e .[rosbag]
```

### 3. Run the end-to-end demo

```bash
python -m pipelines.demo
```

This ingests both sample data sources, runs evaluations, analyzes failures, builds replay summaries, generates reports, and creates a comparison report.

### 4. Run smoke validation

```bash
python scripts/run_smoke_checks.py
```

Expected output:

```text
Smoke checks passed.
```

## Core Workflow

The demo flow exercises the full loop:

1. `configs/datasets/libero_debug.yaml` ingests a benchmark-style sample.
2. `configs/datasets/softrobotics_rosbag.yaml` ingests a ROSBag2-style sample through the metadata-backed reader.
3. `configs/datasets/softrobotics_rosbag_sqlite.yaml` ingests a generated ROSBag2 SQLite fixture through the SQLite reader.
4. `configs/datasets/softrobotics_rosbag_cdr.yaml` ingests a generated CDR-serialized ROSBag2 sqlite3 fixture through the optional `rosbags` backend.
5. `configs/datasets/softrobotics_rosbag_mcap.yaml` exercises the same backend over MCAP storage.
6. `configs/eval/libero_cached_eval.yaml` runs a cached rollout baseline.
7. `configs/eval/libero_perturbed_eval.yaml` runs a degraded rollout for comparison.
8. `configs/eval/softrobotics_rosbag_eval.yaml` runs a replay-style ROS-compatible case.
9. `configs/eval/failure_taxonomy_v0.yaml` provides failure tags.
10. `configs/cases/libero_comparison_case.yaml` defines the comparison case.

## Shared Episode Artifacts

Each normalized episode materializes as:

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

`episode.json` records the common schema:

- episode and dataset identifiers
- task and instruction
- source type and source URI
- start and end timestamps
- action, state, observation, event, and plan-trace references
- source metadata and reference outcome fields

Each evaluation run also writes:

```text
outputs/runs/<run_name>/episodes/<episode_id>/evaluation.json
```

That file ties the normalized episode to the policy adapter result, success status, completion ratio, latency, failure tags, and adapter metadata.

For ROSBag2-style sources, the dataset root also writes `quality_report.json`. The per-episode `quality.json` files summarize topic availability, aligned sample counts, timestamp tolerance, stale or missing samples, and stream gaps.

## Command Reference

### Ingest datasets

```bash
python -m pipelines.ingest --config configs/datasets/libero_debug.yaml
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag.yaml
python scripts/create_rosbag2_sqlite_fixture.py
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag_sqlite.yaml
python scripts/create_rosbag2_cdr_fixture.py
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag_cdr.yaml
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag_mcap.yaml
```

## Validation and Export

Validate a normalized dataset before using it downstream:

```bash
python -m pipelines.validate_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1
```

Export a portable learning-dataset index:

```bash
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format learning_jsonl
```

Export a LeRobot-style metadata stub:

```bash
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format lerobot_stub
```

Export an HDF5-compatible packing contract stub:

```bash
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format hdf5_stub
```

Export a deterministic train/eval split view for downstream learning workflows:

```bash
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format split_jsonl --split-ratio 0.5 --split-seed 2
```

Export tabular action/state streams as JSONL plus Parquet when a Parquet engine is available:

```bash
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format parquet
```

### Run evaluations

```bash
python -m pipelines.eval --config configs/eval/libero_cached_eval.yaml
python -m pipelines.eval --config configs/eval/libero_perturbed_eval.yaml
python -m pipelines.eval --config configs/eval/softrobotics_rosbag_eval.yaml
```

### Analyze failures

```bash
python -m pipelines.analyze --run outputs/runs/libero_cached_eval --taxonomy configs/eval/failure_taxonomy_v0.yaml
python -m pipelines.analyze --run outputs/runs/softrobotics_rosbag_eval --taxonomy configs/eval/failure_taxonomy_v0.yaml
```

### Build replay artifacts

```bash
python -m pipelines.replay --run outputs/runs/libero_cached_eval --top-k 3
python -m pipelines.replay --run outputs/runs/softrobotics_rosbag_eval --top-k 3
```

### Generate reports

```bash
python -m pipelines.report --run outputs/runs/libero_cached_eval
python -m pipelines.report --run outputs/runs/softrobotics_rosbag_eval
```

### Compare runs

```bash
python -m pipelines.compare --config configs/cases/libero_comparison_case.yaml
```

### Evaluate regression gates

```bash
python -m pipelines.gate --config configs/cases/libero_regression_gate_pass.yaml
```

### Inspect the local registry

```bash
python -m pipelines.registry
```

## Reports and Demo Outputs

After running `python -m pipelines.demo`, useful outputs include:

```text
outputs/runs/libero_cached_eval/report.md
outputs/runs/libero_cached_eval/report.html
outputs/runs/libero_perturbed_eval/report.md
outputs/runs/softrobotics_rosbag_eval/report.md
outputs/comparisons/libero_comparison_case/comparison.md
outputs/comparisons/libero_comparison_case/comparison.html
outputs/registry_snapshot.json
```

The generated reports are ignored by git because they can be recreated from the sample inputs and configs.

For a narrative walkthrough, see:

- `docs/showcase/demo-walkthrough.md`
- `docs/showcase/case-study-libero-rosbag.md`

## Testing and Validation

The lightweight validation path does not require pytest:

```bash
python scripts/run_smoke_checks.py
```

It verifies:

- both sample datasets ingest successfully;
- cached, perturbed, and ROS-compatible evaluations run;
- analysis and replay artifacts are generated;
- deterministic train/eval split export manifests are generated;
- regression gates can both pass and fail in reproducible ways;
- reports and comparison reports exist;
- registry snapshot is populated;
- richer episode artifacts include event timelines, plan traces, action streams, run config hashes, and replay summaries.

If pytest is installed:

```bash
python -m pytest -q
```

The GitHub Actions smoke workflow runs `pytest`, generates ROSBag2 SQLite/CDR/MCAP fixtures, ingests them, validates the SQLite dataset, exports LeRobot and HDF5 contract stubs, exercises deterministic split export, verifies regression gates, and then runs the end-to-end smoke script.

## Research Positioning

This project is best understood as research infrastructure for embodied policy evaluation. It is designed to show:

- artifact design for heterogeneous embodied data;
- reproducible evaluation workflows;
- acceptance-style regression checks over benchmark and replay runs;
- adapter-based integration over one-off scripts;
- failure observability beyond scalar metrics;
- a bridge between benchmark-side VLA work and ROS-compatible execution traces.

It is intentionally scoped as a CPU-first software stack. It does not train policies, run GPU inference, or require a physical robot.

## Limitations

- The built-in SQLite ROSBag2 reader can parse standard `topics` and `messages` tables with JSON payload fixtures.
- The optional `rosbags` backend can deserialize CDR payloads from generated ROSBag2 sqlite3 and MCAP bags for common message families used by this project; broader custom ROS message support is future work.
- Replay artifacts are textual and JSON-based; there is no heavy media viewer.
- The sample datasets are small and intended for workflow demonstration.
- Failure tags are heuristic and lightweight, not a learned root-cause model.
- Generated outputs use local filesystem paths and should be regenerated after cloning.

## Roadmap

High-value next steps:

- extend CDR deserialization coverage to project-specific custom ROS messages;
- add split-aware Parquet and richer release-oriented dataset exports;
- write full LeRobot and HDF5 dataset packs with media/tensor storage;
- add an external-process policy adapter for real VLA wrappers;
- add richer per-task metrics and failure clustering.

## License

This project is released under the MIT License. See `LICENSE`.
