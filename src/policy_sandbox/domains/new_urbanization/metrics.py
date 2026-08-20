"""Decision-facing aggregate metrics for synthetic county states."""

from policy_sandbox.domains.new_urbanization.state import CountyState


def _ratio(numerator: float, denominator: float) -> float:
    """Return a safe ratio, using zero for a zero denominator."""

    return numerator / denominator if denominator else 0.0


def compute_metrics(state: CountyState) -> dict[str, float]:
    """Compute comparable indicators and auditable stocks from one state."""

    total_revenue = state.fiscal_revenue + state.transfer_revenue
    total_expenditure = state.operating_expenditure + state.capital_expenditure
    land_envelope = (
        state.used_construction_land
        + state.developable_land
        + state.ecological_protected_land
    )
    return {
        "total_population": state.total_population,
        "urban_residents": state.urban_residents,
        "urban_hukou_residents": state.urban_hukou_residents,
        "jobs": state.jobs,
        "housing_units": state.housing_units,
        "education_capacity": state.education_capacity,
        "health_capacity": state.health_capacity,
        "transfer_revenue": state.transfer_revenue,
        "debt": state.debt,
        "used_construction_land": state.used_construction_land,
        "developable_land": state.developable_land,
        "reusable_stock_land": state.reusable_stock_land,
        "urbanization_rate": _ratio(state.urban_residents, state.total_population) * 100.0,
        "urban_hukou_gap": max(0.0, state.urban_residents - state.urban_hukou_residents),
        "employment_rate": _ratio(
            state.employed_population,
            state.working_age_population,
        )
        * 100.0,
        "job_vacancy_rate": _ratio(
            max(0.0, state.jobs - state.employed_population),
            state.jobs,
        )
        * 100.0,
        "housing_occupancy_rate": _ratio(
            state.occupied_housing_units,
            state.housing_units,
        )
        * 100.0,
        "affordable_housing_share": _ratio(
            state.affordable_housing_units,
            state.housing_units,
        )
        * 100.0,
        "education_capacity_per_1000": _ratio(
            state.education_capacity,
            state.total_population,
        )
        * 1000.0,
        "health_capacity_per_1000": _ratio(
            state.health_capacity,
            state.total_population,
        )
        * 1000.0,
        "fiscal_expenditure_ratio": _ratio(total_expenditure, total_revenue) * 100.0,
        "debt_to_revenue": _ratio(state.debt, total_revenue) * 100.0,
        "developable_land_share": _ratio(state.developable_land, land_envelope) * 100.0,
        "reusable_stock_land_share": _ratio(
            state.reusable_stock_land,
            state.used_construction_land,
        )
        * 100.0,
    }

