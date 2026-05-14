"""Run comparison reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Template

from packages.common.config import display_path, resolve_repo_path
from packages.common.io import dump_json, ensure_dir, load_json, load_jsonl, load_yaml
from packages.eval_runner.service import compare_runs
from packages.registry.service import register_comparison
from packages.reporting._artifacts import enrich_failure, format_value, html_escape, load_replay_lookup

COMPARISON_TEMPLATE = Template(
    """# Comparison Report: {{ case_name }}

## Runs

- Baseline: `{{ baseline_run }}`
- Candidate: `{{ candidate_run }}`
- Report root: `{{ comparison_root }}`
{% if focus_tasks %}
- Focus tasks: `{{ focus_tasks | join("`, `") }}`
{% endif %}

## Case Questions

{% if questions %}
{% for question in questions -%}
- {{ question }}
{% endfor %}
{% else %}
- No case questions provided.
{% endif %}

## Aggregate Delta

- Success rate delta: `{{ delta.success_rate }}`
- Episode length delta: `{{ delta.episode_length }}`
- Completion ratio delta: `{{ delta.completion_ratio }}`
- Action latency delta: `{{ delta.action_latency_ms }}`

## Top Task Regressions

{% if task_rows %}
{% for row in task_rows -%}
- `{{ row.task_id }}` | success delta=`{{ row.success_rate_delta }}` | completion delta=`{{ row.completion_ratio_delta }}` | latency delta=`{{ row.action_latency_ms_delta }}`
{% endfor %}
{% else %}
- No task regressions detected.
{% endif %}

## Candidate Failure Breakdown

{% if failure_breakdown %}
{% for tag, count in failure_breakdown.items() -%}
- `{{ tag }}`: {{ count }}
{% endfor %}
{% else %}
- No candidate failure tags found.
{% endif %}

## Representative Failure

{% if representative_failure %}
- Episode: `{{ representative_failure.episode_id }}`
- Task: `{{ representative_failure.task_id }}`
- Status: `{{ representative_failure.status_display }}`
- Completion ratio: `{{ representative_failure.completion_ratio }}`
- Action latency ms: `{{ representative_failure.action_latency_ms }}`
- Tags: `{{ representative_failure.failure_tags_display }}`
- Replay summary (Markdown): `{{ representative_failure.replay_summary_md }}`
- Replay summary (JSON): `{{ representative_failure.replay_summary_json }}`
- Instruction: {{ representative_failure.instruction_display }}
{% else %}
- No representative failure available.
{% endif %}
"""
)

HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Comparison Report: {{ case_name }}</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 24px auto;
      max-width: 1040px;
      padding: 0 16px 48px;
      color: #1f2937;
      background: #f8fafc;
      line-height: 1.5;
    }
    h1, h2 {
      color: #111827;
      margin-top: 0;
    }
    section {
      background: #ffffff;
      border: 1px solid #dbe3ee;
      border-radius: 8px;
      margin-top: 16px;
      padding: 16px 20px;
    }
    dl {
      display: grid;
      gap: 8px 16px;
      grid-template-columns: max-content 1fr;
      margin: 0;
    }
    dt {
      font-weight: 700;
    }
    dd {
      margin: 0;
    }
    ul {
      margin: 0;
      padding-left: 20px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
    }
    th, td {
      border: 1px solid #dbe3ee;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: #eef4fb;
    }
    .mono {
      font-family: Consolas, "Courier New", monospace;
      word-break: break-word;
    }
    .empty {
      color: #6b7280;
    }
  </style>
</head>
<body>
  <h1>Comparison Report: {{ case_name_escaped }}</h1>

  <section>
    <h2>Runs</h2>
    <dl>
      <dt>Baseline</dt><dd class="mono">{{ baseline_run }}</dd>
      <dt>Candidate</dt><dd class="mono">{{ candidate_run }}</dd>
      <dt>Report root</dt><dd class="mono">{{ comparison_root }}</dd>
      {% if focus_tasks %}
      <dt>Focus tasks</dt><dd class="mono">{{ focus_tasks | join(", ") }}</dd>
      {% endif %}
    </dl>
  </section>

  <section>
    <h2>Case Questions</h2>
    {% if questions %}
    <ul>
      {% for question in questions -%}
      <li>{{ question }}</li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="empty">No case questions provided.</p>
    {% endif %}
  </section>

  <section>
    <h2>Aggregate Delta</h2>
    <dl>
      <dt>Success rate delta</dt><dd>{{ success_rate_delta }}</dd>
      <dt>Episode length delta</dt><dd>{{ episode_length_delta }}</dd>
      <dt>Completion ratio delta</dt><dd>{{ completion_ratio_delta }}</dd>
      <dt>Action latency delta</dt><dd>{{ action_latency_ms_delta }}</dd>
    </dl>
  </section>

  <section>
    <h2>Top Task Regressions</h2>
    {% if task_rows %}
    <table>
      <thead>
        <tr>
          <th>Task</th>
          <th>Success delta</th>
          <th>Completion delta</th>
          <th>Latency delta</th>
        </tr>
      </thead>
      <tbody>
        {% for row in task_rows -%}
        <tr>
          <td class="mono">{{ row.task_id }}</td>
          <td>{{ row.success_rate_delta }}</td>
          <td>{{ row.completion_ratio_delta }}</td>
          <td>{{ row.action_latency_ms_delta }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="empty">No task regressions detected.</p>
    {% endif %}
  </section>

  <section>
    <h2>Candidate Failure Breakdown</h2>
    {% if failure_items %}
    <ul>
      {% for item in failure_items -%}
      <li><span class="mono">{{ item.tag }}</span>: {{ item.count }}</li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="empty">No candidate failure tags found.</p>
    {% endif %}
  </section>

  <section>
    <h2>Representative Failure</h2>
    {% if representative_failure %}
    <dl>
      <dt>Episode</dt><dd class="mono">{{ representative_failure.episode_id }}</dd>
      <dt>Task</dt><dd class="mono">{{ representative_failure.task_id }}</dd>
      <dt>Status</dt><dd>{{ representative_failure.status_display }}</dd>
      <dt>Completion ratio</dt><dd>{{ representative_failure.completion_ratio }}</dd>
      <dt>Action latency ms</dt><dd>{{ representative_failure.action_latency_ms }}</dd>
      <dt>Failure tags</dt><dd>{{ representative_failure.failure_tags_display }}</dd>
      <dt>Instruction</dt><dd>{{ representative_failure.instruction_display }}</dd>
      <dt>Replay</dt>
      <dd>
        {% if representative_failure.replay_summary_md_href %}
        <div><a href="{{ representative_failure.replay_summary_md_href }}">summary.md</a></div>
        {% else %}
        <div class="empty">summary.md unavailable</div>
        {% endif %}
        {% if representative_failure.replay_summary_json_href %}
        <div><a href="{{ representative_failure.replay_summary_json_href }}">summary.json</a></div>
        {% else %}
        <div class="empty">summary.json unavailable</div>
        {% endif %}
      </dd>
    </dl>
    {% else %}
    <p class="empty">No representative failure available.</p>
    {% endif %}
  </section>
</body>
</html>
"""
)


