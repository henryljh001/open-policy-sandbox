"""Parameterised synthetic household microsimulation for new urbanization."""

import math
import random
from typing import Any, Mapping

from policy_sandbox.domain.models import EngineDescriptor, SimulationResult
from policy_sandbox.domains.new_urbanization import (
    BaselineRates,
    SyntheticCountyFactory,
    advance_one_year,
    compute_metrics,
)
from policy_sandbox.domains.new_urbanization.compiler import compile_policy_package
from policy_sandbox.domains.new_urbanization.microsim import (
    HouseholdBehaviorEngine,
    SyntheticHouseholdFactory,
    assess_calibration,
    compute_group_outcomes,
    compute_household_outcomes,
)
from policy_sandbox.domains.new_urbanization.pressure_compiler import (
    compile_pressure_package,
)
from policy_sandbox.plugins.base import SimulationEngine
from policy_sandbox.plugins.registry import DomainPluginFactory, register_engine


@register_engine("new_urbanization_microsim")
class NewUrbanizationMicrosimulationEngine(SimulationEngine):
    """Combine aggregate accounting with a weighted synthetic household sample."""

    descriptor = EngineDescriptor(name="new_urbanization_microsim", version="0.4.0")

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        super().__init__(cfg)
        if cfg.get("strict_invariants", True) is not True:
            raise ValueError("strict_invariants cannot be disabled")

    def run(self, scenario: Mapping[str, Any]) -> SimulationResult:
        """Run one stochastic synthetic household scenario."""

        if scenario.get("synthetic") is not True:
            raise ValueError("new_urbanization_microsim accepts only synthetic=true scenarios")
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
        policy = compile_policy_package(scenario["policy_package"], baseline_rates)
        policy_rates = policy.apply_to(baseline_rates)
        pressure = compile_pressure_package(
            scenario.get(
                "pressure_package",
                {"package_id": "empty", "pressures": [], "synthetic": True},
            ),
            policy_rates,
        )
        rates = pressure.apply_to(policy_rates)

        microsim_config = scenario.get("microsim_config")
        if not isinstance(microsim_config, Mapping):
            raise TypeError("microsim_config must be an object")
        if microsim_config.get("synthetic") is not True:
            raise ValueError("microsim_config must set synthetic=true")
        random_seed = scenario["random_seed"]
        if isinstance(random_seed, bool) or not isinstance(random_seed, int):
            raise TypeError("random_seed must be an integer")
        cohort = SyntheticHouseholdFactory(
            {
                "archetype": archetype,
                "sample_size": microsim_config.get("sample_size", 10000),
                "target_population": state.total_population,
                "random_seed": random_seed,
                "synthetic": True,
            }
        ).create()
        behavior = HouseholdBehaviorEngine(
            {
                "behavior": microsim_config["behavior"],
                "policy_adjustments": policy.tracked_adjustments,
                "pressure_deltas": pressure.behavior_deltas,
            }
        )
        rng = random.Random(random_seed + 1)
        invariant_checks = 0
        for _ in range(domain_config["horizon_years"]):
            state, _flow = advance_one_year(state, rates)
            cohort = cohort.reconcile_population(state.total_population)
            cohort = behavior.advance(cohort, state, rng)
            micro = compute_household_outcomes(cohort)
            self._assert_micro_capacity(micro, state, behavior)
            if not math.isclose(
                cohort.represented_population,
                state.total_population,
                rel_tol=0.0,
                abs_tol=1e-6,
            ):
                raise ValueError("household population weight did not reconcile")
            invariant_checks += 2

        final_metrics = compute_metrics(state)
        micro = compute_household_outcomes(cohort)
        groups = compute_group_outcomes(cohort)
        outcomes = {f"final_{name}": value for name, value in final_metrics.items()}
        outcomes.update({f"micro_{name}": value for name, value in micro.items()})
        outcomes.update(
            {
                "years_simulated": float(domain_config["horizon_years"]),
                "invariant_checks_passed": float(invariant_checks),
                "active_interventions": float(len(policy.intervention_names)),
                "active_pressures": float(len(pressure.pressure_names)),
                "population_change_pct": (
                    final_metrics["total_population"]
                    / initial_metrics["total_population"]
                    - 1.0
                )
                * 100.0,
            }
        )
        warnings: list[Mapping[str, str]] = [
            {
                "code": "SYNTHETIC_HOUSEHOLD_MICROSIM",
                "severity": "warning",
                "message": "家庭为无个人信息的合成样本，结果不是个人或地区预测。",
            },
            {
                "code": "AGGREGATE_ACCOUNTING_AUTHORITY",
                "severity": "info",
                "message": "人口、财政和土地守恒由聚合模型负责，家庭层用于分配分析。",
            },
            *policy.warnings,
            *pressure.warnings,
        ]
        calibration = microsim_config.get("calibration")
        if calibration is not None:
            if not isinstance(calibration, Mapping):
                raise TypeError("calibration must be an object")
            if calibration.get("synthetic_targets") is not True:
                raise ValueError("I3 calibration targets must set synthetic_targets=true")
            targets = calibration.get("targets")
            if not isinstance(targets, Mapping):
                raise TypeError("calibration.targets must be an object")
            assessment = assess_calibration(micro, targets)
            outcomes["calibration_pass_rate_pct"] = float(
                assessment["pass_rate_pct"]
            )
            outcomes["calibration_all_passed"] = float(
                bool(assessment["all_passed"])
            )
            warnings.append(
                {
                    "code": "SYNTHETIC_CALIBRATION_TARGETS",
                    "severity": "warning",
                    "message": "当前只验证校准接口，未完成真实数据经验校准。",
                }
            )
        return SimulationResult(
            outcomes=outcomes,
            group_outcomes=groups,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _assert_micro_capacity(
        outcomes: Mapping[str, float],
        state: Any,
        behavior: HouseholdBehaviorEngine,
    ) -> None:
        """Fail rather than silently exceed jobs, housing, education, or health."""

        tolerance = 1e-6
        limits = {
            "represented_employed_adults": state.jobs,
            "represented_households": state.housing_units,
            "represented_education_users": state.education_capacity,
            "represented_health_users": (
                state.health_capacity
                * behavior.parameters.health_population_per_bed_capacity
            ),
        }
        actuals = dict(outcomes)
        actuals["represented_households"] = (
            outcomes["represented_households"]
            * outcomes["housing_security_rate_pct"]
            / 100.0
        )
        for name, limit in limits.items():
            if actuals[name] > limit + tolerance:
                raise ValueError(f"microsim capacity exceeded: {name}")
