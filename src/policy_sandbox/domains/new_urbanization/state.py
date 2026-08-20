"""Typed aggregate state for the synthetic new-urbanization baseline."""

from dataclasses import asdict, dataclass, fields
from typing import Any, Mapping


def _number(value: Any, field_name: str) -> float:
    """Convert a JSON number to float while rejecting booleans."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


@dataclass(frozen=True)
class CountyState:
    """One synthetic county aggregate at the end of a calendar year.

    Population, jobs, housing, and service fields are counts. Fiscal fields
    are synthetic currency units. Land fields are synthetic area units.
    Values are deliberately not tied to any identifiable real county.
    """

    year: int
    county_type: str
    total_population: float
    urban_residents: float
    urban_hukou_residents: float
    working_age_population: float
    employed_population: float
    jobs: float
    housing_units: float
    occupied_housing_units: float
    affordable_housing_units: float
    education_capacity: float
    health_capacity: float
    fiscal_revenue: float
    transfer_revenue: float
    operating_expenditure: float
    capital_expenditure: float
    debt: float
    used_construction_land: float
    developable_land: float
    reusable_stock_land: float
    ecological_protected_land: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "CountyState":
        """Build a state from a JSON-compatible mapping."""

        year = value["year"]
        county_type = value["county_type"]
        if isinstance(year, bool) or not isinstance(year, int):
            raise TypeError("year must be an integer")
        if not isinstance(county_type, str) or not county_type:
            raise TypeError("county_type must be a non-empty string")

        numeric_names = {
            item.name for item in fields(cls) if item.name not in {"year", "county_type"}
        }
        numeric_values = {name: _number(value[name], name) for name in numeric_names}
        return cls(year=year, county_type=county_type, **numeric_values)

    def to_mapping(self) -> dict[str, int | float | str]:
        """Return a JSON-compatible state mapping."""

        return dict(asdict(self))


@dataclass(frozen=True)
class AnnualFlow:
    """Auditable flow ledger connecting two consecutive county states."""

    year: int
    births: float
    deaths: float
    net_migration: float
    urban_resident_change: float
    urban_hukou_change: float
    job_change: float
    housing_added: float
    education_capacity_added: float
    health_capacity_added: float
    fiscal_balance: float
    debt_change: float
    greenfield_land_used: float
    stock_land_reused: float

    def to_mapping(self) -> dict[str, int | float]:
        """Return a JSON-compatible flow mapping."""

        return dict(asdict(self))


@dataclass(frozen=True)
class BaselineRates:
    """Config-driven annual rates for a no-policy synthetic baseline."""

    birth_rate: float = 0.007
    death_rate: float = 0.008
    net_migration_rate: float = 0.0
    urbanization_change: float = 0.006
    hukou_conversion_rate: float = 0.08
    working_age_share: float = 0.62
    employment_rate: float = 0.74
    job_growth_rate: float = 0.01
    housing_growth_rate: float = 0.012
    affordable_share_of_new_housing: float = 0.12
    education_growth_rate: float = 0.008
    health_growth_rate: float = 0.01
    fiscal_revenue_growth_rate: float = 0.02
    transfer_growth_rate: float = 0.015
    operating_expenditure_growth_rate: float = 0.018
    capital_expenditure_share: float = 0.18
    construction_land_growth_rate: float = 0.006
    stock_land_reuse_rate: float = 0.04

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "BaselineRates":
        """Build and validate annual rates from configuration."""

        known = {item.name for item in fields(cls)}
        unknown = sorted(set(value) - known)
        if unknown:
            raise ValueError("Unknown baseline rates: " + ", ".join(unknown))
        parsed = {name: _number(raw, name) for name, raw in value.items()}
        rates = cls(**parsed)
        issues = rates.validate()
        if issues:
            raise ValueError("Invalid baseline rates: " + "; ".join(issues))
        return rates

    def validate(self) -> tuple[str, ...]:
        """Return domain violations for annual rates."""

        issues: list[str] = []
        bounded = {
            "birth_rate": (0.0, 0.1),
            "death_rate": (0.0, 0.1),
            "net_migration_rate": (-0.1, 0.1),
            "urbanization_change": (-0.05, 0.05),
            "hukou_conversion_rate": (0.0, 1.0),
            "working_age_share": (0.0, 1.0),
            "employment_rate": (0.0, 1.0),
            "job_growth_rate": (-0.2, 0.2),
            "housing_growth_rate": (0.0, 0.2),
            "affordable_share_of_new_housing": (0.0, 1.0),
            "education_growth_rate": (-0.1, 0.2),
            "health_growth_rate": (-0.1, 0.2),
            "fiscal_revenue_growth_rate": (-0.2, 0.3),
            "transfer_growth_rate": (-0.2, 0.3),
            "operating_expenditure_growth_rate": (-0.2, 0.3),
            "capital_expenditure_share": (0.0, 1.0),
            "construction_land_growth_rate": (0.0, 0.1),
            "stock_land_reuse_rate": (0.0, 1.0),
        }
        for name, (lower, upper) in bounded.items():
            value = getattr(self, name)
            if not lower <= value <= upper:
                issues.append(f"{name} must be between {lower} and {upper}")
        return tuple(issues)

