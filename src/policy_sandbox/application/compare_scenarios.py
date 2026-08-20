"""Fair multi-scenario comparison with no hidden composite score."""

import copy
import hashlib
import json
import math
from importlib.resources import files
from typing import Any, Mapping, Sequence

from policy_sandbox.application.run_experiment import run_experiment
from policy_sandbox.domains.new_urbanization.microsim_scenario import (
    build_microsim_scenario,
)

RESOURCE_PACKAGE = "policy_sandbox.domains.new_urbanization.resources"
DECISION_DEFAULTS_FILE = "decision_defaults.json"
COMPARISON_MODES = frozenset({"policy", "stress", "joint"})
MAX_COMPARISON_WORK_UNITS = 50_000_000


class ComparisonValidationError(ValueError):
    """Stable validation error for public comparison callers."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Sequence[Mapping[str, str]] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = tuple(dict(detail) for detail in details)

    def to_mapping(self) -> dict[str, Any]:
        """Return a JSON-compatible API error envelope."""

        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "details": [dict(detail) for detail in self.details],
            }
        }


def load_decision_defaults() -> dict[str, Any]:
    """Load a fresh copy of inspectable metric and risk defaults."""

    resource = files(RESOURCE_PACKAGE).joinpath(DECISION_DEFAULTS_FILE)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        raise ValueError("decision defaults must declare synthetic=true")
    return payload


def _digest(value: Any) -> str:
    """Return a stable SHA-256 digest for JSON-compatible values."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _without_seed(domain_config: Mapping[str, Any]) -> dict[str, Any]:
    """Remove only the repetition seed from a domain context."""

    value = copy.deepcopy(dict(domain_config))
    value.pop("random_seed", None)
    return value


def _comparison_context(scenario: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Return fields that must remain equal for the selected comparison mode."""

    context: dict[str, Any] = {
        "domain_config": _without_seed(scenario["domain_config"]),
        "archetype": scenario.get("archetype"),
        "start_year": scenario.get("start_year"),
        "population_scale": scenario.get("population_scale", 1.0),
        "baseline_rates": scenario.get("baseline_rates", {}),
        "microsim_config": scenario.get("microsim_config"),
        "engine": scenario.get("engine"),
    }
    if mode == "policy":
        context["pressure_package"] = scenario.get("pressure_package")
    elif mode == "stress":
        context["policy_package"] = scenario.get("policy_package")
    return context


def _number(value: Any, name: str) -> float:
    """Parse a finite comparison threshold."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComparisonValidationError(
            "invalid_number",
            f"{name} must be numeric",
            ({"field": name, "code": "invalid_type"},),
        )
    number = float(value)
    if not math.isfinite(number):
        raise ComparisonValidationError(
            "invalid_number",
            f"{name} must be finite",
            ({"field": name, "code": "not_finite"},),
        )
    return number


def _scenario_work_units(scenario: Mapping[str, Any], repetitions: int) -> int:
    """Estimate household-year transitions before any experiment is run."""

    microsim_config = scenario.get("microsim_config")
    domain_config = scenario.get("domain_config")
    if not isinstance(microsim_config, Mapping) or not isinstance(domain_config, Mapping):
        raise ComparisonValidationError(
            "invalid_work_dimensions",
            "microsim_config and domain_config are required for work estimation",
        )
    sample_size = microsim_config.get("sample_size")
    horizon_years = domain_config.get("horizon_years")
    if (
        isinstance(sample_size, bool)
        or not isinstance(sample_size, int)
        or not 100 <= sample_size <= 100_000
    ):
        raise ComparisonValidationError(
            "invalid_work_dimensions",
            "sample_size must be an integer between 100 and 100000",
            ({"field": "microsim_config.sample_size", "code": "out_of_range"},),
        )
    if (
        isinstance(horizon_years, bool)
        or not isinstance(horizon_years, int)
        or not 1 <= horizon_years <= 15
    ):
        raise ComparisonValidationError(
            "invalid_work_dimensions",
            "horizon_years must be an integer between 1 and 15",
            ({"field": "domain_config.horizon_years", "code": "out_of_range"},),
        )
    return repetitions * sample_size * horizon_years


