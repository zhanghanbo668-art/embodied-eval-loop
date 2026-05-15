"""Regression gate evaluation for baseline-vs-candidate runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Template

from packages.common.config import display_path, resolve_repo_path
from packages.common.io import dump_json, ensure_dir, load_jsonl, load_yaml
from packages.eval_runner.service import compare_runs
from packages.reporting.comparison import task_regressions

GATE_TEMPLATE = Template(
    """# Regression Gate: {{ case_name }}

## Summary

- Status: `{{ status }}`
- Baseline: `{{ baseline_run }}`
- Candidate: `{{ candidate_run }}`
- Gate root: `{{ output_root }}`
- Failed checks: `{{ failed_count }}`

## Aggregate Delta

- Success rate delta: `{{ aggregate_delta.success_rate }}`
- Episode length delta: `{{ aggregate_delta.episode_length }}`
- Completion ratio delta: `{{ aggregate_delta.completion_ratio }}`
- Action latency delta: `{{ aggregate_delta.action_latency_ms }}`

## Checks

{% if checks %}
{% for check in checks -%}
- [`{{ check.status }}`] `{{ check.scope }}` / `{{ check.metric }}` observed=`{{ check.observed_delta }}` rule=`{{ check.rule }}`{% if check.task_id %} task=`{{ check.task_id }}`{% endif %}
{% endfor %}
{% else %}
- No checks configured.
{% endif %}
"""
)


@dataclass(slots=True)
class GateResult:
    """Structured result for one regression gate evaluation."""

    case_name: str
    status: str
    output_root: Path
    report_path: Path
    json_path: Path
    failed_count: int
    checks: list[dict[str, Any]]


def run_regression_gate(config_path: str | Path) -> GateResult:
    """Evaluate configured regression gates over baseline/candidate runs."""
    config_file = resolve_repo_path(config_path)
    config = load_yaml(config_file)
    case_name = str(config.get("name", config_file.stem))
    baseline_run = resolve_repo_path(config["baseline_run"])
    candidate_run = resolve_repo_path(config["candidate_run"])
    output_root = ensure_dir(resolve_repo_path(str(config.get("output_root", f"outputs/gates/{case_name}"))))

    aggregate = compare_runs(baseline_run, candidate_run)
    baseline_episodes = load_jsonl(baseline_run / "episodes.jsonl")
    candidate_episodes = load_jsonl(candidate_run / "episodes.jsonl")
    task_rows = {str(row["task_id"]): row for row in task_regressions(baseline_episodes, candidate_episodes)}

    checks = _evaluate_checks(
        aggregate_delta=aggregate["delta"],
        task_rows=task_rows,
        aggregate_rules=config.get("aggregate_gates", []),
        task_rules=config.get("task_gates", []),
    )
    failed_count = sum(1 for check in checks if check["status"] == "fail")
    status = "pass" if failed_count == 0 else "fail"

    payload = {
        "case_name": case_name,
        "status": status,
        "baseline_run": display_path(baseline_run),
        "candidate_run": display_path(candidate_run),
        "output_root": display_path(output_root),
        "aggregate_delta": aggregate["delta"],
        "failed_count": failed_count,
        "checks": checks,
    }
    json_path = dump_json(output_root / "gate.json", payload)
    report_path = output_root / "gate.md"
    report_path.write_text(
        GATE_TEMPLATE.render(
            case_name=case_name,
            status=status,
            baseline_run=display_path(baseline_run),
            candidate_run=display_path(candidate_run),
            output_root=display_path(output_root),
            failed_count=failed_count,
            aggregate_delta=aggregate["delta"],
            checks=checks,
        ),
        encoding="utf-8",
    )
    return GateResult(
        case_name=case_name,
        status=status,
        output_root=output_root,
        report_path=report_path,
        json_path=json_path,
        failed_count=failed_count,
        checks=checks,
    )


def _evaluate_checks(
    *,
    aggregate_delta: dict[str, Any],
    task_rows: dict[str, dict[str, Any]],
    aggregate_rules: Any,
    task_rules: Any,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for rule in aggregate_rules if isinstance(aggregate_rules, list) else []:
        if not isinstance(rule, dict):
            continue
        metric = str(rule.get("metric", "")).strip()
        if not metric:
            continue
        observed = float(aggregate_delta.get(metric, 0.0))
        checks.append(_build_check(scope="aggregate", metric=metric, observed=observed, rule=rule))

    for rule in task_rules if isinstance(task_rules, list) else []:
        if not isinstance(rule, dict):
            continue
        task_id = str(rule.get("task_id", "")).strip()
        metric = str(rule.get("metric", "")).strip()
        if not task_id or not metric:
            continue
        row = task_rows.get(task_id)
        observed = float(row.get(f"{metric}_delta", 0.0)) if row else 0.0
        check = _build_check(scope="task", metric=metric, observed=observed, rule=rule)
        check["task_id"] = task_id
        check["task_present"] = row is not None
        if row is None:
            check["status"] = "fail"
            check["message"] = "task not present in comparison output"
        checks.append(check)
    return checks


def _build_check(*, scope: str, metric: str, observed: float, rule: dict[str, Any]) -> dict[str, Any]:
    min_delta = rule.get("min_delta")
    max_delta = rule.get("max_delta")
    if min_delta is None and max_delta is None:
        raise ValueError(f"Gate rule for {scope}/{metric} must define min_delta or max_delta")

    failed_reasons: list[str] = []
    rule_parts: list[str] = []
    if min_delta is not None:
        min_value = float(min_delta)
        rule_parts.append(f">= {min_value}")
        if observed < min_value:
            failed_reasons.append(f"observed delta {observed} < minimum {min_value}")
    if max_delta is not None:
        max_value = float(max_delta)
        rule_parts.append(f"<= {max_value}")
        if observed > max_value:
            failed_reasons.append(f"observed delta {observed} > maximum {max_value}")

    return {
        "scope": scope,
        "metric": metric,
        "observed_delta": round(observed, 4),
        "rule": " and ".join(rule_parts),
        "status": "fail" if failed_reasons else "pass",
        "message": "; ".join(failed_reasons) if failed_reasons else "within threshold",
    }
