"""Deterministic no-policy baseline for the synthetic new-urbanization domain."""

from typing import Any, Mapping

from policy_sandbox.domain.models import EngineDescriptor, SimulationResult
from policy_sandbox.domains.new_urbanization import (
    BaselineRates,
    SyntheticCountyFactory,
    advance_one_year,
    compute_metrics,
)
from policy_sandbox.plugins.base import SimulationEngine
from policy_sandbox.plugins.registry import DomainPluginFactory, register_engine


@register_engine("new_urbanization_baseline")
class NewUrbanizationBaselineEngine(SimulationEngine):
    """Run a synthetic county baseline from configuration only."""

    descriptor = EngineDescriptor(name="new_urbanization_baseline", version="0.2.0")

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        super().__init__(cfg)
        if cfg.get("strict_invariants", True) is not True:
            raise ValueError("strict_invariants cannot be disabled")

    def run(self, scenario: Mapping[str, Any]) -> SimulationResult:
        """Run a deterministic annual baseline and return final indicators."""

        if scenario.get("synthetic") is not True:
            raise ValueError("new_urbanization_baseline accepts only synthetic=true scenarios")

        domain_config = scenario["domain_config"]
        DomainPluginFactory("new_urbanization", domain_config)
        archetype = scenario.get("archetype") or domain_config.get("county_type")
        factory = SyntheticCountyFactory(
            {
                "archetype": archetype,
                "start_year": scenario.get("start_year", 2025),
                "population_scale": scenario.get("population_scale", 1.0),
            }
        )
        state = factory.create()
        initial_metrics = compute_metrics(state)
        rates = BaselineRates.from_mapping(scenario.get("baseline_rates", {}))

        invariant_checks = 0
        for _ in range(domain_config["horizon_years"]):
            state, _flow = advance_one_year(state, rates)
            invariant_checks += 1

        final_metrics = compute_metrics(state)
        outcomes = {f"final_{name}": value for name, value in final_metrics.items()}
        outcomes.update(
            {
                "years_simulated": float(domain_config["horizon_years"]),
                "invariant_checks_passed": float(invariant_checks),
                "population_change_pct": (
                    final_metrics["total_population"]
                    / initial_metrics["total_population"]
                    - 1.0
                )
                * 100.0,
                "urbanization_change_pp": (
                    final_metrics["urbanization_rate"]
                    - initial_metrics["urbanization_rate"]
                ),
                "urban_hukou_gap_change": (
                    final_metrics["urban_hukou_gap"]
                    - initial_metrics["urban_hukou_gap"]
                ),
            }
        )
        warnings = (
            {
                "code": "SYNTHETIC_DOMAIN_BASELINE",
                "severity": "warning",
                "message": "结果来自合成县域原型，不代表任何真实地区。",
            },
            {
                "code": "NO_POLICY_EFFECTS",
                "severity": "info",
                "message": "当前引擎只运行无政策冲击基线，不估计干预因果效应。",
            },
        )
        return SimulationResult(outcomes=outcomes, warnings=warnings)
