"""Deterministic decision brief and audit bundle for scenario comparisons."""

import hashlib
import json
from typing import Any, Mapping

from policy_sandbox import __version__
from policy_sandbox.application.compare_scenarios import ComparisonValidationError
from policy_sandbox.plugins.engines.new_urbanization_microsim import (
    NewUrbanizationMicrosimulationEngine,
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_comparison(comparison: Mapping[str, Any]) -> None:
    if comparison.get("schema_version") != "1.0.0":
        raise ComparisonValidationError(
            "unsupported_comparison_version",
            "decision products require comparison schema_version 1.0.0",
        )
    if comparison.get("status") != "succeeded":
        raise ComparisonValidationError(
            "comparison_not_succeeded",
            "decision products require a succeeded comparison",
        )
    if comparison.get("synthetic") is not True:
        raise ComparisonValidationError(
            "non_synthetic_comparison",
            "decision products accept only synthetic=true comparisons",
        )
    required = (
        "comparison_id",
        "scenario_order",
        "scenario_summaries",
        "metric_comparison",
        "group_disparities",
        "resource_risk_ledger",
        "non_dominated_scenario_ids",
    )
    missing = [name for name in required if name not in comparison]
    if missing:
        raise ComparisonValidationError(
            "incomplete_comparison",
            "comparison is missing required fields: " + ", ".join(missing),
        )


def _scenario_name(comparison: Mapping[str, Any], scenario_id: str) -> str:
    summary = comparison["scenario_summaries"][scenario_id]
    return str(summary.get("name") or scenario_id)


def _mean(comparison: Mapping[str, Any], scenario_id: str, metric: str) -> float:
    value = comparison["scenario_summaries"][scenario_id]["selected_outcomes"][metric]
    return float(value["mean"])


def _metric_finding(comparison: Mapping[str, Any], metric: str) -> dict[str, Any]:
    result = comparison["metric_comparison"][metric]
    best_ids = list(result["best_mean_scenario_ids"])
    best_id = best_ids[0]
    entry = result["scenarios"][best_id]
    return {
        "code": "BEST_MEAN_BY_METRIC",
        "title": str(result["title"]),
        "message": (
            f"{_scenario_name(comparison, best_id)} has the preferred mean for this "
            "metric; uncertainty and resource constraints remain material."
        ),
        "evidence": {
            "metric": metric,
            "scenario_ids": best_ids,
            "mean": float(entry["mean"]),
            "p05": float(entry["p05"]),
            "p95": float(entry["p95"]),
            "delta_from_baseline": float(entry["delta_from_baseline"]),
            "preferred_direction": str(result["preferred_direction"]),
        },
    }


def _largest_group_gap(comparison: Mapping[str, Any]) -> dict[str, Any]:
    candidates: list[tuple[float, str, str, Mapping[str, Any]]] = []
    for scenario_id, dimensions in comparison["group_disparities"].items():
        for dimension, result in dimensions.items():
            candidates.append((float(result["max_min_gap"]), scenario_id, dimension, result))
    gap, scenario_id, dimension, result = max(candidates, key=lambda item: item[0])
    return {
        "code": "LARGEST_GROUP_GAP",
        "title": "Largest observed group gap",
        "message": (
            f"{_scenario_name(comparison, scenario_id)} has the largest max-min gap "
            f"in the {dimension} grouping."
        ),
        "evidence": {
            "scenario_id": scenario_id,
            "dimension": dimension,
            "metric": str(result["metric"]),
            "max_min_gap": gap,
            "worst_group_ids": list(result["worst_group_ids"]),
            "best_group_ids": list(result["best_group_ids"]),
        },
    }


def _risk_finding(comparison: Mapping[str, Any]) -> dict[str, Any]:
    ledger = comparison["resource_risk_ledger"]
    maximum = max(int(item["risk_flag_count"]) for item in ledger.values())
    scenario_ids = sorted(
        scenario_id
        for scenario_id, item in ledger.items()
        if int(item["risk_flag_count"]) == maximum
    )
    return {
        "code": "MAX_RISK_FLAGS",
        "title": "Explicit resource and risk flags",
        "message": (
            f"{maximum} explicit threshold flags were observed in the most flagged "
            "scenario set; thresholds are visible assumptions, not policy standards."
        ),
        "evidence": {
            "scenario_ids": scenario_ids,
            "risk_flag_count": maximum,
        },
    }


def _distribution_rows(comparison: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_id in comparison["scenario_order"]:
        dimensions = comparison["group_disparities"][scenario_id]
        dimension, result = max(
            dimensions.items(),
            key=lambda item: float(item[1]["max_min_gap"]),
        )
        rows.append(
            {
                "scenario_id": scenario_id,
                "scenario_name": _scenario_name(comparison, scenario_id),
                "largest_gap_dimension": dimension,
                "metric": str(result["metric"]),
                "max_min_gap": float(result["max_min_gap"]),
                "worst_group_ids": list(result["worst_group_ids"]),
                "best_group_ids": list(result["best_group_ids"]),
            }
        )
    return rows


def build_decision_brief(comparison: Mapping[str, Any]) -> dict[str, Any]:
    """Build a compact, auditable brief without an overall score or ranking."""

    _validate_comparison(comparison)
    front = list(comparison["non_dominated_scenario_ids"])
    if len(front) == 1:
        headline = (
            f"{_scenario_name(comparison, front[0])} is the only option on the "
            "unweighted Pareto front; this is not a recommendation."
        )
        posture = "single_non_dominated_option"
    else:
        headline = (
            f"No single option dominates all reported objectives; {len(front)} options "
            "remain on the unweighted Pareto front."
        )
        posture = "tradeoff_review"

    focus_metrics = (
        "micro_stable_citizenization_rate_pct",
        "micro_employment_rate_pct",
        "micro_housing_security_rate_pct",
        "micro_service_access_rate_pct",
        "micro_mean_housing_burden_ratio",
        "final_debt_to_revenue",
        "final_developable_land_share",
        "failure_rate",
    )
    available_metrics = set(comparison["selected_metrics"])
    matrix: list[dict[str, Any]] = []
    front_set = set(front)
    for scenario_id in comparison["scenario_order"]:
        summary = comparison["scenario_summaries"][scenario_id]
        risk = comparison["resource_risk_ledger"][scenario_id]
        matrix.append(
            {
                "scenario_id": scenario_id,
                "scenario_name": _scenario_name(comparison, scenario_id),
                "scenario_code": summary.get("scenario_code"),
                "on_unweighted_pareto_front": scenario_id in front_set,
                "successful_runs": int(summary["successful_runs"]),
                "failed_runs": int(summary["failed_runs"]),
                "risk_flag_count": int(risk["risk_flag_count"]),
                "decision_means": {
                    metric: _mean(comparison, scenario_id, metric)
                    for metric in focus_metrics
                    if metric in available_metrics
                },
            }
        )

    failure_rates = {
        scenario_id: float(comparison["scenario_summaries"][scenario_id]["failure_rate"])
        for scenario_id in comparison["scenario_order"]
    }
    worst_failure = max(failure_rates.values())
    worst_ids = sorted(
        scenario_id
        for scenario_id, value in failure_rates.items()
        if value == worst_failure
    )
    brief: dict[str, Any] = {
        "schema_version": "1.0.0",
        "brief_id": f"brief-{comparison['input_digest'][:16]}",
        "comparison_id": comparison["comparison_id"],
        "title": f"Decision brief: {comparison['name']}",
        "decision_posture": posture,
        "headline": headline,
        "key_findings": [
            _metric_finding(comparison, "micro_stable_citizenization_rate_pct"),
            _risk_finding(comparison),
            _largest_group_gap(comparison),
        ],
        "scenario_matrix": matrix,
        "distributional_findings": _distribution_rows(comparison),
        "resource_risk_ledger": comparison["resource_risk_ledger"],
        "worst_case": {
            "metric": "failure_rate",
            "scenario_ids": worst_ids,
            "value": worst_failure,
        },
        "non_dominated_scenario_ids": front,
        "next_actions": [
            "Complete U6 external calibration before using real regional data.",
            "Review every risk threshold and document the responsible owner.",
            "Add value weights only when a human decision owner supplies and signs them.",
        ],
        "boundaries": [
            "Demo output from synthetic households and explicit assumptions.",
            "Pareto membership is unweighted and is not a policy recommendation.",
            "Group gaps are diagnostic outputs, not causal estimates.",
            "U6 calibration, U7 privacy review, and U8 human sign-off are incomplete.",
        ],
        "warnings": list(comparison["warnings"]),
        "input_digest": comparison["input_digest"],
        "not_a_recommendation": True,
        "reproducible": bool(comparison["reproducible"]),
        "usage_level": "Demo",
        "synthetic": True,
    }
    brief["brief_digest"] = _digest(brief)
    return brief


def build_audit_bundle(comparison: Mapping[str, Any]) -> dict[str, Any]:
    """Build a machine-readable audit trail for a completed comparison."""

    _validate_comparison(comparison)
    engine = NewUrbanizationMicrosimulationEngine.descriptor
    traces = []
    for scenario_id in comparison["scenario_order"]:
        summary = comparison["scenario_summaries"][scenario_id]
        traces.append(
            {
                "scenario_id": scenario_id,
                "scenario_code": summary.get("scenario_code"),
                "scenario_input_digest": summary["scenario_input_digest"],
                "experiment_id": summary["experiment_id"],
                "experiment_input_digest": summary["experiment_input_digest"],
                "successful_runs": int(summary["successful_runs"]),
                "failed_runs": int(summary["failed_runs"]),
            }
        )
    bundle: dict[str, Any] = {
        "schema_version": "1.0.0",
        "audit_id": f"audit-{comparison['input_digest'][:16]}",
        "comparison_id": comparison["comparison_id"],
        "comparison_input_digest": comparison["input_digest"],
        "comparison_output_digest": _digest(comparison),
        "component_versions": {
            "open_policy_sandbox": __version__,
            "comparison_interface": "1.0.0",
            "engine_plugin": {"name": engine.name, "version": engine.version},
            "metric_catalog": comparison["metric_catalog_version"],
        },
        "comparison_design": {
            "mode": comparison["comparison_mode"],
            "baseline_scenario_id": comparison["baseline_scenario_id"],
            "scenario_order": list(comparison["scenario_order"]),
            "repetitions": int(comparison["repetitions"]),
            "base_seed": int(comparison["base_seed"]),
            "common_random_numbers": True,
            "selected_metrics": list(comparison["selected_metrics"]),
            "pareto_metrics": list(comparison["pareto_metrics"]),
            "composite_score": None,
        },
        "scenario_traces": traces,
        "risk_thresholds": dict(comparison["risk_thresholds"]),
        "gates": [
            {
                "gate_id": "SYNTHETIC_ONLY",
                "result": "pass",
                "evidence": "comparison.synthetic=true",
            },
            {
                "gate_id": "COMMON_RANDOM_NUMBERS",
                "result": "pass",
                "evidence": "one base_seed is reused across scenario_order",
            },
            {
                "gate_id": "NO_HIDDEN_COMPOSITE_SCORE",
                "result": "pass",
                "evidence": "unweighted Pareto front; composite_score=null",
            },
            {
                "gate_id": "U6_EXTERNAL_CALIBRATION",
                "result": "not_passed",
                "evidence": "no real-data calibration adapter is attached",
            },
            {
                "gate_id": "U7_PRIVACY_REVIEW",
                "result": "not_passed",
                "evidence": "Demo scope uses synthetic data only",
            },
            {
                "gate_id": "U8_HUMAN_SIGNOFF",
                "result": "not_passed",
                "evidence": "human sign-off was not requested or recorded",
            },
        ],
        "warnings": list(comparison["warnings"]),
        "usage_level": "Demo",
        "synthetic": True,
    }
    bundle["audit_digest"] = _digest(bundle)
    return bundle


def _markdown_text(value: Any) -> str:
    """Encode one caller-derived value for a single Markdown text line."""

    text = " ".join(str(value).split())
    text = text.replace("\\", "\\\\")
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    for character in "`*_{}[]()#+-.!|":
        text = text.replace(character, f"\\{character}")
    return text


def render_decision_brief_markdown(brief: Mapping[str, Any]) -> str:
    """Render a stable, one-page-oriented Markdown view of a decision brief."""

    if brief.get("synthetic") is not True:
        raise ComparisonValidationError(
            "non_synthetic_brief",
            "Markdown rendering accepts only synthetic=true briefs",
        )

    def display(value: Any) -> str:
        if isinstance(value, float):
            return f"{value:.2f}"
        return _markdown_text(value)

    lines = [
        f"# {_markdown_text(brief['title'])}",
        "",
        "> **Demo / synthetic assumptions only. Not a recommendation.**",
        "",
        "## Decision signal",
        "",
        _markdown_text(brief["headline"]),
        "",
        "## Scenario matrix",
        "",
        "| Scenario | Pareto front | Stable citizenization (%) | Failure rate | Risk flags |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in brief["scenario_matrix"]:
        means = row["decision_means"]
        lines.append(
            "| {name} | {pareto} | {stable} | {failure} | {flags} |".format(
                name=_markdown_text(row["scenario_name"]),
                pareto="yes" if row["on_unweighted_pareto_front"] else "no",
                stable=display(means.get("micro_stable_citizenization_rate_pct", "n/a")),
                failure=display(means.get("failure_rate", "n/a")),
                flags=row["risk_flag_count"],
            )
        )
    lines.extend(["", "## Key findings", ""])
    for finding in brief["key_findings"]:
        lines.append(
            f"- **{_markdown_text(finding['title'])}**: "
            f"{_markdown_text(finding['message'])}"
        )
    lines.extend(
        [
            "",
            "## Distributional checks",
            "",
            "| Scenario | Largest gap dimension | Max-min gap | Worst group |",
            "|---|---|---:|---|",
        ]
    )
    for row in brief["distributional_findings"]:
        lines.append(
            "| {name} | {dimension} | {gap} | {groups} |".format(
                name=_markdown_text(row["scenario_name"]),
                dimension=_markdown_text(row["largest_gap_dimension"]),
                gap=display(row["max_min_gap"]),
                groups=", ".join(
                    _markdown_text(group) for group in row["worst_group_ids"]
                ),
            )
        )
    lines.extend(["", "## Boundaries and next actions", ""])
    lines.extend(f"- {_markdown_text(item)}" for item in brief["boundaries"])
    lines.extend(f"- Next: {_markdown_text(item)}" for item in brief["next_actions"])
    lines.extend(["", f"Audit digest: `{_markdown_text(brief['brief_digest'])}`", ""])
    return "\n".join(lines)


def build_decision_package(comparison: Mapping[str, Any]) -> dict[str, Any]:
    """Return the comparison, compact brief, Markdown, and audit bundle together."""

    brief = build_decision_brief(comparison)
    audit = build_audit_bundle(comparison)
    package = {
        "schema_version": "1.0.0",
        "comparison": dict(comparison),
        "decision_brief": brief,
        "decision_brief_markdown": render_decision_brief_markdown(brief),
        "audit_bundle": audit,
        "usage_level": "Demo",
        "synthetic": True,
    }
    package["package_digest"] = _digest(package)
    return package
