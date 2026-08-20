"""Overall and grouped metrics for a weighted synthetic household cohort."""

from collections.abc import Callable, Iterable

from policy_sandbox.domains.new_urbanization.microsim.state import (
    Household,
    HouseholdCohort,
    assert_cohort,
)


def _rate(numerator: float, denominator: float) -> float:
    """Return a bounded percentage, or zero for an empty denominator."""

    if denominator <= 0:
        return 0.0
    return min(max(numerator / denominator * 100.0, 0.0), 100.0)


def _service_access(household: Household) -> bool:
    """Return whether relevant education and health access are both available."""

    return household.health_access and (
        household.children == 0 or household.education_access
    )


def _stable_citizenized(household: Household) -> bool:
    """Apply the synthetic stable-citizenization outcome definition."""

    return (
        household.origin_status != "local_urban"
        and household.stable_resident
        and household.settled
        and household.employed_adults > 0
        and household.housing_secure
        and _service_access(household)
    )


def _family_group(household: Household) -> str:
    """Return a mutually exclusive synthetic family-structure label."""

    if household.children > 0 and household.elderly > 0:
        return "children_and_elderly"
    if household.children > 0:
        return "with_children"
    if household.elderly > 0:
        return "with_elderly"
    return "working_only"


def _metrics_for_households(
    households: Iterable[Household],
    weight: float,
    total_population: float,
) -> dict[str, float]:
    """Compute a stable metric set for any household subset."""

    values = tuple(households)
    represented_households = len(values) * weight
    represented_population = sum(value.size for value in values) * weight
    working_age = sum(value.working_age_adults for value in values) * weight
    employed = sum(value.employed_adults for value in values) * weight
    nonlocal_stable = sum(
        1
        for value in values
        if value.origin_status != "local_urban" and value.stable_resident
    ) * weight
    settled = sum(
        1
        for value in values
        if value.origin_status != "local_urban"
        and value.stable_resident
        and value.settled
    ) * weight
    secure = sum(value.housing_secure for value in values) * weight
    service = sum(_service_access(value) for value in values) * weight
    citizenized = sum(_stable_citizenized(value) for value in values) * weight
    burden = sum(value.housing_burden_ratio for value in values)
    elderly = sum(value.elderly for value in values) * weight
    education_users = sum(
        value.children for value in values if value.education_access
    ) * weight
    health_users = sum(value.size for value in values if value.health_access) * weight
    return {
        "represented_households": represented_households,
        "represented_population": represented_population,
        "population_share_pct": _rate(represented_population, total_population),
        "employment_rate_pct": _rate(employed, working_age),
        "nonlocal_stable_households": nonlocal_stable,
        "settlement_rate_pct": _rate(settled, nonlocal_stable),
        "housing_security_rate_pct": _rate(secure, represented_households),
        "service_access_rate_pct": _rate(service, represented_households),
        "stable_citizenized_households": citizenized,
        "stable_citizenization_rate_pct": _rate(citizenized, nonlocal_stable),
        "mean_housing_burden_ratio": burden / len(values) if values else 0.0,
        "elderly_share_pct": _rate(elderly, represented_population),
        "represented_employed_adults": employed,
        "represented_education_users": education_users,
        "represented_health_users": health_users,
    }


def compute_household_outcomes(cohort: HouseholdCohort) -> dict[str, float]:
    """Compute overall outcomes and reconciliation diagnostics."""

    assert_cohort(cohort)
    outcomes = _metrics_for_households(
        cohort.households,
        cohort.household_weight,
        cohort.represented_population,
    )
    outcomes.update(
        {
            "sample_households": float(cohort.sample_households),
            "sample_population": float(cohort.sample_population),
            "household_weight": cohort.household_weight,
        }
    )
    return outcomes


def compute_group_outcomes(
    cohort: HouseholdCohort,
) -> dict[str, dict[str, float]]:
    """Compute outcomes by skill, origin, family structure, and location."""

    assert_cohort(cohort)
    dimensions: dict[str, Callable[[Household], str]] = {
        "skill": lambda household: household.skill_level,
        "origin": lambda household: household.origin_status,
        "family": _family_group,
        "zone": lambda household: household.zone,
    }
    results: dict[str, dict[str, float]] = {}
    for dimension, getter in dimensions.items():
        labels = sorted({getter(household) for household in cohort.households})
        for label in labels:
            subset = tuple(
                household
                for household in cohort.households
                if getter(household) == label
            )
            results[f"{dimension}:{label}"] = _metrics_for_households(
                subset,
                cohort.household_weight,
                cohort.represented_population,
            )
    return results
