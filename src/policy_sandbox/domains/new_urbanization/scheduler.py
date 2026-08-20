"""Versioned annual event order for the synthetic no-policy baseline."""

from dataclasses import replace

from policy_sandbox.domains.new_urbanization.invariants import assert_state, assert_transition
from policy_sandbox.domains.new_urbanization.state import (
    AnnualFlow,
    BaselineRates,
    CountyState,
)

EVENT_ORDER_VERSION = "1.0.0"


def _clamp(value: float, lower: float, upper: float) -> float:
    """Clamp a numeric value to a closed interval."""

    return min(max(value, lower), upper)


def advance_one_year(
    state: CountyState,
    rates: BaselineRates,
) -> tuple[CountyState, AnnualFlow]:
    """Advance population, economy, services, fiscal, and land once.

    Event order is population -> jobs -> housing -> services -> fiscal -> land.
    It is deterministic and intentionally contains no policy intervention.
    """

    assert_state(state)
    rate_issues = rates.validate()
    if rate_issues:
        raise ValueError("Invalid baseline rates: " + "; ".join(rate_issues))

    births = state.total_population * rates.birth_rate
    deaths = state.total_population * rates.death_rate
    net_migration = state.total_population * rates.net_migration_rate
    total_population = state.total_population + births - deaths + net_migration

    previous_urban_share = state.urban_residents / state.total_population
    urban_share = _clamp(previous_urban_share + rates.urbanization_change, 0.0, 1.0)
    urban_residents = total_population * urban_share
    hukou_gap = max(0.0, urban_residents - state.urban_hukou_residents)
    urban_hukou_residents = min(
        urban_residents,
        state.urban_hukou_residents + hukou_gap * rates.hukou_conversion_rate,
    )

    working_age_population = total_population * rates.working_age_share
    jobs = max(0.0, state.jobs * (1.0 + rates.job_growth_rate))
    employed_population = min(working_age_population * rates.employment_rate, jobs)

    housing_units = state.housing_units * (1.0 + rates.housing_growth_rate)
    housing_added = housing_units - state.housing_units
    occupied_housing_units = min(housing_units, urban_residents / 2.6)
    affordable_housing_units = min(
        housing_units,
        state.affordable_housing_units
        + housing_added * rates.affordable_share_of_new_housing,
    )

    education_capacity = max(
        0.0,
        state.education_capacity * (1.0 + rates.education_growth_rate),
    )
    health_capacity = max(0.0, state.health_capacity * (1.0 + rates.health_growth_rate))

    fiscal_revenue = max(
        0.0,
        state.fiscal_revenue * (1.0 + rates.fiscal_revenue_growth_rate),
    )
    transfer_revenue = max(
        0.0,
        state.transfer_revenue * (1.0 + rates.transfer_growth_rate),
    )
    operating_expenditure = max(
        0.0,
        state.operating_expenditure * (1.0 + rates.operating_expenditure_growth_rate),
    )
    total_revenue = fiscal_revenue + transfer_revenue
    capital_expenditure = total_revenue * rates.capital_expenditure_share
    fiscal_balance = total_revenue - operating_expenditure - capital_expenditure
    debt = max(0.0, state.debt - fiscal_balance)

    greenfield_land_used = min(
        state.developable_land,
        state.used_construction_land * rates.construction_land_growth_rate,
    )
    stock_land_reused = min(
        state.reusable_stock_land,
        state.reusable_stock_land * rates.stock_land_reuse_rate,
    )

    current = replace(
        state,
        year=state.year + 1,
        total_population=total_population,
        urban_residents=urban_residents,
        urban_hukou_residents=urban_hukou_residents,
        working_age_population=working_age_population,
        employed_population=employed_population,
        jobs=jobs,
        housing_units=housing_units,
        occupied_housing_units=occupied_housing_units,
        affordable_housing_units=affordable_housing_units,
        education_capacity=education_capacity,
        health_capacity=health_capacity,
        fiscal_revenue=fiscal_revenue,
        transfer_revenue=transfer_revenue,
        operating_expenditure=operating_expenditure,
        capital_expenditure=capital_expenditure,
        debt=debt,
        used_construction_land=state.used_construction_land + greenfield_land_used,
        developable_land=state.developable_land - greenfield_land_used,
        reusable_stock_land=state.reusable_stock_land - stock_land_reused,
    )
    flow = AnnualFlow(
        year=current.year,
        births=births,
        deaths=deaths,
        net_migration=net_migration,
        urban_resident_change=urban_residents - state.urban_residents,
        urban_hukou_change=urban_hukou_residents - state.urban_hukou_residents,
        job_change=jobs - state.jobs,
        housing_added=housing_added,
        education_capacity_added=education_capacity - state.education_capacity,
        health_capacity_added=health_capacity - state.health_capacity,
        fiscal_balance=fiscal_balance,
        debt_change=debt - state.debt,
        greenfield_land_used=greenfield_land_used,
        stock_land_reused=stock_land_reused,
    )
    assert_transition(state, current, flow)
    return current, flow

