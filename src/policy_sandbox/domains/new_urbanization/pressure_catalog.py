"""Packaged synthetic pressure catalog and portable package builder."""

import copy
import json
from importlib.resources import files
from typing import Any, Iterable

RESOURCE_PACKAGE = "policy_sandbox.domains.new_urbanization.resources"
CATALOG_FILE = "pressure_catalog.json"


def _load_catalog() -> dict[str, Any]:
    """Load and minimally validate the packaged pressure catalog."""

    resource = files(RESOURCE_PACKAGE).joinpath(CATALOG_FILE)
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        raise ValueError("pressure catalog must declare synthetic=true")
    pressures = payload.get("pressures")
    if not isinstance(pressures, dict) or len(pressures) != 5:
        raise ValueError("pressure catalog must contain exactly five pressures")
    return payload


def available_catalog_pressures() -> tuple[str, ...]:
    """Return five packaged pressure names in stable order."""

    return tuple(sorted(_load_catalog()["pressures"]))


def build_pressure_package(names: Iterable[str] = ()) -> dict[str, Any]:
    """Build a complete explicit pressure package from registered catalog names."""

    catalog = _load_catalog()
    entries: list[dict[str, Any]] = []
    selected = tuple(names)
    if len(selected) != len(set(selected)):
        raise ValueError("pressure names must be unique")
    for index, name in enumerate(selected):
        if name not in catalog["pressures"]:
            available = ", ".join(available_catalog_pressures())
            raise ValueError(f"Unknown pressure '{name}'. Available: {available}")
        entry = catalog["pressures"][name]
        entries.append(
            {
                "pressure_id": f"pressure-{index + 1}-{name}",
                "name": name,
                "config": copy.deepcopy(entry["config"]),
            }
        )
    return {
        "package_id": "new-urbanization-pressure-package",
        "pressures": entries,
        "synthetic": True,
    }
