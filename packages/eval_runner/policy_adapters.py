"""Policy adapter implementations for the evaluation runner."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.common.config import resolve_repo_path
from packages.common.io import load_jsonl


@dataclass(slots=True)
class AdapterEpisodeResult:
    """Adapter output for one evaluated episode."""

    success: bool
    completion_ratio: float
    action_latency_ms: int
    predicted_failure_tags: list[str]
    adapter_metadata: dict[str, Any]


class PolicyAdapter:
    """Small interface for software-only policy adapters."""

    def evaluate_episode(self, episode: dict[str, Any], episode_index: int) -> AdapterEpisodeResult:
        raise NotImplementedError


class CachedRolloutAdapter(PolicyAdapter):
    """Replay cached rollout metadata without model inference."""

    def __init__(self, policy_config: dict[str, Any]) -> None:
        self.policy_config = policy_config
        artifacts_root = resolve_repo_path(policy_config.get("artifacts_root", "data/cached_rollouts/reference"))
        actions_path = artifacts_root / str(policy_config.get("action_source", "actions.jsonl"))
        self.actions_by_episode = self._load_actions(actions_path)

    def _load_actions(self, actions_path: Path) -> dict[str, list[str]]:
        if not actions_path.exists():
            return {}
        records = load_jsonl(actions_path)
        return {
            str(record.get("episode_id")): [str(action) for action in record.get("actions", [])]
            for record in records
            if isinstance(record, dict) and record.get("episode_id")
        }

    def evaluate_episode(self, episode: dict[str, Any], episode_index: int) -> AdapterEpisodeResult:
        metadata = episode.get("metadata", {})
        episode_id = str(episode.get("episode_id"))
        action_trace = self.actions_by_episode.get(episode_id, [])
        success = bool(metadata.get("reference_success", True))
        completion_ratio = float(metadata.get("reference_completion_ratio", 1.0))
        latency_ms = int(metadata.get("reference_action_latency_ms", 50))
        tags = ["environment_or_data_issue"] if not success else ["ok"]
        return AdapterEpisodeResult(
            success=success,
            completion_ratio=round(completion_ratio, 4),
            action_latency_ms=latency_ms,
            predicted_failure_tags=tags,
            adapter_metadata={"action_trace": action_trace},
        )


class PerturbedRolloutAdapter(CachedRolloutAdapter):
    """Apply synthetic degradations on top of cached rollout metadata."""

    def __init__(self, policy_config: dict[str, Any]) -> None:
        base_config = {
            "artifacts_root": policy_config.get(
                "base_artifacts_root",
                policy_config.get("artifacts_root", "data/cached_rollouts/reference"),
            ),
            "action_source": policy_config.get("action_source", "actions.jsonl"),
        }
        super().__init__(base_config)
        self.perturbations = policy_config.get("perturbations", {})

    def evaluate_episode(self, episode: dict[str, Any], episode_index: int) -> AdapterEpisodeResult:
        base = super().evaluate_episode(episode, episode_index)
        success = base.success
        completion_ratio = base.completion_ratio
        latency_ms = base.action_latency_ms
        tags: list[str] = []

        action_delay = int(self.perturbations.get("action_delay_steps", 0))
        truncate_last_k = int(self.perturbations.get("truncate_last_k_actions", 0))
        drop_every_n = int(self.perturbations.get("drop_every_n_frames", 0))

        if action_delay > 0:
            latency_ms += action_delay * 75
            completion_ratio = max(0.0, round(completion_ratio - 0.2, 4))
            if success and episode_index % 2 == 1:
                success = False
            tags.append("control_execution_mismatch")

        if truncate_last_k > 0:
            completion_ratio = max(0.0, round(completion_ratio - 0.15, 4))
            if success and episode_index % 3 == 1:
                success = False
            tags.append("planning_breakdown")

        if drop_every_n > 0:
            completion_ratio = max(0.0, round(completion_ratio - 0.1, 4))
            if success and episode_index % 3 == 2:
                success = False
            tags.append("perception_miss")

        if not tags:
            tags.append("ok" if success else "environment_or_data_issue")
        elif not success and "environment_or_data_issue" not in tags and episode.get("source_type") == "rosbag2":
            tags.append("environment_or_data_issue")

        return AdapterEpisodeResult(
            success=success,
            completion_ratio=completion_ratio,
            action_latency_ms=latency_ms,
            predicted_failure_tags=tags,
            adapter_metadata=base.adapter_metadata | {"perturbations": self.perturbations},
        )


def load_policy_adapter(policy_config: dict[str, Any]) -> PolicyAdapter:
    """Instantiate a policy adapter from the policy config."""
    adapter_name = str(policy_config.get("adapter", "cached_rollout"))
    if adapter_name == "cached_rollout":
        return CachedRolloutAdapter(policy_config)
    if adapter_name == "perturbed_rollout":
        return PerturbedRolloutAdapter(policy_config)
    raise ValueError(f"Unsupported policy adapter: {adapter_name}")
