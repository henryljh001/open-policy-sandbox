"""Synthetic household state and non-bypassable cohort invariants."""

import math
from dataclasses import dataclass, replace

SKILL_LEVELS = frozenset({"low", "medium", "high"})
ORIGIN_STATUSES = frozenset({"local_urban", "local_rural", "migrant"})
ZONES = frozenset({"county_seat", "key_town", "rural", "neighboring_city"})
HOUSING_TENURES = frozenset({"owner", "renter", "affordable", "family"})


class CohortInvariantError(ValueError):
    """Raised when a household or cohort accounting invariant fails."""


@dataclass(frozen=True)
class Household:
    """One synthetic household record with no personal identifiers."""

    household_id: str
    size: int
    working_age_adults: int
    children: int
    elderly: int
    skill_level: str
    origin_status: str
    zone: str
    employed_adults: int
    income_per_capita: float
    housing_tenure: str
    housing_secure: bool
    housing_burden_ratio: float
    service_eligible: bool
    education_access: bool
    health_access: bool
    settled: bool
    stable_resident: bool

    def issues(self) -> tuple[str, ...]:
        """Return all household-level invariant violations."""

        issues: list[str] = []
        if not self.household_id:
            issues.append("household_id must be non-empty")
        if self.size < 1:
            issues.append("size must be at least one")
        composition = self.working_age_adults + self.children + self.elderly
        if composition != self.size:
            issues.append("working_age_adults + children + elderly must equal size")
        if min(self.working_age_adults, self.children, self.elderly) < 0:
            issues.append("household composition counts cannot be negative")
        if not 0 <= self.employed_adults <= self.working_age_adults:
            issues.append("employed_adults must not exceed working_age_adults")
        if self.skill_level not in SKILL_LEVELS:
            issues.append("unknown skill_level")
        if self.origin_status not in ORIGIN_STATUSES:
            issues.append("unknown origin_status")
        if self.zone not in ZONES:
            issues.append("unknown zone")
        if self.housing_tenure not in HOUSING_TENURES:
            issues.append("unknown housing_tenure")
        if not math.isfinite(self.income_per_capita) or self.income_per_capita < 0:
            issues.append("income_per_capita must be finite and non-negative")
        if not math.isfinite(self.housing_burden_ratio):
            issues.append("housing_burden_ratio must be finite")
        elif not 0.0 <= self.housing_burden_ratio <= 1.0:
            issues.append("housing_burden_ratio must be between zero and one")
        if self.zone == "neighboring_city" and self.stable_resident:
            issues.append("neighboring_city household cannot be a stable county resident")
        return tuple(issues)


@dataclass(frozen=True)
class HouseholdCohort:
    """A fixed synthetic sample reconciled to an aggregate population by weight."""

    households: tuple[Household, ...]
    household_weight: float
    random_seed: int
    synthetic: bool = True

    @property
    def sample_households(self) -> int:
        """Return the number of synthetic records."""

        return len(self.households)

    @property
    def sample_population(self) -> int:
        """Return unweighted sample population."""

        return sum(household.size for household in self.households)

    @property
    def represented_population(self) -> float:
        """Return aggregate population represented by the weighted sample."""

        return self.sample_population * self.household_weight

    def reconcile_population(self, target_population: float) -> "HouseholdCohort":
        """Adjust only the sample weight to match aggregate population exactly."""

        if not math.isfinite(target_population) or target_population <= 0:
            raise CohortInvariantError("target_population must be finite and positive")
        if self.sample_population <= 0:
            raise CohortInvariantError("sample population must be positive")
        return replace(
            self,
            household_weight=target_population / self.sample_population,
        )


def cohort_issues(cohort: HouseholdCohort) -> tuple[str, ...]:
    """Return cohort-level and nested household invariant violations."""

    issues: list[str] = []
    if cohort.synthetic is not True:
        issues.append("cohort must declare synthetic=true")
    if isinstance(cohort.random_seed, bool) or cohort.random_seed < 0:
        issues.append("random_seed must be a non-negative integer")
    if not cohort.households:
        issues.append("cohort must contain at least one household")
    if not math.isfinite(cohort.household_weight) or cohort.household_weight <= 0:
        issues.append("household_weight must be finite and positive")
    identifiers = [household.household_id for household in cohort.households]
    if len(identifiers) != len(set(identifiers)):
        issues.append("household_id values must be unique")
    for household in cohort.households:
        for issue in household.issues():
            issues.append(f"{household.household_id}: {issue}")
    return tuple(issues)


def assert_cohort(cohort: HouseholdCohort) -> None:
    """Raise when any synthetic household accounting invariant fails."""

    issues = cohort_issues(cohort)
    if issues:
        raise CohortInvariantError("; ".join(issues))
