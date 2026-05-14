# Embodied Data & Evaluation Stack for VLA Policies

## Working Title

**Embodied Data & Evaluation Stack for VLA Policies**  
Subtitle: A software-only control plane for multimodal data ingest, policy evaluation, replay, and failure analysis.

Short alias: **VLA-ROS Data and Evaluation Loop**

## Positioning

This project is a pure-software research infrastructure system for embodied AI. Its purpose is to turn fragmented robot logs, benchmark trajectories, and policy outputs into one reproducible loop for data ingest, rollout evaluation, replay, failure analysis, and report generation.

It is not a new model, not a training stack, and not a hardware demo. The value is in building the layer that makes embodied policy work easier to test, compare, diagnose, and present.

## Hard Constraints

- CPU-first and software-only.
- No GPU training loop.
- No dependency on bringing up a real robot.
- Front end is optional and must stay lightweight.
- The core artifact must remain useful even if the only inputs are benchmark logs, rosbags, simulator traces, and cached model outputs.

## Why This Fits The CV Best

This direction strengthens the exact line already visible in the current CV:

- `PlanDiff-OpenVLA` gives the policy-side evaluation and benchmark anchor.
- The soft robotics ROS work gives the multimodal sensing and execution-side context.
- The testing internship explains the emphasis on verification, failure analysis, and debugging workflow.

So the project reads naturally as: **the software infrastructure that makes embodied learning systems testable, diagnosable, and reproducible.**

## Core Thesis

The right framing is not "a pure robotics runtime" and not "a benchmark script collection." It is a **data and evaluation control plane** for VLA and robot-learning workflows.

## Problem Statement

Embodied AI projects often break down at the workflow level:

1. data arrives in incompatible formats;
2. policy interfaces differ across benchmarks and projects;
3. evaluation outputs are hard to compare or reproduce;
4. failures are visible only as scalar metrics instead of inspectable evidence;
5. ROS and simulator traces are hard to connect back to policy-side analysis.

This project addresses that gap with a thin but coherent software layer.

## System Loop

`data ingest -> schema normalization -> policy adapter -> rollout/eval runner -> replay/failure analysis -> report -> targeted re-run`

The loop must work without training. Re-run means re-evaluating from a changed config, adapter, filter, or benchmark slice, not retraining a model.

## Core Modules

1. **Data ingest and time alignment**
   - Inputs: `rosbag/rosbag2`, benchmark trajectories, simulator logs, videos, state/action logs.
   - Responsibilities: parsing, field validation, timestamp alignment, task metadata extraction.
   - Boundary: produces normalized artifacts only.

2. **Unified episode schema and run registry**
   - Canonical records: `episode`, `run`, `artifact`, `report`.
   - Canonical fields: `instruction`, `observation refs`, `action`, `robot state`, `timestamp`, `task_id`, `source`, plus optional `plan_trace` or `reasoning_trace`.
   - Boundary: stores references and metadata, not heavy media processing logic.

3. **Policy adapter layer**
   - Exposes one interface over different policy families, cached outputs, or mock policies.
   - Boundary: does not own benchmark logic or metrics.

4. **Unified rollout and evaluation runner**
   - Runs benchmark slices, offline replay checks, and software-only ROS-compatible evaluations.
   - Produces manifests, metrics, and artifact bundles from config.
   - Boundary: executes and logs; deep diagnosis belongs downstream.

5. **Failure analysis and replay**
   - Supports episode slicing, keyframe replay, failure taxonomy tags, and trace inspection.
   - Boundary: consumes normalized outputs rather than raw sensor capture.

6. **Reporting and comparison**
   - Generates Markdown or HTML reports with run summaries, task breakdowns, regressions, and representative failures.
   - Boundary: presentation layer only.

7. **ROS or simulator compatibility harness**
   - Provides a thin bridge for rosbag-backed or simulator-backed case studies.
   - Boundary: validates compatibility without turning the project into a robot control stack.

## Minimal Technical Architecture

### Execution stack

- `Python` for the control plane and CLI tools.
- `SQLite` for the local registry.
- `Parquet`, `JSON`, and media file references for episode artifacts.
- Optional ROS 2 compatibility through rosbag import and replay adapters.

### Data layout

Each normalized episode is stored as a folder containing:

- `episode.json`
- `state.parquet`
- `action.parquet`
- `events.jsonl`
- `media/` references such as `rgb.mp4`
- optional `plan_trace.jsonl`

Each run produces:

- `config.yaml`
- `run.json`
- `metrics.json`
- `episodes.jsonl`
- `failure_tags.jsonl`
- `report.md`

### Execution surfaces

The runner should support three software-only modes:

1. `benchmark`: evaluate a policy adapter or cached output against a benchmark slice;
2. `replay`: replay an existing trajectory bundle for inspection and validation;
3. `rosbag_case`: ingest and analyze ROS-compatible logs without online robot execution.

## Design Principles

1. **Episode-first, versioned artifacts**  
   Everything is organized around versioned episodes and runs so results remain inspectable and reproducible.

2. **Adapter over rewrite**  
   Reuse existing benchmarks, logs, and policy outputs through thin adapters instead of inventing a new framework.

3. **Failure observability is a first-class output**  
   A run is incomplete unless it produces replayable evidence, not just aggregate scores.

## Deliberate Non-Goals

- No model training or fine-tuning.
- No heavy GPU dependency.
- No distributed orchestration system.
- No full robotics middleware replacement.
- No polished front-end product.
- No hardware-dependent demo as the main proof point.

## Recommended Six-Week Shape

The strongest short-horizon version of the project should include:

- one unified schema;
- two or more data-source ingestors;
- one benchmark adapter path;
- one reproducible eval runner;
- one failure taxonomy and replay path;
- one report generator;
- one rosbag-backed or simulator-backed case study.

## Success Criteria

The project is successful if it can show:

- two data sources normalized into one episode format;
- one command-driven eval path with reproducible outputs;
- one benchmark comparison report;
- one failure-analysis workflow from metric to replay to tag;
- one software-only ROS or simulator case study proving the stack is not benchmark-only.

## Companion Docs

- `docs/architecture/module-boundaries.md`
- `docs/roadmap/6-week-plan.md`
- `docs/cv/project-positioning.md`
