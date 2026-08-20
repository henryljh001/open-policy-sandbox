"""Run the packaged S0-S8 synthetic policy scenario catalog."""

import argparse
import json

from policy_sandbox.application import run_scenario
from policy_sandbox.domains.new_urbanization.scenario_catalog import (
    available_scenarios,
    build_catalog_scenario,
)


def main() -> None:
    """Run nine scenarios for one synthetic county archetype."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archetype", default="metropolitan_adjacent")
    args = parser.parse_args()

    rows = []
    for code in available_scenarios():
        result = run_scenario(build_catalog_scenario(code, archetype=args.archetype))
        outcomes = result["outcomes"]
        rows.append(
            {
                "scenario_code": code,
                "run_id": result["run_id"],
                "urban_hukou_gap": outcomes["final_urban_hukou_gap"],
                "employment_rate": outcomes["final_employment_rate"],
                "housing_units": outcomes["final_housing_units"],
                "debt": outcomes["final_debt"],
                "used_construction_land": outcomes["final_used_construction_land"],
                "warnings": [item["code"] for item in result["warnings"]],
                "synthetic": result["synthetic"],
            }
        )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

