"""Seven explicit synthetic policy levers for the new-urbanization MVP."""

import math
from typing import Any, ClassVar, Mapping

from policy_sandbox.domain.models import InterventionDescriptor, PolicyEffect
from policy_sandbox.plugins.base import PolicyIntervention
from policy_sandbox.plugins.registry import register_intervention


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


class _SyntheticRateIntervention(PolicyIntervention):
    """Compile explicit, intensity-scaled assumptions without hidden values."""

    allowed_rates: ClassVar[frozenset[str]] = frozenset()
    allowed_adjustments: ClassVar[frozenset[str]] = frozenset()

    def compile(self) -> PolicyEffect:
        """Validate and scale configured rate and tracked adjustments."""

        if self.cfg.get("synthetic_assumption") is not True:
            raise ValueError("intervention config must set synthetic_assumption=true")
        intensity_raw = self.cfg.get("intensity")
        if (
            isinstance(intensity_raw, bool)
            or not isinstance(intensity_raw, (int, float))
            or not 0.0 < float(intensity_raw) <= 1.0
        ):
            raise ValueError("intensity must be a number greater than 0 and at most 1")
        intensity = float(intensity_raw)
        rates = _numeric_mapping(self.cfg.get("rate_deltas", {}), "rate_deltas")
        adjustments = _numeric_mapping(
            self.cfg.get("tracked_adjustments", {}),
            "tracked_adjustments",
        )
        if not rates and not adjustments:
            raise ValueError("intervention must define an explicit synthetic effect")

        unknown_rates = sorted(set(rates) - self.allowed_rates)
        if unknown_rates:
            raise ValueError("unsupported rate_deltas: " + ", ".join(unknown_rates))
        unknown_adjustments = sorted(set(adjustments) - self.allowed_adjustments)
        if unknown_adjustments:
            raise ValueError(
                "unsupported tracked_adjustments: " + ", ".join(unknown_adjustments)
            )
        return PolicyEffect(
            rate_deltas={name: value * intensity for name, value in rates.items()},
            tracked_adjustments={
                name: value * intensity for name, value in adjustments.items()
            },
            tags=(self.descriptor.name, "synthetic_assumption"),
        )


@register_intervention("settlement_threshold")
class SettlementThresholdIntervention(_SyntheticRateIntervention):
    """Represent explicit assumptions about lowering settlement barriers."""

    descriptor = InterventionDescriptor(
        name="settlement_threshold",
        version="0.3.0",
        domain="new_urbanization",
        title="落户门槛调整",
    )
    allowed_rates = frozenset(
        {"hukou_conversion_rate", "net_migration_rate", "operating_expenditure_growth_rate"}
    )
    allowed_adjustments = frozenset({"settlement_access_gain_pp"})


@register_intervention("resident_based_service_eligibility")
class ResidentServiceEligibilityIntervention(_SyntheticRateIntervention):
    """Represent service eligibility linked to residence instead of hukou."""

    descriptor = InterventionDescriptor(
        name="resident_based_service_eligibility",
        version="0.3.0",
        domain="new_urbanization",
        title="常住人口服务资格",
    )
    allowed_rates = frozenset(
        {"education_growth_rate", "health_growth_rate", "operating_expenditure_growth_rate"}
    )
    allowed_adjustments = frozenset({"service_eligibility_gain_pp"})


@register_intervention("skills_and_employment_support")
class SkillsEmploymentIntervention(_SyntheticRateIntervention):
    """Represent training, matching, and employment-service assumptions."""

    descriptor = InterventionDescriptor(
        name="skills_and_employment_support",
        version="0.3.0",
        domain="new_urbanization",
        title="技能培训与就业支持",
    )
    allowed_rates = frozenset(
        {"employment_rate", "job_growth_rate", "operating_expenditure_growth_rate"}
    )
    allowed_adjustments = frozenset({"skill_match_gain_pp"})


@register_intervention("affordable_housing")
class AffordableHousingIntervention(_SyntheticRateIntervention):
    """Represent affordable-housing supply assumptions."""

    descriptor = InterventionDescriptor(
        name="affordable_housing",
        version="0.3.0",
        domain="new_urbanization",
        title="保障性住房供给",
    )
    allowed_rates = frozenset(
        {"housing_growth_rate", "affordable_share_of_new_housing", "capital_expenditure_share"}
    )
    allowed_adjustments = frozenset({"housing_burden_reduction_pp"})


@register_intervention("county_service_expansion")
class CountyServiceExpansionIntervention(_SyntheticRateIntervention):
    """Represent education and health capacity expansion assumptions."""

    descriptor = InterventionDescriptor(
        name="county_service_expansion",
        version="0.3.0",
        domain="new_urbanization",
        title="教育医疗容量扩容",
    )
    allowed_rates = frozenset(
        {
            "education_growth_rate",
            "health_growth_rate",
            "operating_expenditure_growth_rate",
            "capital_expenditure_share",
            "construction_land_growth_rate",
        }
    )
    allowed_adjustments = frozenset({"service_efficiency_gain_pp"})


@register_intervention("citizenization_transfer")
class CitizenizationTransferIntervention(_SyntheticRateIntervention):
    """Represent fiscal transfers linked to absorbed residents."""

    descriptor = InterventionDescriptor(
        name="citizenization_transfer",
        version="0.3.0",
        domain="new_urbanization",
        title="市民化转移支付",
    )
    allowed_rates = frozenset({"transfer_growth_rate"})
    allowed_adjustments = frozenset({"local_matching_burden_change_pp"})


@register_intervention("land_capacity_bundle")
class LandCapacityBundleIntervention(_SyntheticRateIntervention):
    """Represent bounded greenfield use and stock-land reuse assumptions."""

    descriptor = InterventionDescriptor(
        name="land_capacity_bundle",
        version="0.3.0",
        domain="new_urbanization",
        title="新增用地与存量盘活组合",
    )
    allowed_rates = frozenset(
        {"construction_land_growth_rate", "stock_land_reuse_rate", "capital_expenditure_share"}
    )
    allowed_adjustments = frozenset({"stock_efficiency_gain_pp"})
