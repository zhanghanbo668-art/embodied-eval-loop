# GitHub Release Checklist

Use this checklist before making the repository public.

## Repository Hygiene

- [ ] `outputs/` is ignored and generated artifacts are not committed.
- [ ] Generated ROSBag2 SQLite fixtures such as `data/rosbags/softrobotics_sqlite_case/*.db3` are ignored; regenerate them with `python scripts/create_rosbag2_sqlite_fixture.py`.
- [ ] `__pycache__/`, `*.pyc`, `.pytest_cache/`, virtual environments, and editor files are ignored.
- [ ] No private datasets, credentials, tokens, or personal paths are committed.
- [ ] `README.md` explains the problem, workflow, setup, commands, and limitations.
- [ ] `LICENSE` exists.
- [ ] Demo and smoke commands run from a clean checkout.

## Local Validation

Run:

```bash
python -m pip install -e .[dev,rosbag]
python -m pytest -q
python scripts/create_rosbag2_sqlite_fixture.py
python scripts/create_rosbag2_cdr_fixture.py
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag_sqlite.yaml
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag_cdr.yaml
python -m pipelines.ingest --config configs/datasets/softrobotics_rosbag_mcap.yaml
python -m pipelines.demo
python scripts/run_smoke_checks.py
python -m pipelines.validate_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format lerobot_stub
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format hdf5_stub
python -m pipelines.export_dataset --dataset outputs/datasets/softrobotics_rosbag_sqlite_v1 --format split_jsonl --split-ratio 0.5 --split-seed 2
python -m pipelines.gate --config configs/cases/libero_regression_gate_pass.yaml
```

## GitHub Setup

After creating the repository on GitHub:

```bash
git init
git add .
git commit -m "Initial public release"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

## GitHub Actions

This repository already includes an enabled smoke workflow at:

```text
.github/workflows/smoke.yml
```

It installs the package with test and `rosbags` dependencies, runs `pytest`, generates ROSBag2 SQLite/CDR/MCAP fixtures, ingests the generated datasets, validates the SQLite dataset, exports LeRobot/HDF5/split dataset views, evaluates a passing regression gate, and finishes with the end-to-end smoke script.

## Reproducibility Note

For split exports, always record both `--split-ratio` and `--split-seed` in any experiment note, paper appendix, or release artifact. The current implementation uses a stable hash over `dataset_id + episode_id + seed`, so the same dataset and seed will reproduce the same assignment across machines.

## Suggested Repository Description

```text
Software-only embodied AI evaluation stack for benchmark trajectories, ROS-compatible logs, replay, failure analysis, and comparison reports.
```

## Suggested Topics

```text
embodied-ai, robotics, vla, evaluation, ros, replay, failure-analysis, research-infrastructure
```

## After Publishing

- [ ] Open the GitHub Actions tab and confirm the smoke workflow passes.
- [ ] Add the repository link to your CV or portfolio.
- [ ] Consider adding screenshots or exported report snippets to the README later.
- [ ] Keep generated outputs out of git unless a small static example is deliberately curated.