def _aggregate_by_task(episodes: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_task: dict[str, list[dict[str, Any]]] = {}
    for episode in episodes:
        task_id = str(episode.get("task_id", "unknown_task"))
        by_task.setdefault(task_id, []).append(episode)

    summary: dict[str, dict[str, float]] = {}
    for task_id, rows in by_task.items():
        count = len(rows)
        success_rate = sum(1 for row in rows if row.get("success")) / count if count else 0.0
        completion_ratio = sum(float(row.get("completion_ratio", 0.0)) for row in rows) / count if count else 0.0
        latency = sum(int(row.get("action_latency_ms", 0)) for row in rows) / count if count else 0.0
        summary[task_id] = {
            "success_rate": round(success_rate, 4),
            "completion_ratio": round(completion_ratio, 4),
            "action_latency_ms": round(latency, 4),
        }
    return summary


def _task_regressions(baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base_summary = _aggregate_by_task(baseline)
    cand_summary = _aggregate_by_task(candidate)
    task_ids = sorted(set(base_summary) | set(cand_summary))
    rows: list[dict[str, Any]] = []
    for task_id in task_ids:
        base = base_summary.get(task_id, {"success_rate": 0.0, "completion_ratio": 0.0, "action_latency_ms": 0.0})
        cand = cand_summary.get(task_id, {"success_rate": 0.0, "completion_ratio": 0.0, "action_latency_ms": 0.0})
        rows.append(
            {
                "task_id": task_id,
                "success_rate_delta": round(cand["success_rate"] - base["success_rate"], 4),
                "completion_ratio_delta": round(cand["completion_ratio"] - base["completion_ratio"], 4),
                "action_latency_ms_delta": round(cand["action_latency_ms"] - base["action_latency_ms"], 4),
            }
        )
    return sorted(rows, key=lambda row: (row["completion_ratio_delta"], row["success_rate_delta"]))


def _filter_focus_tasks(rows: list[dict[str, Any]], focus_tasks: list[str]) -> list[dict[str, Any]]:
    if not focus_tasks:
        return rows
    focus = {task_id for task_id in focus_tasks}
    return [row for row in rows if str(row.get("task_id")) in focus]


def _failure_items(by_tag: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"tag": str(tag), "count": count} for tag, count in by_tag.items()]


def _render_html(
    report_path: Path,
    case_name: str,
    baseline_run: str,
    candidate_run: str,
    delta: dict[str, Any],
    task_rows: list[dict[str, Any]],
    failure_breakdown: dict[str, Any],
    representative_failure: dict[str, Any] | None,
    focus_tasks: list[str],
    questions: list[str],
) -> None:
    html_path = report_path.with_suffix(".html")
    html_text = HTML_TEMPLATE.render(
        case_name=case_name,
        case_name_escaped=html_escape(case_name),
        baseline_run=html_escape(baseline_run),
        candidate_run=html_escape(candidate_run),
        comparison_root=html_escape(display_path(report_path.parent)),
        success_rate_delta=format_value(delta.get("success_rate")),
        episode_length_delta=format_value(delta.get("episode_length")),
        completion_ratio_delta=format_value(delta.get("completion_ratio")),
        action_latency_ms_delta=format_value(delta.get("action_latency_ms")),
        task_rows=task_rows,
        failure_items=_failure_items(failure_breakdown),
        representative_failure=representative_failure,
        focus_tasks=focus_tasks,
        questions=questions,
    )
    html_path.write_text(html_text, encoding="utf-8")


def build_comparison_report(case_config_path: str | Path) -> Path:
    """Generate a comparison report from a case config."""
    config_path = resolve_repo_path(case_config_path)
    case = load_yaml(config_path)
    case_name = str(case.get("name", config_path.stem))
    baseline_run = resolve_repo_path(case["baseline_run"])
    candidate_run = resolve_repo_path(case["candidate_run"])
    focus_tasks = [str(task_id) for task_id in case.get("focus_tasks", []) if str(task_id).strip()]
    questions = [str(question) for question in case.get("questions", []) if str(question).strip()]

    aggregate = compare_runs(baseline_run, candidate_run)
    baseline_episodes = load_jsonl(baseline_run / "episodes.jsonl")
    candidate_episodes = load_jsonl(candidate_run / "episodes.jsonl")
    candidate_analysis = load_json(candidate_run / "analysis.json") if (candidate_run / "analysis.json").exists() else {}
    comparison_root = ensure_dir(resolve_repo_path(f"outputs/comparisons/{case_name}"))
    report_path = comparison_root / "comparison.md"

    replay_lookup = load_replay_lookup(candidate_run, report_path)
    ranked_failures = candidate_analysis.get("ranked_episode_ids", [])
    representative_failure = next(
        (
            enrich_failure(episode, replay_lookup, report_path)
            for episode in candidate_episodes
            if episode.get("episode_id") in ranked_failures
        ),
        None,
    )

    task_rows = _filter_focus_tasks(_task_regressions(baseline_episodes, candidate_episodes), focus_tasks)
    failure_breakdown = candidate_analysis.get("by_tag", {})
    baseline_display = display_path(baseline_run)
    candidate_display = display_path(candidate_run)

    report_text = COMPARISON_TEMPLATE.render(
        case_name=case_name,
        baseline_run=baseline_display,
        candidate_run=candidate_display,
        comparison_root=display_path(comparison_root),
        focus_tasks=focus_tasks,
        questions=questions,
        delta=aggregate["delta"],
        task_rows=task_rows,
        failure_breakdown=failure_breakdown,
        representative_failure=representative_failure,
    )
    report_path.write_text(report_text, encoding="utf-8")
    _render_html(
        report_path,
        case_name=case_name,
        baseline_run=baseline_display,
        candidate_run=candidate_display,
        delta=aggregate["delta"],
        task_rows=task_rows,
        failure_breakdown=failure_breakdown,
        representative_failure=representative_failure,
        focus_tasks=focus_tasks,
        questions=questions,
    )

    payload = {
        "case_name": case_name,
        "baseline_run": baseline_display,
        "candidate_run": candidate_display,
        "focus_tasks": focus_tasks,
        "questions": questions,
        "aggregate": aggregate,
        "task_rows": task_rows,
        "representative_failure": representative_failure,
    }
    dump_json(comparison_root / "comparison.json", payload)
    register_comparison(
        case_name=case_name,
        baseline_run=baseline_display,
        candidate_run=candidate_display,
        output_root=display_path(comparison_root),
        report_path=display_path(report_path),
    )
    return report_path
