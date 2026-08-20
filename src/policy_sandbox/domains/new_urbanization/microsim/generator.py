"""Generate reproducible synthetic household cohorts from packaged profiles."""

import json
import math
import random
from importlib.resources import files
from typing import Any, Mapping

from policy_sandbox.domains.new_urbanization.microsim.state import (
    Household,
    HouseholdCohort,
    assert_cohort,
)

RESOURCE_PACKAGE = "policy_sandbox.domains.new_urbanization.resources"
DEFAULTS_FILE = "microsim_defaults.json"


def load_microsim_defaults() -> dict[str, Any]:
    """Load a fresh copy of packaged, inspectable synthetic defaults."""

    resource = files(RESOURCE_PACKAGE).joinpath(DEFAULTS_FILE)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        raise ValueError("microsim defaults must declare synthetic=true")
    return payload


def _weighted_choice(rng: random.Random, probabilities: Mapping[str, Any]) -> str:
    """Choose a key from non-negative, finite configured weights."""

    names: list[str] = []
    weights: list[float] = []
    for name, raw in probabilities.items():
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise TypeError(f"probability for {name} must be numeric")
        weight = float(raw)
        if not math.isfinite(weight) or weight < 0:
            raise ValueError(f"probability for {name} must be finite and non-negative")
        names.append(name)
        weights.append(weight)
    if not names or sum(weights) <= 0:
        raise ValueError("probability mapping must have positive total weight")
    return rng.choices(names, weights=weights, k=1)[0]


class SyntheticHouseholdFactory:
    """Create a no-PII household sample from explicit synthetic configuration."""

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.cfg = dict(cfg)

    def create(self) -> HouseholdCohort:
        """Generate and validate a weighted synthetic household cohort."""

        if self.cfg.get("synthetic") is not True:
            raise ValueError("household cohort config must set synthetic=true")
        defaults = load_microsim_defaults()
        archetype = self.cfg.get("archetype")
        if archetype not in defaults["profiles"]:
            available = ", ".join(sorted(defaults["profiles"]))
            raise ValueError(f"Unknown household archetype '{archetype}'. Available: {available}")
        sample_size = self.cfg.get("sample_size", defaults["cohort"]["sample_size"])
        if isinstance(sample_size, bool) or not isinstance(sample_size, int):
            raise TypeError("sample_size must be an integer")
        if not 100 <= sample_size <= 100000:
            raise ValueError("sample_size must be between 100 and 100000")
        random_seed = self.cfg.get("random_seed")
        if isinstance(random_seed, bool) or not isinstance(random_seed, int):
            raise TypeError("random_seed must be an integer")
        if random_seed < 0:
            raise ValueError("random_seed must be non-negative")
        target_population = self.cfg.get("target_population")
        if (
            isinstance(target_population, bool)
            or not isinstance(target_population, (int, float))
            or not math.isfinite(float(target_population))
            or float(target_population) <= 0
        ):
            raise ValueError("target_population must be finite and positive")

        rng = random.Random(random_seed)
        common = defaults["cohort"]
        profile = defaults["profiles"][archetype]
        behavior = defaults["behavior"]
        households = tuple(
            self._create_household(index, rng, common, profile, behavior)
            for index in range(sample_size)
        )
        sample_population = sum(household.size for household in households)
        cohort = HouseholdCohort(
            households=households,
            household_weight=float(target_population) / sample_population,
            random_seed=random_seed,
        )
        assert_cohort(cohort)
        return cohort

    @staticmethod
    def _create_household(
        index: int,
        rng: random.Random,
        common: Mapping[str, Any],
        profile: Mapping[str, Any],
        behavior: Mapping[str, Any],
    ) -> Household:
        """Create one internally consistent synthetic household."""

        composition_name = _weighted_choice(
            rng,
            {
                name: value["probability"]
                for name, value in common["composition"].items()
            },
        )
        composition = common["composition"][composition_name]
        working_age = int(composition["working_age_adults"])
        children = int(composition["children"])
        elderly = int(composition["elderly"])
        size = working_age + children + elderly
        skill = _weighted_choice(rng, profile["skill_probabilities"])
        origin = _weighted_choice(rng, profile["origin_probabilities"])
        zone = _weighted_choice(rng, profile["zone_probabilities"])
        tenure = _weighted_choice(rng, common["tenure_probabilities"])
        employment_probability = float(behavior[f"{skill}_skill_employment_probability"])
        employed = sum(
            1 for _ in range(working_age) if rng.random() < employment_probability
        )
        income_base = float(common["income_by_skill"][skill])
        income_noise = rng.gauss(0.0, float(common["income_noise_share"]))
        income = max(0.0, income_base * (1.0 + income_noise))
        burden_base = float(common["housing_burden_by_tenure"][tenure])
        burden = min(max(burden_base + rng.uniform(-0.04, 0.04), 0.0), 1.0)
        stable_resident = zone != "neighboring_city"
        settled = origin == "local_urban" and stable_resident
        if origin != "local_urban" and stable_resident:
            settled = rng.random() < 0.10
        eligible_probability = float(behavior["service_eligibility_probability"])
        service_eligible = origin == "local_urban" or settled
        if not service_eligible:
            service_eligible = rng.random() < eligible_probability
        housing_secure_probability = 0.95 if tenure != "renter" else 0.70
        housing_secure = stable_resident and rng.random() < housing_secure_probability
        access_probability = float(behavior["service_access_probability"])
        education_access = service_eligible and rng.random() < access_probability
        health_access = service_eligible and rng.random() < access_probability
        return Household(
            household_id=f"syn-hh-{index + 1:07d}",
            size=size,
            working_age_adults=working_age,
            children=children,
            elderly=elderly,
            skill_level=skill,
            origin_status=origin,
            zone=zone,
            employed_adults=employed,
            income_per_capita=income,
            housing_tenure=tenure,
            housing_secure=housing_secure,
            housing_burden_ratio=burden,
            service_eligible=service_eligible,
            education_access=education_access,
            health_access=health_access,
            settled=settled,
            stable_resident=stable_resident,
        )
