"""Run the synthetic aggregate calibration integration fixture."""

import argparse
import json
from pathlib import Path

from policy_sandbox.application.run_calibration import run_calibration
from policy_sandbox.domains.new_urbanization.microsim_scenario import (
    build_microsim_scenario,
)


def main() -> None:
    """Load one aggregate dataset, run S0-S8, and print a calibration record."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--scenario", default="S0")
    parser.add_argument("--archetype", default="metropolitan_adjacent")
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260819)
    parser.add_argument("--reference-year", type=int, default=2030)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    dataset = json.loads(args.data.read_text(encoding="utf-8"))
    scenario = build_microsim_scenario(
        args.scenario,
        archetype=args.archetype,
        sample_size=args.sample_size,
        random_seed=args.seed,
    )
    result = run_calibration(
        scenario,
        dataset,
        adapter_name="new_urbanization_synthetic_aggregate_v1",
        adapter_config={"expected_reference_year": args.reference_year},
        repetitions=args.repetitions,
        base_seed=args.seed,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8")
    print(
        json.dumps(
            {
                "calibration_id": result["calibration_id"],
                "output": str(args.output.resolve()),
                "status": result["status"],
                "U6_status": result["U6_status"],
                "synthetic": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
