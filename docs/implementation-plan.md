# Implementation Plan

## Goal

Design and build this project in the same order that a real software system would need to grow:

1. freeze artifact contracts;
2. make ingest stable;
3. make evaluation pluggable;
4. make analysis inspectable;
5. make comparison explainable;
6. only then polish packaging and presentation.

This document is implementation-first on purpose. It is meant to answer: **what do we build next, why now, and what blocks what?**

## Engineering Principle

The system should always remain usable after each phase.

That means every phase must leave behind:

- one stable interface;
- one inspectable artifact;
- one demo path that still runs.

## Dependency Order

### Phase 1 - Artifact contract

Build first:

- `EpisodeRecord`
- `DatasetManifest`
- `RunRecord`
- `FailureTag`
- output directory conventions

Why first:

- everything else reads and writes these objects;
- if they drift, every later module becomes glue code.

Done when:

- ingest writes normalized episode artifacts;
- eval writes a stable run manifest;
- analysis and report consume those artifacts without hidden state.

Current status:

- done in `packages/schemas/`
- done in `packages/ingest/`
- done in `packages/eval_runner/`

### Phase 2 - Dataset normalization

Build second:

- `libero` ingest path
- `rosbag2` metadata-only ingest path

Why second:

- no evaluation layer matters if inputs are inconsistent;
- this is where the benchmark-side and ROS-side stories meet.

Done when:

- two source types normalize into the same schema;
- both produce `dataset_manifest.json` and `episodes.jsonl`.

Current status:

- done as MVP in `packages/ingest/service.py`

### Phase 3 - Policy adapter layer

Build third:

- `cached_rollout` adapter
- `perturbed_rollout` adapter

Why third:

- evaluation should depend on a policy interface, not hard-coded branching;
- this is the seam that later allows external-process adapters or real checkpoints.

Done when:

- eval can load an adapter from policy config;
- perturbations degrade a base rollout without inventing success;
- adapter outputs are recorded in episode artifacts.

Current status:

- done in `packages/eval_runner/policy_adapters.py`
- integrated into `packages/eval_runner/service.py`

### Phase 4 - Run execution and artifact writing

Build fourth:

- config-driven eval runner
- metrics computation
- run manifests
- config snapshots

Why fourth:

- once inputs and adapters are stable, execution becomes mostly orchestration.

Done when:

- one command creates a complete run folder;
- the run folder is enough for downstream analysis.

Current status:

- done as MVP in `packages/eval_runner/service.py`

### Phase 5 - Analysis, replay, and failure artifacts

Build fifth:

- failure ranking
- failure tags
- replay summaries
- run report

Why fifth:

- the project is only useful if a bad metric can be turned into evidence.

Done when:

- a user can move from metric -> episode -> replay -> tag -> report.

Current status:

- done as MVP in `packages/analysis/`, `packages/replay/`, `packages/reporting/`

### Phase 6 - Run comparison

Build sixth:

- baseline vs candidate metric comparison
- per-task regression breakdown
- comparison report

Why sixth:

- this is the first layer that makes the project feel like reusable research infrastructure rather than a one-shot script.

Done when:

- two runs can be compared from config;
- the report explains where the regression happened;
- one representative failure is surfaced automatically.

Current status:

- done in `packages/eval_runner/service.py` and `packages/reporting/comparison.py`
- verified through `python -m pipelines.compare --config configs/cases/libero_comparison_case.yaml`

### Phase 7 - Hardening

Build last:

- smoke tests
- better sample data
- packaging cleanup
- optional HTML output

Why last:

- polishing before the comparison path is stable would be wasted motion.

Current status:

- smoke harness implemented in `scripts/run_smoke_checks.py`
- HTML report output implemented for run and comparison artifacts
- local registry snapshot available via `python -m pipelines.registry`

## File-Level Plan

### New or expanded files

- `packages/eval_runner/policy_adapters.py`
- `packages/reporting/comparison.py`
- `pipelines/compare.py`
- `docs/implementation-plan.md`

### Existing files to update

- `packages/eval_runner/service.py`
- `pipelines/demo.py`
- `README.md`

## Acceptance Criteria

The implemented MVP is successful if:

1. benchmark and rosbag-style sources both ingest into shared episode artifacts;
2. config-driven evaluation runs produce manifests, metrics, and per-episode outputs;
3. replay, failure analysis, and reports work on generated runs;
4. comparison reports explain baseline-vs-candidate regressions;
5. `python scripts/run_smoke_checks.py` passes on CPU only.
