"""Report generation for the embodied evaluation stack MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Template

from packages.common.config import display_path, resolve_repo_path
from packages.common.io import load_json, load_jsonl
from packages.registry.service import register_run
from packages.reporting._artifacts import enrich_failure, format_value, html_escape, load_replay_lookup

REPORT_TEMPLATE = Template(
    """# Run Report: {{ run.run_name }}

## Summary

- Dataset: `{{ run.dataset_id }}`
- Policy: `{{ run.policy_name }}`
- Mode: `{{ run.mode }}`
- Run root: `{{ run_root }}`
- Config hash: `{{ run.config_hash or "n/a" }}`
- Created at: `{{ run.created_at or "n/a" }}`
- Episodes: `{{ metrics.episode_count }}`
- Success rate: `{{ metrics.success_rate }}`
- Avg completion ratio: `{{ metrics.completion_ratio }}`
- Avg action latency ms: `{{ metrics.action_latency_ms }}`

## Failure Breakdown

{% if by_tag %}
{% for tag, count in by_tag.items() -%}
- `{{ tag }}`: {{ count }}
{% endfor %}
{% else %}
- No failure tags recorded.
{% endif %}

## Ranked Failures

{% if ranked_failures %}
{% for episode in ranked_failures -%}
### `{{ episode.episode_id }}`

- Task: `{{ episode.task_id }}`
- Status: `{{ episode.status_display }}`
- Completion ratio: `{{ episode.completion_ratio }}`
- Action latency ms: `{{ episode.action_latency_ms }}`
- Failure tags: `{{ episode.failure_tags_display }}`
- Ingest quality: `{{ episode.quality_status_display }}` (issues: `{{ episode.quality_issue_count_display }}`)
- Replay summary (Markdown): `{{ episode.replay_summary_md }}`
- Replay summary (JSON): `{{ episode.replay_summary_json }}`
- Evaluation artifact: `{{ episode.evaluation_json_display }}`
- Instruction: {{ episode.instruction_display }}

{% endfor %}
{% else %}
- No failures in this run.
{% endif %}
"""
)

HTML_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Run Report: {{ run_name }}</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 24px auto;
      max-width: 960px;
      padding: 0 16px 48px;
      color: #1f2937;
      background: #f8fafc;
      line-height: 1.5;
    }
    h1, h2, h3 {
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
  <h1>Run Report: {{ run_name_escaped }}</h1>

  <section>
    <h2>Summary</h2>
    <dl>
      <dt>Dataset</dt><dd class="mono">{{ dataset_id }}</dd>
      <dt>Policy</dt><dd class="mono">{{ policy_name }}</dd>
      <dt>Mode</dt><dd class="mono">{{ mode }}</dd>
      <dt>Run root</dt><dd class="mono">{{ run_root }}</dd>
      <dt>Config hash</dt><dd class="mono">{{ config_hash }}</dd>
      <dt>Created at</dt><dd class="mono">{{ created_at }}</dd>
      <dt>Episodes</dt><dd>{{ episode_count }}</dd>
      <dt>Success rate</dt><dd>{{ success_rate }}</dd>
      <dt>Avg completion ratio</dt><dd>{{ completion_ratio }}</dd>
      <dt>Avg action latency ms</dt><dd>{{ action_latency_ms }}</dd>
    </dl>
  </section>

  <section>
    <h2>Failure Breakdown</h2>
    {% if failure_items %}
    <ul>
      {% for item in failure_items -%}
      <li><span class="mono">{{ item.tag }}</span>: {{ item.count }}</li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="empty">No failure tags recorded.</p>
    {% endif %}
  </section>

  <section>
    <h2>Ranked Failures</h2>
    {% if ranked_failures %}
    <table>
      <thead>
        <tr>
          <th>Episode</th>
          <th>Task</th>
          <th>Status</th>
          <th>Completion</th>
          <th>Latency ms</th>
          <th>Failure tags</th>
          <th>Quality</th>
          <th>Replay</th>
          <th>Eval artifact</th>
          <th>Instruction</th>
        </tr>
      </thead>
      <tbody>
        {% for episode in ranked_failures -%}
        <tr>
          <td class="mono">{{ episode.episode_id }}</td>
          <td class="mono">{{ episode.task_id }}</td>
          <td>{{ episode.status_display }}</td>
          <td>{{ episode.completion_ratio }}</td>
          <td>{{ episode.action_latency_ms }}</td>
          <td>{{ episode.failure_tags_display }}</td>
          <td>{{ episode.quality_status_display }} ({{ episode.quality_issue_count_display }})</td>
          <td>
            {% if episode.replay_summary_md_href %}
            <div><a href="{{ episode.replay_summary_md_href }}">summary.md</a></div>
            {% else %}
            <div class="empty">summary.md unavailable</div>
            {% endif %}
            {% if episode.replay_summary_json_href %}
            <div><a href="{{ episode.replay_summary_json_href }}">summary.json</a></div>
            {% else %}
            <div class="empty">summary.json unavailable</div>
            {% endif %}
          </td>
          <td>
            {% if episode.evaluation_json_href %}
            <a href="{{ episode.evaluation_json_href }}">evaluation.json</a>
            {% else %}
            <span class="empty">evaluation.json unavailable</span>
            {% endif %}
          </td>
          <td>{{ episode.instruction_display }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <p class="empty">No failures in this run.</p>
    {% endif %}
  </section>
</body>
</html>
"""
)


