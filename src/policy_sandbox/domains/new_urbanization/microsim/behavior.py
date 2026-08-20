"""Stochastic household transitions under explicit synthetic behavior rules."""

import math
import random
from dataclasses import asdict, dataclass, fields, replace
from typing import Any, Mapping

from policy_sandbox.domains.new_urbanization.microsim.state import (
    Household,
    HouseholdCohort,
    assert_cohort,
)
from policy_sandbox.domains.new_urbanization.state import CountyState


class MicrosimulationFailure(RuntimeError):
    """Raised when a configured pressure realizes an explicit run failure."""


def _number(value: Any, name: str) -> float:
    """Parse a finite numeric configuration value."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _clamp(value: float) -> float:
    """Clamp a probability to the closed unit interval."""

    return min(max(value, 0.0), 1.0)


@dataclass(frozen=True)
class BehaviorParameters:
    """Inspectable parameters for household migration and allocation choices."""

    migration_in_probability: float
    migration_out_probability: float
    employment_probability: float
    low_skill_employment_probability: float
    medium_skill_employment_probability: float
    high_skill_employment_probability: float
    employment_retention_bonus: float
    settlement_probability: float
    settlement_employment_bonus: float
    settlement_family_bonus: float
    service_eligibility_probability: float
    housing_security_probability: float
    housing_retention_bonus: float
    service_access_probability: float
    service_retention_bonus: float
    aging_transition_probability: float
    run_failure_probability: float
    health_population_per_bed_capacity: float
    secure_housing_burden_change: float
    insecure_housing_burden_change: float
    employed_income_growth: float
    unemployed_income_growth: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BehaviorParameters":
        """Build parameters from a complete mapping and reject unknown fields."""

        known = {item.name for item in fields(cls)}
        unknown = sorted(set(value) - known)
        missing = sorted(known - set(value))
        if unknown:
            raise ValueError("Unknown behavior parameters: " + ", ".join(unknown))
        if missing:
            raise ValueError("Missing behavior parameters: " + ", ".join(missing))
        parsed = {name: _number(raw, name) for name, raw in value.items()}
        parameters = cls(**parsed)
        issues = parameters.validate()
        if issues:
            raise ValueError("Invalid behavior parameters: " + "; ".join(issues))
        return parameters

    def validate(self) -> tuple[str, ...]:
        """Return parameter-domain violations."""

        issues: list[str] = []
        probabilities = {
            "migration_in_probability",
            "migration_out_probability",
            "low_skill_employment_probability",
            "medium_skill_employment_probability",
            "high_skill_employment_probability",
            "employment_retention_bonus",
            "settlement_probability",
            "settlement_employment_bonus",
            "settlement_family_bonus",
            "service_eligibility_probability",
            "housing_security_probability",
            "housing_retention_bonus",
            "service_access_probability",
            "service_retention_bonus",
            "aging_transition_probability",
            "run_failure_probability",
        }
        for name in probabilities:
            current = getattr(self, name)
            if not 0.0 <= current <= 1.0:
                issues.append(f"{name} must be between zero and one")
        if not -1.0 <= self.employment_probability <= 1.0:
            issues.append("employment_probability must be between minus one and one")
        if self.health_population_per_bed_capacity <= 0:
            issues.append("health_population_per_bed_capacity must be positive")
        bounded_changes = {
            "secure_housing_burden_change": self.secure_housing_burden_change,
            "insecure_housing_burden_change": self.insecure_housing_burden_change,
            "employed_income_growth": self.employed_income_growth,
            "unemployed_income_growth": self.unemployed_income_growth,
        }
        for name, current in bounded_changes.items():
            if not -1.0 <= current <= 1.0:
                issues.append(f"{name} must be between minus one and one")
        return tuple(issues)

    def apply_deltas(self, deltas: Mapping[str, float]) -> "BehaviorParameters":
        """Apply explicit pressure deltas and revalidate the parameter set."""

        values = {name: float(current) for name, current in asdict(self).items()}
        for name, delta in deltas.items():
            if name not in values:
                raise ValueError(f"Unknown behavior delta after compilation: {name}")
            values[name] += _number(delta, name)
        return BehaviorParameters.from_mapping(values)

    def with_policy_adjustments(
        self,
        tracked_adjustments: Mapping[str, float],
    ) -> "BehaviorParameters":
        """Map policy percentage-point assumptions to named probabilities."""

        values = {name: float(current) for name, current in asdict(self).items()}
        links = {
            "settlement_access_gain_pp": ("settlement_probability", 0.01),
            "service_eligibility_gain_pp": ("service_eligibility_probability", 0.01),
            "skill_match_gain_pp": ("employment_probability", 0.01),
            "housing_burden_reduction_pp": ("housing_security_probability", 0.01),
            "service_efficiency_gain_pp": ("service_access_probability", 0.01),
        }
        for adjustment, (parameter, multiplier) in links.items():
            if adjustment in tracked_adjustments:
                values[parameter] += float(tracked_adjustments[adjustment]) * multiplier
        for name in (
            "settlement_probability",
            "service_eligibility_probability",
            "housing_security_probability",
            "service_access_probability",
        ):
            values[name] = _clamp(values[name])
        values["employment_probability"] = min(
            max(values["employment_probability"], -1.0),
            1.0,
        )
        return BehaviorParameters.from_mapping(values)


class HouseholdBehaviorEngine:
    """Advance a weighted household sample without replacing aggregate accounting."""

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        behavior = cfg.get("behavior")
        if not isinstance(behavior, Mapping):
            raise TypeError("behavior must be an object")
        self.parameters = BehaviorParameters.from_mapping(behavior)
        pressure_deltas = cfg.get("pressure_deltas", {})
        if not isinstance(pressure_deltas, Mapping):
            raise TypeError("pressure_deltas must be an object")
        self.parameters = self.parameters.apply_deltas(pressure_deltas)
        policy_adjustments = cfg.get("policy_adjustments", {})
        if not isinstance(policy_adjustments, Mapping):
            raise TypeError("policy_adjustments must be an object")
        self.parameters = self.parameters.with_policy_adjustments(policy_adjustments)

    def advance(
        self,
        cohort: HouseholdCohort,
        county: CountyState,
        rng: random.Random,
    ) -> HouseholdCohort:
        """Advance migration, aging, jobs, settlement, housing, and services once."""

        assert_cohort(cohort)
        if rng.random() < self.parameters.run_failure_probability:
            raise MicrosimulationFailure("configured extreme disruption realized")
        weight = cohort.household_weight
        order = list(range(cohort.sample_households))
        rng.shuffle(order)
        job_slots = county.jobs / weight
        housing_slots = county.housing_units / weight
        education_slots = county.education_capacity / weight
        health_slots = (
            county.health_capacity
            * self.parameters.health_population_per_bed_capacity
            / weight
        )
        updated: list[Household | None] = [None] * cohort.sample_households
        for index in order:
            household = self._advance_household(
                cohort.households[index],
                rng,
                job_slots,
                housing_slots,
                education_slots,
                health_slots,
            )
            job_slots -= household.employed_adults
            if household.housing_secure:
                housing_slots -= 1
            if household.education_access:
                education_slots -= household.children
            if household.health_access:
                health_slots -= household.size
            updated[index] = household
        if any(household is None for household in updated):
            raise MicrosimulationFailure("household update order was incomplete")
        result = HouseholdCohort(
            households=tuple(household for household in updated if household is not None),
            household_weight=cohort.household_weight,
            random_seed=cohort.random_seed,
        ).reconcile_population(county.total_population)
        assert_cohort(result)
        return result

    def _advance_household(
        self,
        household: Household,
        rng: random.Random,
        job_slots: float,
        housing_slots: float,
        education_slots: float,
        health_slots: float,
    ) -> Household:
        """Advance one household under remaining aggregate capacities."""

        parameters = self.parameters
        zone = household.zone
        stable_resident = household.stable_resident
        settled = household.settled
        if zone == "neighboring_city" and rng.random() < parameters.migration_in_probability:
            zone = "county_seat" if rng.random() < 0.75 else "key_town"
            stable_resident = True
        elif stable_resident and rng.random() < parameters.migration_out_probability:
            zone = "neighboring_city"
            stable_resident = False
            settled = False

        aged = sum(
            1
            for _ in range(household.working_age_adults)
            if rng.random() < parameters.aging_transition_probability
        )
        working_age = household.working_age_adults - aged
        elderly = household.elderly + aged
        skill_probability = getattr(
            parameters,
            f"{household.skill_level}_skill_employment_probability",
        )
        employment_probability = skill_probability + parameters.employment_probability
        if household.employed_adults > 0:
            employment_probability += parameters.employment_retention_bonus
        employed = 0
        for _ in range(working_age):
            if job_slots - employed < 1:
                break
            if stable_resident and rng.random() < _clamp(employment_probability):
                employed += 1

        if stable_resident and household.origin_status != "local_urban" and not settled:
            settlement_probability = parameters.settlement_probability
            if employed > 0:
                settlement_probability += parameters.settlement_employment_bonus
            if household.children > 0 or elderly > 0:
                settlement_probability += parameters.settlement_family_bonus
            settled = rng.random() < _clamp(settlement_probability)
        service_eligible = household.origin_status == "local_urban" or settled
        if stable_resident and not service_eligible:
            service_eligible = rng.random() < parameters.service_eligibility_probability

        housing_probability = parameters.housing_security_probability
        if household.housing_secure:
            housing_probability += parameters.housing_retention_bonus
        housing_secure = (
            stable_resident
            and housing_slots >= 1
            and rng.random() < _clamp(housing_probability)
        )
        burden_change = (
            parameters.secure_housing_burden_change
            if housing_secure
            else parameters.insecure_housing_burden_change
        )
        housing_burden = _clamp(household.housing_burden_ratio + burden_change)

        access_probability = parameters.service_access_probability
        if household.education_access or household.health_access:
            access_probability += parameters.service_retention_bonus
        education_access = (
            service_eligible
            and (household.children == 0 or education_slots >= household.children)
            and rng.random() < _clamp(access_probability)
        )
        health_access = (
            service_eligible
            and health_slots >= household.size
            and rng.random() < _clamp(access_probability)
        )
        income_growth = (
            parameters.employed_income_growth
            if employed > 0
            else parameters.unemployed_income_growth
        )
        income = max(0.0, household.income_per_capita * (1.0 + income_growth))
        return replace(
            household,
            working_age_adults=working_age,
            elderly=elderly,
            zone=zone,
            employed_adults=employed,
            income_per_capita=income,
            housing_secure=housing_secure,
            housing_burden_ratio=housing_burden,
            service_eligible=service_eligible,
            education_access=education_access,
            health_access=health_access,
            settled=settled,
            stable_resident=stable_resident,
        )
