# Six-Week Plan

## Project Mode

Treat this as a software-only evaluation and failure-analysis control plane for embodied AI workflows.

## V1 Upgrade Target

The next high-value upgrade is documented in `docs/roadmap/rosbag2-to-learning-dataset-v1.md`.

Short version: extend the current evaluation stack with a ROSBag2-to-learning-dataset conversion path that adds topic parsing, timestamp alignment, episode slicing, quality checks, and export hooks while preserving the existing replay, analysis, and reporting flow.

## Week 1 - Scope freeze, schema, ingest MVP

**Deliverables**

- Freeze one primary benchmark slice and one secondary slice.
- Define `episode`, `run`, `artifact`, and `report` schemas.
- Build the first ingest path for benchmark traces and rosbag or simulator logs.

**Risks**

- Over-designing the schema.
- Spending time on generality before the loop works.

**Exit criteria**

- Two data sources normalize into the same artifact layout.
- Metadata can index trajectories, instructions, and media references.

## Week 2 - Evaluation runner

**Deliverables**

- Build a reproducible eval runner driven by config.
- Support one policy adapter path plus one simple baseline or cached-output adapter.
- Emit run manifests and episode-level metrics.

**Risks**

- Benchmark wrapper complexity.
- Hidden dependency on GPU-only inference.

**Exit criteria**

- One command runs a minimal evaluation end to end.
- One baseline run completes and produces structured outputs.

## Week 3 - Failure analysis and replay

**Deliverables**

- Implement failure taxonomy v0.
- Support episode replay and keyframe inspection.
- Support failure tagging and ranked failure retrieval.

**Risks**

- Building a full annotation tool by accident.
- Turning replay into a UI project.

**Exit criteria**

- A user can go from aggregate metrics to a failed episode and inspect it quickly.

## Week 4 - Reporting and run comparison

**Deliverables**

- Generate Markdown or HTML reports.
- Support run-to-run comparison and task-slice breakdowns.
- Surface representative regressions and representative successes.

**Risks**

- Too much presentation work.
- Not enough analysis value.

**Exit criteria**

- The report answers where a run regressed and which cases deserve inspection.

## Week 5 - Software-only case study

**Deliverables**

- Build one rosbag-backed or simulator-backed case study.
- Demonstrate a full loop: ingest, replay, failure diagnosis, config change, re-run.

**Risks**

- Choosing a case that depends on hardware.
- Picking too many shallow cases.

**Exit criteria**

- One case study is complete, reproducible, and easy to explain.

## Week 6 - Packaging and demo readiness

**Deliverables**

- Clean repository structure.
- Finish README, diagrams, smoke tests, and demo script.
- Prepare a short demo narrative and screenshots or clips.

**Risks**

- Cosmetic work crowding out verification.
- Weak final explanation of why the project matters.

**Exit criteria**

- A new reader can reproduce the minimal demo from the README.

## Weekly Showcase Artifact

| Week | Best artifact |
| --- | --- |
| 1 | schema doc and sample normalized episode |
| 2 | reproducible baseline eval report |
| 3 | failure replay board and tags |
| 4 | run comparison report |
| 5 | one complete rosbag or simulator case study |
| 6 | clean public-ready repo and short demo |

## Repository Shape

```text
docs/
  architecture/
  roadmap/
  cv/
configs/
  datasets/
  policies/
  eval/
  cases/
packages/
  schemas/
  ingest/
  eval_runner/
  analysis/
  replay/
  reporting/
  adapters_benchmark/
  adapters_rosbags/
pipelines/
cases/
  libero_replay/
  calvin_slice/
  rosbag_case_study/
tests/
  unit/
  integration/
  smoke/
scripts/
  demo/
```

## Must-Not-Do List

1. Do not train or fine-tune a VLA.
2. Do not depend on a live robot bring-up.
3. Do not try to cover every benchmark.
4. Do not build a generic data platform for every future lab project.
5. Do not add distributed orchestration.
6. Do not turn failure analysis into a heavy annotation product.
