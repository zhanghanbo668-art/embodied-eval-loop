# Project Design

## Final Project Definition

Build a **software-only, CPU-first embodied evaluation stack** that ingests benchmark trajectories and ROS-compatible logs into a shared episode format, runs reproducible evaluation or replay workflows, surfaces failures through replay and tagging, and emits reports that are easy to use in research discussions, applications, and demos.

Public-facing title:

**Embodied Data & Evaluation Stack for VLA Policies (VLA-ROS)**

Internal repo shorthand:

`embodied-eval-loop`

## Why This Is The Right Version

This project is optimized for one job: strengthen your CV background story.

It should make readers believe:

- you can support embodied learning work beyond model ideas;
- you understand evaluation and failure modes, not only training objectives;
- you can connect policy-side research with ROS-side data and execution traces;
- you can build research infrastructure that a lab would actually reuse.

## Hard Design Decisions

### 1. Make LIBERO the primary benchmark

Reason:

- it already matches the story in your current VLA work;
- it is a common benchmark for embodied policy evaluation;
- it gives you a natural bridge to your existing `PlanDiff-OpenVLA` narrative.

Decision:

- `LIBERO` is the only benchmark that must be supported in the MVP.
- `CALVIN` is a stretch goal, not a requirement.

### 2. Use rosbag or rosbag2 logs as the second data source

Reason:

- it ties directly to your ROS soft robotics background;
- it keeps the project software-only;
- it demonstrates that the stack is not benchmark-only.

Decision:

- one rosbag-backed case study is mandatory;
- live robot execution is explicitly out of scope.

### 3. Start with cached rollouts, not model inference

Reason:

- the project must not depend on GPU inference or training;
- cached outputs are enough to demonstrate evaluation, replay, slicing, and failure analysis;
- you can still support external policy adapters later.

Decision:

- the first policy adapter is `cached_rollout`;
- a simple heuristic or scripted baseline can be the second adapter;
- direct OpenVLA integration is optional and can remain external-process based.

### 4. Reports matter more than UI

Reason:

- for CV value, readable artifacts beat fancy front ends;
- a static HTML or Markdown report is enough to show judgment;
- replay can be implemented as simple generated pages plus media assets.

Decision:

- prioritize CLI + report generation;
- no heavy dashboard in the MVP.

## What The MVP Must Demonstrate

The MVP is complete if it can do all of the following:

1. ingest one LIBERO slice and one rosbag-backed dataset into the same schema;
2. run a config-driven evaluation or replay workflow over cached policy outputs;
3. produce aggregate metrics plus per-episode artifacts;
4. trace a failure from summary metric -> episode -> replay -> failure tag;
5. compare two runs and explain what changed;
6. generate a report that can be shown in a demo or linked from an application.

## Core Demo Story

The best end-to-end demo is:

1. ingest a small LIBERO slice;
2. load two cached rollout bundles:
   - one stronger run;
   - one weaker or perturbed run;
3. compute the same metrics for both runs;
4. identify the largest failure cluster;
5. replay a representative episode;
6. assign one or more failure tags;
7. generate a report showing:
   - where the regression happened;
   - which task slice broke;
   - which episode is the best explanatory example;
8. repeat the same artifact flow on a rosbag-backed case.

This is strong because it tells a complete story without needing any GPU, model training, or real robot bring-up.

## The Three Demo Modes

### Mode A: Benchmark comparison

Purpose:

- compare two runs on a small LIBERO task slice.

Inputs:

- normalized LIBERO episodes;
- cached rollout bundle A;
- cached rollout bundle B.

Outputs:

- success rate and task-level metrics;
- per-episode breakdown;
- ranked failure cases;
- comparison report.

### Mode B: Failure injection

Purpose:

- prove the stack can detect and explain characteristic failures even when real model outputs are limited.

Method:

- start from a successful rollout bundle;
- inject controlled perturbations such as action delay, action truncation, dropped observations, or instruction mismatch;
- run analysis and observe changes in metrics and tags.

Outputs:

- synthetic but explainable failure clusters;
- clearer replay examples for the final demo.

### Mode C: Rosbag case study

Purpose:

- show that the same schema and analysis path also works on ROS-compatible data.

Inputs:

- one rosbag or rosbag2 recording from your prior soft robotics workflow or a synthetic equivalent.

Outputs:

- normalized episode bundle;
- event timeline;
- replay assets;
- report with case notes and failure interpretation.

## Final MVP Scope

### In scope

