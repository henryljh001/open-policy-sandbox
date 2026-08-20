"""Rule engine for explicit synthetic new-urbanization policy packages."""

from typing import Any, Mapping

from policy_sandbox.domain.models import EngineDescriptor, SimulationResult
from policy_sandbox.domains.new_urbanization import (
    BaselineRates,
    SyntheticCountyFactory,
    advance_one_year,
    compute_metrics,
)
from policy_sandbox.domains.new_urbanization.compiler import compile_policy_package
from policy_sandbox.plugins.base import SimulationEngine
from policy_sandbox.plugins.registry import DomainPluginFactory, register_engine


@register_engine("new_urbanization_policy_rules")
class NewUrbanizationPolicyRulesEngine(SimulationEngine):
    """Apply compiled synthetic rate assumptions to the conserved baseline."""

    descriptor = EngineDescriptor(name="new_urbanization_policy_rules", version="0.3.0")

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        super().__init__(cfg)
        if cfg.get("strict_invariants", True) is not True:
            raise ValueError("strict_invariants cannot be disabled")

    def run(self, scenario: Mapping[str, Any]) -> SimulationResult:
        """Compile, bound, and run one synthetic policy package."""

        if scenario.get("synthetic") is not True:
            raise ValueError("new_urbanization_policy_rules accepts only synthetic=true scenarios")
        domain_config = scenario["domain_config"]
        DomainPluginFactory("new_urbanization", domain_config)
        archetype = scenario.get("archetype") or domain_config.get("county_type")
        state = SyntheticCountyFactory(
            {
                "archetype": archetype,
                "start_year": scenario.get("start_year", 2025),
                "population_scale": scenario.get("population_scale", 1.0),
            }
        ).create()
        initial_metrics = compute_metrics(state)
        baseline_rates = BaselineRates.from_mapping(scenario.get("baseline_rates", {}))
        compiled = compile_policy_package(scenario["policy_package"], baseline_rates)
        policy_rates = compiled.apply_to(baseline_rates)

        invariant_checks = 0
        for _ in range(domain_config["horizon_years"]):
            state, _flow = advance_one_year(state, policy_rates)
            invariant_checks += 1

        final_metrics = compute_metrics(state)
        outcomes = {f"final_{name}": value for name, value in final_metrics.items()}
        outcomes.update(
            {
                "years_simulated": float(domain_config["horizon_years"]),
                "invariant_checks_passed": float(invariant_checks),
                "active_interventions": float(len(compiled.intervention_names)),
                "compiler_warning_count": float(len(compiled.warnings)),
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
        for name, value in compiled.tracked_adjustments.items():
            outcomes[f"assumption_{name}"] = value

        warnings: tuple[Mapping[str, str], ...] = (
            {
                "code": "SYNTHETIC_POLICY_SCENARIO",
                "severity": "warning",
                "message": "结果来自合成县域和显式假设，不代表任何真实地区。",
            },
            {
                "code": "POLICY_EFFECTS_ARE_ASSUMPTIONS",
                "severity": "warning",
                "message": "政策参数只用于方向测试，未经过经验或因果识别。",
            },
            *compiled.warnings,
        )
        return SimulationResult(outcomes=outcomes, warnings=warnings)
