"""Build runnable household-microsimulation scenarios from packaged catalogs."""

import copy
from typing import Iterable

from policy_sandbox.domains.new_urbanization.microsim.generator import (
    load_microsim_defaults,
)
from policy_sandbox.domains.new_urbanization.pressure_catalog import (
    build_pressure_package,
)
from policy_sandbox.domains.new_urbanization.scenario_catalog import (
    build_catalog_scenario,
)


def build_microsim_scenario(
    scenario_code: str = "S6",
    pressures: Iterable[str] = (),
    archetype: str = "metropolitan_adjacent",
    start_year: int = 2025,
    random_seed: int = 20260819,
    sample_size: int = 10000,
) -> dict[str, object]:
    """Build a portable I3 scenario with explicit behavior and pressure config."""

    scenario = build_catalog_scenario(
        scenario_code,
        archetype=archetype,
        start_year=start_year,
        random_seed=random_seed,
    )
    defaults = load_microsim_defaults()
    selected_pressures = tuple(pressures)
    scenario["scenario_id"] = f"{scenario['scenario_id']}-microsim"
    scenario["name"] = f"{scenario['name']}｜合成家庭微观模拟"
    scenario["version"] = "1.1.0"
    scenario["engine"] = {
        "name": "new_urbanization_microsim",
        "config": {"strict_invariants": True},
    }
    scenario["microsim_config"] = {
        "sample_size": sample_size,
        "behavior": copy.deepcopy(defaults["behavior"]),
        "synthetic": True,
    }
    scenario["pressure_package"] = build_pressure_package(selected_pressures)
    assumptions = list(scenario.get("assumptions", []))
    assumptions.extend(
        [
            "家庭记录为无个人信息的合成样本，只表达群体差异。",
            "家庭权重每年只对齐聚合人口，聚合模型仍是人口财政土地账的权威层。",
            "行为概率与压力效应均为配置中可见的合成假设。",
        ]
    )
    scenario["assumptions"] = assumptions
    return scenario
