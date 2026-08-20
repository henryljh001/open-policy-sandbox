"""Portable synthetic county factory backed by package resources."""

import json
from importlib.resources import files
from typing import Any, Mapping

from policy_sandbox.domains.new_urbanization.invariants import assert_state
from policy_sandbox.domains.new_urbanization.state import CountyState

RESOURCE_PACKAGE = "policy_sandbox.domains.new_urbanization.resources"
ARCHETYPE_FILE = "county_archetypes.json"


def _load_archetypes() -> dict[str, Any]:
    """Load synthetic archetypes without depending on the process CWD."""

    resource = files(RESOURCE_PACKAGE).joinpath(ARCHETYPE_FILE)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        raise ValueError("Archetype resource must declare synthetic=true")
    archetypes = payload.get("archetypes")
    if not isinstance(archetypes, dict) or not archetypes:
        raise ValueError("Archetype resource must contain a non-empty archetypes object")
    return archetypes


class SyntheticCountyFactory:
    """Create one aggregate county state from a config mapping."""

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.cfg = dict(cfg)

    @staticmethod
    def available_archetypes() -> tuple[str, ...]:
        """Return bundled synthetic archetype names in stable order."""

        return tuple(sorted(_load_archetypes()))

    def create(self) -> CountyState:
        """Create and validate a synthetic county state."""

        archetype_name = self.cfg.get("archetype")
        archetypes = _load_archetypes()
        if archetype_name not in archetypes:
            available = ", ".join(sorted(archetypes))
            raise ValueError(f"Unknown county archetype '{archetype_name}'. Available: {available}")

        start_year = self.cfg.get("start_year", 2025)
        if isinstance(start_year, bool) or not isinstance(start_year, int):
            raise TypeError("start_year must be an integer")
        scale = self.cfg.get("population_scale", 1.0)
        if isinstance(scale, bool) or not isinstance(scale, (int, float)) or scale <= 0:
            raise ValueError("population_scale must be a positive number")

        record = dict(archetypes[archetype_name]["initial_state"])
        record["year"] = start_year
        record["county_type"] = archetype_name
        scale_fields = {
            "total_population",
            "urban_residents",
            "urban_hukou_residents",
            "working_age_population",
            "employed_population",
            "jobs",
            "housing_units",
            "occupied_housing_units",
            "affordable_housing_units",
            "education_capacity",
            "health_capacity",
            "fiscal_revenue",
            "transfer_revenue",
            "operating_expenditure",
            "capital_expenditure",
            "debt",
        }
        for name in scale_fields:
            record[name] = float(record[name]) * float(scale)

        state = CountyState.from_mapping(record)
        assert_state(state)
        return state

