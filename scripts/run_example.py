"""Run a bundled synthetic scenario and print its result as JSON."""

import argparse
import json
from pathlib import Path

from policy_sandbox.application import run_scenario


def _reject_nonfinite_constant(value: str) -> None:
    """Reject NaN and Infinity tokens, which are not valid JSON numbers."""

    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def main() -> None:
    """Load and run a selected synthetic scenario."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        nargs="?",
        help="Scenario JSON path; defaults to examples/minimal_scenario.json",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    scenario_path = (
        Path(args.scenario)
        if args.scenario
        else root / "examples" / "minimal_scenario.json"
    )
    scenario = json.loads(
        scenario_path.read_text(encoding="utf-8"),
        parse_constant=_reject_nonfinite_constant,
    )
    print(
        json.dumps(
            run_scenario(scenario), ensure_ascii=False, indent=2, allow_nan=False
        )
    )


if __name__ == "__main__":
    main()

