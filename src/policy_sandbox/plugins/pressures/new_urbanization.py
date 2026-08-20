"""Five explicit synthetic pressures for the new-urbanization microsimulation."""

import math
from typing import Any, ClassVar, Mapping

from policy_sandbox.domain.models import PressureDescriptor, PressureEffect
from policy_sandbox.plugins.base import PressureScenario
from policy_sandbox.plugins.registry import register_pressure


def _numeric_mapping(value: Any, field_name: str) -> dict[str, float]:
    """Validate a JSON object whose values must be finite numbers."""

    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    parsed: dict[str, float] = {}
    for name, raw in value.items():
        if not isinstance(name, str) or not name:
            raise TypeError(f"{field_name} keys must be non-empty strings")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise TypeError(f"{field_name}.{name} must be numeric")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError(f"{field_name}.{name} must be finite")
        parsed[name] = number
    return parsed


class _SyntheticPressure(PressureScenario):
    """Compile only explicit, intensity-scaled synthetic pressure assumptions."""

    allowed_rates: ClassVar[frozenset[str]] = frozenset()
    allowed_behaviors: ClassVar[frozenset[str]] = frozenset()

    def compile(self) -> PressureEffect:
        """Validate and scale rate and household-behavior deltas."""

        if self.cfg.get("synthetic_assumption") is not True:
            raise ValueError("pressure config must set synthetic_assumption=true")
        intensity_raw = self.cfg.get("intensity")
        if (
            isinstance(intensity_raw, bool)
            or not isinstance(intensity_raw, (int, float))
            or not 0.0 < float(intensity_raw) <= 1.0
        ):
            raise ValueError("intensity must be a number greater than 0 and at most 1")
        intensity = float(intensity_raw)
        rates = _numeric_mapping(self.cfg.get("rate_deltas", {}), "rate_deltas")
        behaviors = _numeric_mapping(
            self.cfg.get("behavior_deltas", {}),
            "behavior_deltas",
        )
        if not rates and not behaviors:
            raise ValueError("pressure must define an explicit synthetic effect")

        unknown_rates = sorted(set(rates) - self.allowed_rates)
        if unknown_rates:
            raise ValueError("unsupported rate_deltas: " + ", ".join(unknown_rates))
        unknown_behaviors = sorted(set(behaviors) - self.allowed_behaviors)
        if unknown_behaviors:
            raise ValueError(
                "unsupported behavior_deltas: " + ", ".join(unknown_behaviors)
            )
        return PressureEffect(
            rate_deltas={name: value * intensity for name, value in rates.items()},
            behavior_deltas={
                name: value * intensity for name, value in behaviors.items()
            },
            tags=(self.descriptor.name, "synthetic_assumption"),
        )


@register_pressure("employment_downturn")
class EmploymentDownturnPressure(_SyntheticPressure):
    """Reduce job growth, employment matching, and local revenue growth."""

    descriptor = PressureDescriptor(
        name="employment_downturn",
        version="0.4.0",
        domain="new_urbanization",
        title="就业下行",
    )
    allowed_rates = frozenset(
        {"employment_rate", "job_growth_rate", "fiscal_revenue_growth_rate"}
    )
    allowed_behaviors = frozenset(
        {"employment_probability", "migration_out_probability"}
    )


@register_pressure("fiscal_tightening")
class FiscalTighteningPressure(_SyntheticPressure):
    """Reduce transfers and service or housing implementation capacity."""

    descriptor = PressureDescriptor(
        name="fiscal_tightening",
        version="0.4.0",
        domain="new_urbanization",
        title="财政收紧",
    )
    allowed_rates = frozenset(
        {
            "transfer_growth_rate",
            "fiscal_revenue_growth_rate",
            "capital_expenditure_share",
            "education_growth_rate",
            "health_growth_rate",
        }
    )
    allowed_behaviors = frozenset(
        {"housing_security_probability", "service_access_probability"}
    )


@register_pressure("migration_surge")
class MigrationSurgePressure(_SyntheticPressure):
    """Increase migration inflow and near-term housing and service demand."""

    descriptor = PressureDescriptor(
        name="migration_surge",
        version="0.4.0",
        domain="new_urbanization",
        title="迁入超预期",
    )
    allowed_rates = frozenset({"net_migration_rate"})
    allowed_behaviors = frozenset(
        {
            "migration_in_probability",
            "housing_security_probability",
            "service_access_probability",
        }
    )


@register_pressure("population_aging")
class PopulationAgingPressure(_SyntheticPressure):
    """Increase household aging transitions and health-service demand."""

    descriptor = PressureDescriptor(
        name="population_aging",
        version="0.4.0",
        domain="new_urbanization",
        title="人口老龄化",
    )
    allowed_rates = frozenset({"working_age_share", "death_rate", "health_growth_rate"})
    allowed_behaviors = frozenset(
        {
            "aging_transition_probability",
            "employment_probability",
            "service_access_probability",
        }
    )


@register_pressure("extreme_disruption")
class ExtremeDisruptionPressure(_SyntheticPressure):
    """Represent a bounded extreme event and explicit run-failure risk."""

    descriptor = PressureDescriptor(
        name="extreme_disruption",
        version="0.4.0",
        domain="new_urbanization",
        title="极端事件扰动",
    )
    allowed_rates = frozenset(
        {
            "employment_rate",
            "job_growth_rate",
            "fiscal_revenue_growth_rate",
            "education_growth_rate",
            "health_growth_rate",
        }
    )
    allowed_behaviors = frozenset(
        {
            "employment_probability",
            "housing_security_probability",
            "service_access_probability",
            "run_failure_probability",
        }
    )