def _validate_work_budget(
    scenarios: Sequence[Mapping[str, Any]], repetitions: int
) -> None:
    estimated = sum(_scenario_work_units(scenario, repetitions) for scenario in scenarios)
    if estimated > MAX_COMPARISON_WORK_UNITS:
        raise ComparisonValidationError(
            "work_budget_exceeded",
            "estimated comparison work exceeds the local execution budget",
            (
                {"field": "estimated_work_units", "code": str(estimated)},
                {"field": "max_work_units", "code": str(MAX_COMPARISON_WORK_UNITS)},
            ),
        )


def _validate_inputs(
    scenarios: Sequence[Mapping[str, Any]],
    comparison_id: str,
    mode: str,
    baseline_scenario_id: str,
    repetitions: int,
    base_seed: int,
    selected_metrics: Sequence[str],
    metric_catalog: Mapping[str, Any],
) -> None:
    """Reject non-comparable, ambiguous, or non-synthetic requests."""

    if not comparison_id:
        raise ComparisonValidationError("missing_id", "comparison_id must be non-empty")
    if mode not in COMPARISON_MODES:
        raise ComparisonValidationError(
            "invalid_comparison_mode",
            f"comparison_mode must be one of: {', '.join(sorted(COMPARISON_MODES))}",
        )
    if not 2 <= len(scenarios) <= 9:
        raise ComparisonValidationError(
            "invalid_scenario_count",
            "comparison requires between two and nine scenarios",
        )
    if isinstance(repetitions, bool) or not isinstance(repetitions, int):
        raise ComparisonValidationError("invalid_repetitions", "repetitions must be an integer")
    if not 2 <= repetitions <= 1000:
        raise ComparisonValidationError(
            "invalid_repetitions",
            "repetitions must be between 2 and 1000",
        )
    if isinstance(base_seed, bool) or not isinstance(base_seed, int) or base_seed < 0:
        raise ComparisonValidationError(
            "invalid_base_seed",
            "base_seed must be a non-negative integer",
        )
    identifiers = [scenario.get("scenario_id") for scenario in scenarios]
    if any(not isinstance(identifier, str) or not identifier for identifier in identifiers):
        raise ComparisonValidationError("invalid_scenario_id", "scenario_id must be non-empty")
    if len(identifiers) != len(set(identifiers)):
        raise ComparisonValidationError(
            "duplicate_scenario_id",
            "scenario_id values must be unique",
        )
    if baseline_scenario_id not in identifiers:
        raise ComparisonValidationError(
            "unknown_baseline",
            "baseline_scenario_id must identify one compared scenario",
        )
    for scenario in scenarios:
        if scenario.get("synthetic") is not True:
            raise ComparisonValidationError(
                "non_synthetic_scenario",
                "I4 comparison accepts only synthetic=true scenarios",
            )
        engine = scenario.get("engine", {})
        if engine.get("name") != "new_urbanization_microsim":
            raise ComparisonValidationError(
                "unsupported_engine",
                "I4 comparison requires new_urbanization_microsim",
            )
    _validate_work_budget(scenarios, repetitions)
    if not selected_metrics or len(selected_metrics) != len(set(selected_metrics)):
        raise ComparisonValidationError(
            "invalid_metric_selection",
            "selected metrics must be non-empty and unique",
        )
    unknown_metrics = sorted(set(selected_metrics) - set(metric_catalog))
    if unknown_metrics:
        raise ComparisonValidationError(
            "unknown_metric",
            "unknown selected metrics: " + ", ".join(unknown_metrics),
        )
    context_digests = {
        str(scenario["scenario_id"]): _digest(_comparison_context(scenario, mode))
        for scenario in scenarios
    }
    if len(set(context_digests.values())) != 1:
        details = tuple(
            {
                "field": f"scenarios.{identifier}",
                "message": digest,
                "code": "context_digest_mismatch",
            }
            for identifier, digest in sorted(context_digests.items())
        )
        raise ComparisonValidationError(
            "comparison_context_mismatch",
            f"scenarios are not comparable in {mode} mode",
            details,
        )


def _metric_summary(experiment: Mapping[str, Any], metric: str) -> dict[str, float]:
    """Return a standard summary for an outcome or simulated failure rate."""

    if metric == "failure_rate":
        value = float(experiment["failure_rate"])
        return {"mean": value, "std": 0.0, "p05": value, "p50": value, "p95": value}
    summary = experiment["outcome_summary"].get(metric)
    if not isinstance(summary, Mapping):
        raise ComparisonValidationError(
            "metric_not_produced",
            f"experiment did not produce selected metric: {metric}",
        )
    return {name: float(summary[name]) for name in ("mean", "std", "p05", "p50", "p95")}


