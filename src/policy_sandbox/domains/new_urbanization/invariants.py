"""State and transition invariants for auditable synthetic simulation."""

import math

from policy_sandbox.domains.new_urbanization.state import AnnualFlow, CountyState

ABSOLUTE_TOLERANCE = 1e-6


class StateInvariantError(ValueError):
    """Raised when a synthetic state or transition cannot be reconciled."""


def _close(left: float, right: float) -> bool:
    """Return whether two accounting values match within tolerance."""

    return math.isclose(left, right, rel_tol=1e-9, abs_tol=ABSOLUTE_TOLERANCE)


def state_issues(state: CountyState) -> tuple[str, ...]:
    """Return all detected cross-sectional state violations."""

    issues: list[str] = []
    numeric = state.to_mapping()
    for name, value in numeric.items():
        if name in {"year", "county_type"}:
            continue
        if not math.isfinite(float(value)):
            issues.append(f"{name} must be finite")
        elif float(value) < 0:
            issues.append(f"{name} must be non-negative")

    if state.urban_residents > state.total_population + ABSOLUTE_TOLERANCE:
        issues.append("urban_residents cannot exceed total_population")
    if state.urban_hukou_residents > state.urban_residents + ABSOLUTE_TOLERANCE:
        issues.append("urban_hukou_residents cannot exceed urban_residents")
    if state.working_age_population > state.total_population + ABSOLUTE_TOLERANCE:
        issues.append("working_age_population cannot exceed total_population")
    if state.employed_population > state.working_age_population + ABSOLUTE_TOLERANCE:
        issues.append("employed_population cannot exceed working_age_population")
    if state.employed_population > state.jobs + ABSOLUTE_TOLERANCE:
        issues.append("employed_population cannot exceed jobs")
    if state.occupied_housing_units > state.housing_units + ABSOLUTE_TOLERANCE:
        issues.append("occupied_housing_units cannot exceed housing_units")
    if state.affordable_housing_units > state.housing_units + ABSOLUTE_TOLERANCE:
        issues.append("affordable_housing_units cannot exceed housing_units")
    if state.reusable_stock_land > state.used_construction_land + ABSOLUTE_TOLERANCE:
        issues.append("reusable_stock_land cannot exceed used_construction_land")
    return tuple(issues)


def transition_issues(
    previous: CountyState,
    current: CountyState,
    flow: AnnualFlow,
) -> tuple[str, ...]:
    """Return accounting violations between consecutive annual states."""

    issues = list(state_issues(current))
    if current.year != previous.year + 1 or flow.year != current.year:
        issues.append("transition year must advance by exactly one")

    expected_population = (
        previous.total_population + flow.births - flow.deaths + flow.net_migration
    )
    if not _close(current.total_population, expected_population):
        issues.append("population stock does not reconcile with births, deaths, and migration")
    if not _close(current.urban_residents - previous.urban_residents, flow.urban_resident_change):
        issues.append("urban resident change does not reconcile")
    if not _close(
        current.urban_hukou_residents - previous.urban_hukou_residents,
        flow.urban_hukou_change,
    ):
        issues.append("urban hukou change does not reconcile")
    if not _close(current.jobs - previous.jobs, flow.job_change):
        issues.append("job stock does not reconcile")
    if not _close(current.housing_units - previous.housing_units, flow.housing_added):
        issues.append("housing stock does not reconcile")
    if not _close(
        current.education_capacity - previous.education_capacity,
        flow.education_capacity_added,
    ):
        issues.append("education capacity does not reconcile")
    if not _close(
        current.health_capacity - previous.health_capacity,
        flow.health_capacity_added,
    ):
        issues.append("health capacity does not reconcile")

    expected_debt = max(0.0, previous.debt - flow.fiscal_balance)
    if not _close(current.debt, expected_debt):
        issues.append("debt stock does not reconcile with the fiscal balance")
    if not _close(current.debt - previous.debt, flow.debt_change):
        issues.append("debt change does not reconcile")

    previous_land = (
        previous.used_construction_land
        + previous.developable_land
        + previous.ecological_protected_land
    )
    current_land = (
        current.used_construction_land
        + current.developable_land
        + current.ecological_protected_land
    )
    if not _close(previous_land, current_land):
        issues.append("land envelope is not conserved")
    if not _close(
        current.used_construction_land - previous.used_construction_land,
        flow.greenfield_land_used,
    ):
        issues.append("greenfield land conversion does not reconcile")
    if not _close(
        previous.reusable_stock_land - current.reusable_stock_land,
        flow.stock_land_reused,
    ):
        issues.append("stock land reuse does not reconcile")
    return tuple(issues)


def assert_state(state: CountyState) -> None:
    """Raise when a state violates any invariant."""

    issues = state_issues(state)
    if issues:
        raise StateInvariantError("Invalid county state: " + "; ".join(issues))


def assert_transition(previous: CountyState, current: CountyState, flow: AnnualFlow) -> None:
    """Raise when an annual transition violates any invariant."""

    issues = transition_issues(previous, current, flow)
    if issues:
        raise StateInvariantError("Invalid county transition: " + "; ".join(issues))

