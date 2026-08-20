"""Portable S0-S8 synthetic scenario catalog and builder."""

import copy
import json
from importlib.resources import files
from typing import Any

RESOURCE_PACKAGE = "policy_sandbox.domains.new_urbanization.resources"
CATALOG_FILE = "scenario_catalog.json"


def _load_catalog() -> dict[str, Any]:
    """Load and minimally validate the packaged scenario catalog."""

    resource = files(RESOURCE_PACKAGE).joinpath(CATALOG_FILE)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        raise ValueError("scenario catalog must declare synthetic=true")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, dict) or set(scenarios) != {f"S{i}" for i in range(9)}:
        raise ValueError("scenario catalog must contain exactly S0 through S8")
    return payload


def available_scenarios() -> tuple[str, ...]:
    """Return S0-S8 in stable order."""

    return tuple(sorted(_load_catalog()["scenarios"], key=lambda code: int(code[1:])))


def build_catalog_scenario(
    scenario_code: str,
    archetype: str = "metropolitan_adjacent",
    start_year: int = 2025,
    random_seed: int = 20260819,
) -> dict[str, Any]:
    """Build a complete runnable scenario from a packaged S0-S8 entry."""

    catalog = _load_catalog()
    if scenario_code not in catalog["scenarios"]:
        available = ", ".join(available_scenarios())
        raise ValueError(f"Unknown scenario code '{scenario_code}'. Available: {available}")
    entry = copy.deepcopy(catalog["scenarios"][scenario_code])
    return {
        "schema_version": "1.0.0",
        "scenario_id": f"synthetic-{archetype}-{scenario_code.lower()}",
        "name": entry["title"],
        "version": "1.0.0",
        "description": entry["description"],
        "domain_config": {
            "schema_version": "1.0.0",
            "domain": "new_urbanization",
            "focus_module": "citizenization",
            "spatial_scale": "county",
            "time_step": "annual",
            "horizon_years": 5,
            "county_type": archetype,
            "enabled_modules": [
                "population",
                "labor",
                "housing",
                "public_service",
                "fiscal",
                "land",
            ],
            "random_seed": random_seed,
            "synthetic": True,
        },
        "scenario_code": scenario_code,
        "archetype": archetype,
        "start_year": start_year,
        "population_scale": 1.0,
        "baseline_rates": copy.deepcopy(catalog["baseline_rates"]),
        "policy_package": {
            "package_id": f"new-urbanization-{scenario_code.lower()}",
            "interventions": entry["interventions"],
            "synthetic": True,
        },
        "engine": {
            "name": "new_urbanization_policy_rules",
            "config": {"strict_invariants": True},
        },
        "assumptions": list(catalog["assumptions"]),
        "random_seed": random_seed,
        "synthetic": True,
    }

