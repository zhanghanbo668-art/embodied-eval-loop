# Demo Walkthrough

## Goal

Use this script to explain the project in under five minutes during an application, interview, or portfolio walkthrough.

## 30-Second Version

This project is a software-only evaluation stack for embodied AI. It takes benchmark trajectories and ROS-compatible logs, normalizes them into the same episode format, runs reproducible evaluation or replay workflows, and produces artifacts for failure analysis and run comparison. The point is not to train a new model. The point is to make policy behavior easier to test, diagnose, and communicate.

## Five-Minute Walkthrough

### 1. Start with the problem

The problem I wanted to solve was that embodied AI evaluation often breaks at the workflow level rather than at the model level. Benchmark rollouts, ROS logs, replay traces, and analysis scripts usually live in different formats and different one-off pipelines. That makes it hard to reproduce results, inspect failures, or compare runs cleanly.

### 2. Define the project in one sentence

So I built a software-only control plane that turns benchmark trajectories and ROS-compatible logs into one reproducible evaluation loop: ingest, normalize, replay, analyze failures, and generate comparison-ready reports.

### 3. Explain the core artifact

The key design choice is an episode-first artifact model. Different sources are mapped into a shared schema for episodes, runs, and reports. Once data is normalized, the rest of the workflow becomes consistent: evaluation, replay, tagging, and reporting all operate on the same contracts.

### 4. Walk through the workflow

The end-to-end workflow is:

`data ingest -> schema normalization -> eval or replay -> failure analysis -> comparison report`

In practice, that means I can take a benchmark slice and a ROS-compatible log source, convert both into the same artifact layout, run a config-driven evaluation path, inspect where failures cluster, and generate a report that shows both aggregate metrics and representative episodes.

### 5. Show what makes it useful

The value is in the outputs, not just the code. A run produces reproducible artifacts: manifests, metrics, per-episode records, replayable traces, failure tags, and reports. That gives you something a lab or research team can actually reuse when they need to debug regressions, compare policy variants, or explain results in a paper or meeting.

### 6. Clarify what it is not

This is deliberately not a new model contribution, not a training stack, and not a hardware demo. I treated it as research infrastructure: the layer that makes embodied policy work more testable, diagnosable, and easier to present.

### 7. Close with the engineering value

What I think this project shows is that I can build the software layer around embodied learning systems, not just the modeling side: typed artifacts, reproducible workflows, adapter-based integration, failure analysis, and reports that make experiments easier to trust.

## Interview-Friendly Ending

If I had to summarize it in one line, I would say: I built infrastructure that turns embodied AI evaluation from a collection of ad hoc traces into a reproducible workflow with inspectable evidence.

## Optional Shorter Ending

This project is strongest as infrastructure work. It shows evaluation design, data workflow judgment, and the ability to connect benchmark-side research with ROS-compatible execution traces in a way that other people can actually use.
