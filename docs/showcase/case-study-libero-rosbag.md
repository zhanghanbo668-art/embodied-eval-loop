# Case Study: Benchmark and ROS-Compatible Evaluation Loop

## Summary

This case study demonstrates the main purpose of the stack: turn two different embodied-data sources into one reproducible evaluation and failure-analysis workflow.

The sources are:

- a small benchmark-style LIBERO debug slice;
- a ROS-compatible soft robotics metadata trace.

Both are normalized into the same episode artifact contract, evaluated through config-driven runs, analyzed with the same failure taxonomy, and rendered into Markdown / HTML reports.

## Research Question

Can heterogeneous embodied traces be made comparable and replayable without training a new model or bringing up robot hardware?

The answer shown by this MVP is yes, at the workflow level. The project does not claim new policy performance. It demonstrates that benchmark trajectories and ROS-compatible logs can share a common data and evaluation path.

## Reproduce the Case Study

From the repository root:

```bash
python -m pipelines.demo
python scripts/run_smoke_checks.py
```

The demo writes generated artifacts under `outputs/`.

## Inputs

### Benchmark Slice

Config:

```text
configs/datasets/libero_debug.yaml
```

Sample data:

```text
data/libero/debug/episodes.json
```

This input provides a small set of instruction-conditioned episodes with task IDs, step counts, and reference outcomes.

### ROS-Compatible Trace

Config:

```text
configs/datasets/softrobotics_rosbag.yaml
```

Sample data:

```text
data/rosbags/softrobotics_case/metadata.json
```

This input represents a replay-only ROS-compatible case with topic mappings, task instructions, and reference outcomes.

## Normalized Artifact Contract

After ingest, each source produces the same layout:

```text
outputs/datasets/<dataset_id>/episodes/<episode_id>/
  episode.json
  events.jsonl
  plan_trace.jsonl
  replay_stub.json
  streams/
    action.json
    state.json
    <observation_stream>.json
```

This is the core design choice. Once data has been normalized into this contract, evaluation, replay, analysis, and reporting do not need source-specific code paths.

## Evaluation Runs

The demo runs three evaluations:

```text
outputs/runs/libero_cached_eval
outputs/runs/libero_perturbed_eval
outputs/runs/softrobotics_rosbag_eval
```

The cached run provides a reference-style baseline. The perturbed run injects controlled degradation through adapter settings, which makes the comparison report show a clear regression. The ROS-compatible run proves that the same downstream path works outside the benchmark sample.

Each run writes:

```text
run.json
metrics.json
episodes.jsonl
failure_tags.jsonl
analysis.json
report.md
report.html
episodes/<episode_id>/evaluation.json
replays/<episode_id>/summary.json
replays/<episode_id>/summary.md
```

## Example Interpretation

The benchmark comparison case compares:

```text
outputs/runs/libero_cached_eval
outputs/runs/libero_perturbed_eval
```

The expected qualitative result is:

- the perturbed policy has lower success and completion metrics;
- action latency increases because of synthetic delay;
- failures are tagged as control or planning-related;
- one representative failed episode is surfaced with replay links.

The generated comparison report is:

```text
outputs/comparisons/libero_comparison_case/comparison.html
```

## What This Shows

This case study is not about maximizing benchmark performance. It shows research-engineering capability:

- heterogeneous data normalization;
- reproducible run configuration;
- per-episode evidence artifacts;
- failure ranking and tagging;
- replayable summaries;
- comparison-ready reporting.

That makes the project useful as a compact example of infrastructure for embodied AI evaluation.

## Current Boundaries

The ROS-compatible input is metadata-backed in this MVP. A production version would add a true rosbag/rosbag2 reader and richer media handling. The current version is still useful because the downstream contracts are already source-agnostic and can accept richer adapters later.
