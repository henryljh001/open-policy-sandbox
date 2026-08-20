"""Repeat a stochastic scenario and summarize uncertainty and failure rates."""

import copy
import hashlib
import json
import math
from collections import Counter
from typing import Any, Mapping, Sequence

from policy_sandbox.application.run_scenario import run_scenario
from policy_sandbox.domains.new_urbanization.microsim.behavior import (
    MicrosimulationFailure,
)
from policy_sandbox.plugins.registry import SimulationEngineFactory


def _digest(value: Mapping[str, Any]) -> str:
    """Return a stable digest for JSON-compatible experiment input."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _quantile(sorted_values: Sequence[float], probability: float) -> float:
    """Return a linearly interpolated quantile from sorted values."""

    if not sorted_values:
        raise ValueError("quantile requires at least one value")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(
        sorted_values[lower] * (1.0 - fraction)
        + sorted_values[upper] * fraction
    )


def _summary(values: Sequence[float]) -> dict[str, float]:
    """Return deterministic mean, spread, and policy-facing quantiles."""

    ordered = sorted(float(value) for value in values)
    mean = sum(ordered) / len(ordered)
    variance = sum((value - mean) ** 2 for value in ordered) / len(ordered)
    return {
        "mean": mean,
        "std": math.sqrt(variance),
        "p05": _quantile(ordered, 0.05),
        "p50": _quantile(ordered, 0.50),
        "p95": _quantile(ordered, 0.95),
    }


def _summarize_outcomes(
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float]]:
    """Summarize numeric outcomes present in every successful run."""

    if not runs:
        return {}
    names = set(runs[0]["outcomes"])
    for run in runs[1:]:
        names.intersection_update(run["outcomes"])
    return {
        name: _summary([float(run["outcomes"][name]) for run in runs])
        for name in sorted(names)
    }


def _summarize_groups(
    runs: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Summarize group metrics present in every successful run."""

    if not runs:
        return {}
    group_names = set(runs[0]["group_outcomes"])
    for run in runs[1:]:
        group_names.intersection_update(run["group_outcomes"])
    summaries: dict[str, dict[str, dict[str, float]]] = {}
    for group in sorted(group_names):
        metric_names = set(runs[0]["group_outcomes"][group])
        for run in runs[1:]:
            metric_names.intersection_update(run["group_outcomes"][group])
        summaries[group] = {
            metric: _summary(
                [float(run["group_outcomes"][group][metric]) for run in runs]
            )
            for metric in sorted(metric_names)
        }
    return summaries


def run_experiment(
    scenario: Mapping[str, Any],
    repetitions: int = 100,
    base_seed: int | None = None,
) -> dict[str, Any]:
    """Run a stochastic scenario repeatedly with sequential, auditable seeds."""

    if isinstance(repetitions, bool) or not isinstance(repetitions, int):
        raise TypeError("repetitions must be an integer")
    if not 2 <= repetitions <= 10000:
        raise ValueError("repetitions must be between 2 and 10000")
    selected_seed = scenario["random_seed"] if base_seed is None else base_seed
    if isinstance(selected_seed, bool) or not isinstance(selected_seed, int):
        raise TypeError("base_seed must be an integer")
    if selected_seed < 0:
        raise ValueError("base_seed must be non-negative")
    engine_spec = scenario["engine"]
    engine = SimulationEngineFactory(engine_spec["name"], engine_spec.get("config", {}))
    successful: list[Mapping[str, Any]] = []
    failure_reasons: Counter[str] = Counter()
    for offset in range(repetitions):
        current = copy.deepcopy(dict(scenario))
        seed = selected_seed + offset
        current["random_seed"] = seed
        if isinstance(current.get("domain_config"), dict):
            current["domain_config"]["random_seed"] = seed
        try:
            successful.append(run_scenario(current))
        except MicrosimulationFailure as exc:
            failure_reasons[str(exc)] += 1
    failed = sum(failure_reasons.values())
    experiment_input = {
        "scenario": dict(scenario),
        "repetitions": repetitions,
        "base_seed": selected_seed,
    }
    input_digest = _digest(experiment_input)
    warnings: list[dict[str, str]] = [
        {
            "code": "SYNTHETIC_REPEATED_EXPERIMENT",
            "severity": "warning",
            "message": "重复区间来自合成随机行为，不代表真实地区置信区间。",
        }
    ]
    if failed:
        warnings.append(
            {
                "code": "SIMULATED_RUN_FAILURES",
                "severity": "warning",
                "message": "部分重复触发了配置中的显式失效事件。",
            }
        )
    return {
        "schema_version": "1.0.0",
        "experiment_id": f"experiment-{input_digest[:16]}",
        "scenario_id": scenario["scenario_id"],
        "scenario_version": scenario["version"],
        "input_digest": input_digest,
        "engine": {"name": engine.descriptor.name, "version": engine.descriptor.version},
        "base_seed": selected_seed,
        "repetitions": repetitions,
        "successful_runs": len(successful),
        "failed_runs": failed,
        "failure_rate": failed / repetitions,
        "failure_reasons": dict(sorted(failure_reasons.items())),
        "outcome_summary": _summarize_outcomes(successful),
        "group_summary": _summarize_groups(successful),
        "warnings": warnings,
        "reproducible": True,
        "synthetic": bool(scenario.get("synthetic", False)),
    }
