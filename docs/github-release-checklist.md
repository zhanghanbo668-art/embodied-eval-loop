# GitHub Release Checklist

Use this checklist before making the repository public.

## Repository Hygiene

- [ ] `outputs/` is ignored and generated artifacts are not committed.
- [ ] `__pycache__/`, `*.pyc`, `.pytest_cache/`, virtual environments, and editor files are ignored.
- [ ] No private datasets, credentials, tokens, or personal paths are committed.
- [ ] `README.md` explains the problem, workflow, setup, commands, and limitations.
- [ ] `LICENSE` exists.
- [ ] Demo and smoke commands run from a clean checkout.

## Local Validation

Run:

```bash
python -m pip install -e .
python -m pipelines.demo
python scripts/run_smoke_checks.py
```

Optional:

```bash
python -m pip install pytest
python -m pytest -q
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

## Optional GitHub Actions

This repository includes a smoke workflow template at:

```text
docs/github-actions-smoke.yml
```

To enable it, copy it to:

```text
.github/workflows/smoke.yml
```

If you push through GitHub CLI or a token, the token must include the `workflow` scope.

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