def _directional_change(delta: float, direction: str) -> str:
    """Translate a mean delta into an explicit preferred-direction label."""

    if math.isclose(delta, 0.0, rel_tol=0.0, abs_tol=1e-12):
        return "unchanged"
    improved = delta > 0 if direction == "higher" else delta < 0
    return "improves" if improved else "worsens"


def _metric_comparison(
    experiments: Mapping[str, Mapping[str, Any]],
    scenario_order: Sequence[str],
    baseline_id: str,
    selected_metrics: Sequence[str],
    metric_catalog: Mapping[str, Any],
) -> dict[str, Any]:
    """Build aligned metric deltas without significance or causal claims."""

    results: dict[str, Any] = {}
    for metric in selected_metrics:
        metadata = metric_catalog[metric]
        baseline = _metric_summary(experiments[baseline_id], metric)
        entries: dict[str, Any] = {}
        means: dict[str, float] = {}
        for scenario_id in scenario_order:
            summary = _metric_summary(experiments[scenario_id], metric)
            delta = summary["mean"] - baseline["mean"]
            denominator = abs(baseline["mean"])
            delta_pct = delta / denominator * 100.0 if denominator > 1e-12 else None
            entries[scenario_id] = {
                **summary,
                "delta_from_baseline": delta,
                "delta_pct_from_baseline": delta_pct,
                "directional_change": _directional_change(delta, metadata["direction"]),
                "p05_p95_overlaps_baseline": not (
                    summary["p95"] < baseline["p05"]
                    or baseline["p95"] < summary["p05"]
                ),
            }
            means[scenario_id] = summary["mean"]
        preferred = (
            max(means.values())
            if metadata["direction"] == "higher"
            else min(means.values())
        )
        best = sorted(
            scenario_id
            for scenario_id, value in means.items()
            if math.isclose(value, preferred, rel_tol=1e-12, abs_tol=1e-12)
        )
        results[metric] = {
            "title": metadata["title"],
            "unit": metadata["unit"],
            "category": metadata["category"],
            "preferred_direction": metadata["direction"],
            "baseline_mean": baseline["mean"],
            "best_mean_scenario_ids": best,
            "scenarios": entries,
        }
    return results


def _pareto_front(
    experiments: Mapping[str, Mapping[str, Any]],
    scenario_order: Sequence[str],
    pareto_metrics: Sequence[str],
    metric_catalog: Mapping[str, Any],
) -> list[str]:
    """Return non-dominated scenarios under unweighted named objectives."""

    means = {
        scenario_id: {
            metric: _metric_summary(experiments[scenario_id], metric)["mean"]
            for metric in pareto_metrics
        }
        for scenario_id in scenario_order
    }

    def dominates(left: str, right: str) -> bool:
        no_worse = True
        strictly_better = False
        for metric in pareto_metrics:
            direction = metric_catalog[metric]["direction"]
            left_value = means[left][metric]
            right_value = means[right][metric]
            if direction == "higher":
                no_worse = no_worse and left_value >= right_value - 1e-12
                strictly_better = strictly_better or left_value > right_value + 1e-12
            else:
                no_worse = no_worse and left_value <= right_value + 1e-12
                strictly_better = strictly_better or left_value < right_value - 1e-12
        return no_worse and strictly_better

    return [
        candidate
        for candidate in scenario_order
        if not any(
            dominates(other, candidate)
            for other in scenario_order
            if other != candidate
        )
    ]