- one benchmark ingest path: `LIBERO`
- one ROS-compatible ingest path: `rosbag/rosbag2`
- one unified schema
- one local run registry
- one cached-rollout adapter
- one simple baseline or perturbation adapter
- one evaluation runner
- one failure taxonomy v0
- one replay generator
- one report generator
- one benchmark case study
- one rosbag case study

### Out of scope

- training or fine-tuning any policy
- online robot control
- distributed jobs
- a full web app
- broad benchmark coverage
- general-purpose dataset labeling workflows

## Recommended Technical Stack

### Core language

- `Python`

Reason:

- fastest path for data processing, CLI tools, and research compatibility.

### Schema and config

- `Pydantic` models for typed records
- `YAML` configs for datasets, policies, runs, and cases

### Storage

- `SQLite` for run registry
- `JSON`, `JSONL`, and `Parquet` for artifacts
- media referenced from the filesystem

### Data handling

- `Polars` or `pandas` for tabular episode views
- `pyarrow` for Parquet interop

### Rosbag support

- prefer a pure-Python rosbag reader first;
- keep native ROS tooling optional.

### Reporting

- `Jinja2` templates
- static HTML plus Markdown export
- lightweight charts only

## Recommended Repository Contracts

### Primary records

#### `EpisodeRecord`

- `episode_id`
- `dataset_id`
- `task_id`
- `instruction`
- `start_time`
- `end_time`
- `observation_refs`
- `action_ref`
- `state_ref`
- `source_type`
- `source_uri`
- `metadata`

#### `RunRecord`

- `run_id`
- `dataset_id`
- `policy_id`
- `mode`
- `config_hash`
- `created_at`
- `artifact_root`
- `metrics_ref`
- `status`

#### `FailureTag`

- `run_id`
- `episode_id`
- `tag`
- `confidence`
- `evidence`
- `annotator`

## Failure Taxonomy V0

Start with five tags only:

1. `perception_miss`
2. `instruction_grounding_mismatch`
3. `planning_breakdown`
4. `control_execution_mismatch`
5. `environment_or_data_issue`

This is enough to show structured thinking without building a taxonomy zoo.

## CLI Surface

The MVP should expose five top-level commands:

1. `ingest`
2. `eval`
3. `analyze`
4. `replay`
5. `report`

Optional sixth command:

6. `demo`

### Example command flow

```bash
python -m pipelines.ingest --config configs/datasets/libero_debug.yaml
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag.yaml
python -m pipelines.eval --config configs/eval/libero_cached_eval.yaml
python -m pipelines.analyze --run outputs/runs/libero_cached_eval
python -m pipelines.replay --run outputs/runs/libero_cached_eval --episode EP_0007
python -m pipelines.report --run outputs/runs/libero_cached_eval
```

## Build Order

### Phase 1: Artifact contract first

Build before anything else:

- `EpisodeRecord`
- `RunRecord`
- folder layout
- run manifest writing

If this contract is unstable, the rest of the project will wobble.

### Phase 2: Ingest first, eval second

Order:

1. LIBERO ingest
2. rosbag ingest
3. cached rollout adapter
4. eval runner

This gets you to a usable loop fastest.

### Phase 3: Analysis before UI

Order:

1. failure slicing
2. replay export
3. report generation
4. only then optional viewer polish

## Best Minimal Case Study Choice

Choose:

**one LIBERO slice + one rosbag-backed soft-robotics trace**

Avoid:

- full CALVIN support in the MVP;
- multiple unrelated robot tasks;
- any case that requires live execution or hardware debugging.

## The Safest Demo Without Model Access

If you do not have convenient policy outputs ready, the safest demo path is:

1. ingest benchmark trajectories;
2. create a `reference rollout bundle` from successful trajectories;
3. generate a `perturbed rollout bundle` with controlled degradations;
4. run the same evaluation and failure-analysis pipeline on both;
5. use the comparison report as your main showcase.

That still proves:

- schema design;
- evaluation orchestration;
- reproducibility;
- replay tooling;
- failure analysis;
- research judgment.

## Done Criteria

The project is done when a new reader can:

1. install the environment on CPU;
2. ingest at least one benchmark slice and one rosbag-backed source;
3. run one evaluation config;
4. inspect one failed episode;
5. open one generated report;
6. understand in five minutes why the project matters.

## Stretch Goals

Only do these if the MVP is already solid:

- CALVIN read-only importer
- external-process policy adapter
- interactive local replay browser
- LeRobot-style dataset export adapter

## What To Say About It Publicly

The best public description is:

> A software-only embodied evaluation stack that turns benchmark trajectories and ROS-compatible logs into reproducible episodes, replayable failures, and comparison-ready reports for VLA policy research.
