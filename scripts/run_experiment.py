"""Run a packaged synthetic microsimulation experiment from the command line."""

import argparse
import json

from policy_sandbox.application import run_experiment
from policy_sandbox.domains.new_urbanization.microsim_scenario import (
    build_microsim_scenario,
)


def main() -> None:
    """Parse arguments, run repeated simulations, and print JSON."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="S6")
    parser.add_argument("--archetype", default="metropolitan_adjacent")
    parser.add_argument("--pressure", action="append", default=[])
    parser.add_argument("--sample-size", type=int, default=10000)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260819)
    args = parser.parse_args()
    scenario = build_microsim_scenario(
        args.scenario,
        pressures=args.pressure,
        archetype=args.archetype,
        random_seed=args.seed,
        sample_size=args.sample_size,
    )
    result = run_experiment(
        scenario,
        repetitions=args.repetitions,
        base_seed=args.seed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