def _group_products(
    experiments: Mapping[str, Mapping[str, Any]],
    scenario_order: Sequence[str],
    baseline_id: str,
    group_metric: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build group deltas and within-scenario max-min disparities."""

    group_sets = [set(experiments[item]["group_summary"]) for item in scenario_order]
    common_groups = sorted(set.intersection(*group_sets))
    comparison: dict[str, Any] = {}
    for group in common_groups:
        baseline = float(
            experiments[baseline_id]["group_summary"][group][group_metric]["mean"]
        )
        comparison[group] = {
            "baseline_mean": baseline,
            "scenarios": {
                scenario_id: {
                    "mean": float(
                        experiments[scenario_id]["group_summary"][group][group_metric]["mean"]
                    ),
                    "delta_from_baseline": float(
                        experiments[scenario_id]["group_summary"][group][group_metric]["mean"]
                    )
                    - baseline,
                }
                for scenario_id in scenario_order
            },
        }
    disparities: dict[str, Any] = {}
    dimensions = sorted({group.split(":", 1)[0] for group in common_groups})
    for scenario_id in scenario_order:
        disparities[scenario_id] = {}
        for dimension in dimensions:
            values = {
                group: float(
                    experiments[scenario_id]["group_summary"][group][group_metric]["mean"]
                )
                for group in common_groups
                if group.startswith(f"{dimension}:")
            }
            minimum = min(values.values())
            maximum = max(values.values())
            disparities[scenario_id][dimension] = {
                "metric": group_metric,
                "minimum": minimum,
                "maximum": maximum,
                "max_min_gap": maximum - minimum,
                "worst_group_ids": sorted(
                    group
                    for group, value in values.items()
                    if math.isclose(value, minimum, rel_tol=1e-12, abs_tol=1e-12)
                ),
                "best_group_ids": sorted(
                    group
                    for group, value in values.items()
                    if math.isclose(value, maximum, rel_tol=1e-12, abs_tol=1e-12)
                ),
            }
    return comparison, disparities


def _risk_ledger(
    experiments: Mapping[str, Mapping[str, Any]],
    scenario_order: Sequence[str],
    thresholds: Mapping[str, float],
) -> dict[str, Any]:
    """Apply explicit synthetic warning thresholds to resource and risk stocks."""

    ledgers: dict[str, Any] = {}
    for scenario_id in scenario_order:
        experiment = experiments[scenario_id]
        values = {
            "failure_rate": float(experiment["failure_rate"]),
            "final_debt": _metric_summary(experiment, "final_debt")["mean"],
            "final_debt_to_revenue": _metric_summary(
                experiment, "final_debt_to_revenue"
            )["mean"],
            "final_fiscal_expenditure_ratio": _metric_summary(
                experiment, "final_fiscal_expenditure_ratio"
            )["mean"],
            "final_transfer_revenue": _metric_summary(
                experiment, "final_transfer_revenue"
            )["mean"],
            "final_used_construction_land": _metric_summary(
                experiment, "final_used_construction_land"
            )["mean"],
            "final_developable_land_share": _metric_summary(
                experiment, "final_developable_land_share"
            )["mean"],
            "final_reusable_stock_land": _metric_summary(
                experiment, "final_reusable_stock_land"
            )["mean"],
            "micro_service_access_rate_pct": _metric_summary(
                experiment, "micro_service_access_rate_pct"
            )["mean"],
            "micro_mean_housing_burden_ratio": _metric_summary(
                experiment, "micro_mean_housing_burden_ratio"
            )["mean"],
        }
        checks = (
            ("SIMULATED_FAILURE_RATE", "failure_rate", "gt", "max_failure_rate"),
            (
                "HIGH_DEBT_TO_REVENUE",
                "final_debt_to_revenue",
                "gt",
                "max_debt_to_revenue_pct",
            ),
            (
                "FISCAL_EXPENDITURE_PRESSURE",
                "final_fiscal_expenditure_ratio",
                "gt",
                "max_fiscal_expenditure_ratio_pct",
            ),
            (
                "LOW_DEVELOPABLE_LAND_BUFFER",
                "final_developable_land_share",
                "lt",
                "min_developable_land_share_pct",
            ),
            (
                "LOW_SERVICE_ACCESS",
                "micro_service_access_rate_pct",
                "lt",
                "min_service_access_rate_pct",
            ),
            (
                "HIGH_HOUSING_BURDEN",
                "micro_mean_housing_burden_ratio",
                "gt",
                "max_housing_burden_ratio",
            ),
        )
        flags: list[dict[str, Any]] = []
        for code, metric, operator, threshold_name in checks:
            threshold = float(thresholds[threshold_name])
            triggered = (
                values[metric] > threshold
                if operator == "gt"
                else values[metric] < threshold
            )
            if triggered:
                flags.append(
                    {
                        "code": code,
                        "severity": "warning",
                        "metric": metric,
                        "value": values[metric],
                        "threshold": threshold,
                        "operator": operator,
                    }
                )
        ledgers[scenario_id] = {
            "values": values,
            "risk_flag_count": len(flags),
            "risk_flags": flags,
        }
    return ledgers


def compare_scenarios(
    scenarios: Sequence[Mapping[str, Any]],
    *,
    comparison_id: str,
    name: str,
    comparison_mode: str,
    baseline_scenario_id: str,
    repetitions: int = 100,
    base_seed: int = 20260819,
    selected_metrics: Sequence[str] | None = None,
    risk_thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Compare two to nine synthetic scenarios under common random numbers."""

    defaults = load_decision_defaults()
    catalog = defaults["metrics"]
    metrics = tuple(selected_metrics or defaults["decision_metrics"])
    thresholds = dict(defaults["risk_thresholds"])
    if risk_thresholds is not None:
        unknown = sorted(set(risk_thresholds) - set(thresholds))
        if unknown:
            raise ComparisonValidationError(
                "unknown_risk_threshold",
                "unknown risk thresholds: " + ", ".join(unknown),
            )
        thresholds.update(
            {key: _number(value, key) for key, value in risk_thresholds.items()}
        )
    _validate_inputs(
        scenarios,
        comparison_id,
        comparison_mode,
        baseline_scenario_id,
        repetitions,
        base_seed,
        metrics,
        catalog,
    )
    scenario_order = [str(scenario["scenario_id"]) for scenario in scenarios]
    experiments: dict[str, Mapping[str, Any]] = {}
    scenario_summaries: dict[str, Any] = {}
    for scenario in scenarios:
        scenario_id = str(scenario["scenario_id"])
        experiment = run_experiment(
            scenario,
            repetitions=repetitions,
            base_seed=base_seed,
        )
        if experiment["successful_runs"] == 0:
            raise ComparisonValidationError(
                "no_successful_runs",
                f"scenario has no successful repetitions: {scenario_id}",
            )
        experiments[scenario_id] = experiment
        scenario_summaries[scenario_id] = {
            "name": scenario["name"],
            "scenario_code": scenario.get("scenario_code"),
            "scenario_input_digest": _digest(scenario),
            "experiment_id": experiment["experiment_id"],
            "experiment_input_digest": experiment["input_digest"],
            "successful_runs": experiment["successful_runs"],
            "failed_runs": experiment["failed_runs"],
            "failure_rate": experiment["failure_rate"],
            "selected_outcomes": {
                metric: _metric_summary(experiment, metric) for metric in metrics
            },
        }
    metric_results = _metric_comparison(
        experiments,
        scenario_order,
        baseline_scenario_id,
        metrics,
        catalog,
    )
    group_metric = str(defaults["group_metric"])
    group_comparison, group_disparities = _group_products(
        experiments,
        scenario_order,
        baseline_scenario_id,
        group_metric,
    )
    ledger = _risk_ledger(experiments, scenario_order, thresholds)
    pareto_metrics = tuple(defaults["pareto_metrics"])
    pareto = _pareto_front(experiments, scenario_order, pareto_metrics, catalog)
    request_snapshot = {
        "comparison_id": comparison_id,
        "name": name,
        "comparison_mode": comparison_mode,
        "baseline_scenario_id": baseline_scenario_id,
        "scenario_digests": {
            str(scenario["scenario_id"]): _digest(scenario) for scenario in scenarios
        },
        "repetitions": repetitions,
        "base_seed": base_seed,
        "selected_metrics": list(metrics),
        "risk_thresholds": thresholds,
    }
    warnings: list[dict[str, str]] = [
        {
            "code": "SYNTHETIC_COMPARISON",
            "severity": "warning",
            "message": "方案比较来自合成数据与假设，不是对真实地区的预测或排序。",
        },
        {
            "code": "NO_COMPOSITE_SCORE",
            "severity": "info",
            "message": "系统不生成隐藏综合分，只报告分目标结果与非支配方案。",
        },
        {
            "code": "COMMON_RANDOM_NUMBERS",
            "severity": "info",
            "message": "各方案使用相同基础种子序列，以降低随机比较噪声。",
        },
    ]
    if comparison_mode == "joint":
        warnings.append(
            {
                "code": "JOINT_CHANGE_ATTRIBUTION_LIMIT",
                "severity": "warning",
                "message": "政策与压力同时变化，方案差异不能归因于单一工具。",
            }
        )
    if any(summary["failed_runs"] for summary in scenario_summaries.values()):
        warnings.append(
            {
                "code": "SUCCESS_CONDITIONAL_OUTCOMES",
                "severity": "warning",
                "message": "结果均值基于成功运行，必须与失效率并列解释。",
            }
        )
    return {
        "schema_version": "1.0.0",
        "comparison_id": comparison_id,
        "name": name,
        "comparison_mode": comparison_mode,
        "status": "succeeded",
        "input_digest": _digest(request_snapshot),
        "baseline_scenario_id": baseline_scenario_id,
        "scenario_order": scenario_order,
        "repetitions": repetitions,
        "base_seed": base_seed,
        "metric_catalog_version": defaults["metric_catalog_version"],
        "selected_metrics": list(metrics),
        "pareto_metrics": list(pareto_metrics),
        "scenario_summaries": scenario_summaries,
        "metric_comparison": metric_results,
        "group_metric": group_metric,
        "group_comparison": group_comparison,
        "group_disparities": group_disparities,
        "risk_thresholds": thresholds,
        "resource_risk_ledger": ledger,
        "non_dominated_scenario_ids": pareto,
        "warnings": warnings,
        "reproducible": True,
        "usage_level": "Demo",
        "synthetic": True,
    }


def run_catalog_comparison(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve a compact S0-S8 comparison plan and run the public comparison."""

    known = {
        "schema_version",
        "comparison_id",
        "name",
        "comparison_mode",
        "baseline_key",
        "context",
        "scenario_specs",
        "selected_metrics",
        "risk_thresholds",
        "synthetic",
    }
    unknown = sorted(set(plan) - known)
    if unknown:
        raise ComparisonValidationError(
            "unknown_plan_field",
            "unknown comparison plan fields: " + ", ".join(unknown),
        )
    if plan.get("synthetic") is not True:
        raise ComparisonValidationError(
            "non_synthetic_plan",
            "comparison plan must set synthetic=true",
        )
    context = plan.get("context")
    specs = plan.get("scenario_specs")
    if not isinstance(context, Mapping) or not isinstance(specs, list):
        raise ComparisonValidationError(
            "invalid_plan_structure",
            "context must be an object and scenario_specs must be a list",
        )
    scenarios: list[dict[str, Any]] = []
    keys: list[str] = []
    for spec in specs:
        if not isinstance(spec, Mapping):
            raise ComparisonValidationError(
                "invalid_scenario_spec",
                "each scenario spec must be an object",
            )
        key = spec.get("key")
        if not isinstance(key, str) or not key:
            raise ComparisonValidationError("invalid_scenario_key", "scenario key is required")
        keys.append(key)
        scenario = build_microsim_scenario(
            str(spec.get("scenario_code")),
            pressures=tuple(spec.get("pressures", [])),
            archetype=str(context.get("archetype", "metropolitan_adjacent")),
            start_year=int(context.get("start_year", 2025)),
            random_seed=int(context.get("base_seed", 20260819)),
            sample_size=int(context.get("sample_size", 10000)),
        )
        scenario["scenario_id"] = f"synthetic-comparison-{key}"
        if isinstance(spec.get("title"), str) and spec["title"]:
            scenario["name"] = spec["title"]
        horizon = context.get("horizon_years")
        if horizon is not None:
            scenario["domain_config"]["horizon_years"] = int(horizon)
        scenarios.append(scenario)
    if len(keys) != len(set(keys)):
        raise ComparisonValidationError("duplicate_scenario_key", "scenario keys must be unique")
    baseline_key = plan.get("baseline_key")
    if baseline_key not in keys:
        raise ComparisonValidationError(
            "unknown_baseline_key",
            "baseline_key must identify one scenario spec",
        )
    return compare_scenarios(
        scenarios,
        comparison_id=str(plan.get("comparison_id", "")),
        name=str(plan.get("name", "")),
        comparison_mode=str(plan.get("comparison_mode", "")),
        baseline_scenario_id=f"synthetic-comparison-{baseline_key}",
        repetitions=int(context.get("repetitions", 100)),
        base_seed=int(context.get("base_seed", 20260819)),
        selected_metrics=plan.get("selected_metrics"),
        risk_thresholds=plan.get("risk_thresholds"),
    )