def _ranked_failures(
    episodes: list[dict[str, Any]],
    ranked_ids: list[str],
    replay_lookup: dict[str, dict[str, str]],
    report_path: Path,
) -> list[dict[str, Any]]:
    ranked_set = {str(episode_id) for episode_id in ranked_ids}
    ordered = [episode for episode in episodes if str(episode.get("episode_id")) in ranked_set]
    return [enrich_failure(episode, replay_lookup, report_path) for episode in ordered]


def _failure_items(by_tag: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"tag": str(tag), "count": count} for tag, count in by_tag.items()]


def _render_html(
    report_path: Path,
    run: dict[str, Any],
    metrics: dict[str, Any],
    by_tag: dict[str, Any],
    ranked_failures: list[dict[str, Any]],
) -> None:
    html_path = report_path.with_suffix(".html")
    html_text = HTML_TEMPLATE.render(
        run_name=format_value(run.get("run_name")),
        run_name_escaped=html_escape(run.get("run_name")),
        dataset_id=html_escape(run.get("dataset_id")),
        policy_name=html_escape(run.get("policy_name")),
        mode=html_escape(run.get("mode")),
        run_root=html_escape(display_path(report_path.parent)),
        config_hash=html_escape(run.get("config_hash")),
        created_at=html_escape(run.get("created_at")),
        episode_count=format_value(metrics.get("episode_count")),
        success_rate=format_value(metrics.get("success_rate")),
        completion_ratio=format_value(metrics.get("completion_ratio")),
        action_latency_ms=format_value(metrics.get("action_latency_ms")),
        failure_items=_failure_items(by_tag),
        ranked_failures=ranked_failures,
    )
    html_path.write_text(html_text, encoding="utf-8")


def build_report(run_root: str | Path) -> Path:
    """Generate a Markdown report for one completed run."""
    root = resolve_repo_path(run_root)
    run = load_json(root / "run.json")
    metrics = load_json(root / "metrics.json")
    analysis_path = root / "analysis.json"
    analysis = load_json(analysis_path) if analysis_path.exists() else {}
    episodes = load_jsonl(root / "episodes.jsonl")
    report_path = root / "report.md"
    replay_lookup = load_replay_lookup(root, report_path)
    ranked_ids = analysis.get("ranked_episode_ids", [])
    ranked_failures = _ranked_failures(episodes, ranked_ids, replay_lookup, report_path)
    by_tag = analysis.get("by_tag", {})

    report_text = REPORT_TEMPLATE.render(
        run=run,
        run_root=display_path(root),
        metrics=metrics,
        by_tag=by_tag,
        ranked_failures=ranked_failures,
    )
    report_path.write_text(report_text, encoding="utf-8")
    _render_html(report_path, run, metrics, by_tag, ranked_failures)
    register_run(
        run_name=str(run.get("run_name", root.name)),
        dataset_id=str(run.get("dataset_id", "unknown")),
        mode=str(run.get("mode", "unknown")),
        policy_name=str(run.get("policy_name", "unknown")),
        policy_adapter=str(run.get("policy_adapter", "unknown")),
        output_root=str(root),
        episode_count=int(run.get("episode_count", len(episodes))),
        metrics_path=str(root / "metrics.json"),
        report_path=str(report_path),
    )
    return report_path
