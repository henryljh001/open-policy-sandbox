"""Validate I3 static, generated, run, and repeated-experiment contracts."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from policy_sandbox.application import run_experiment, run_scenario
from policy_sandbox.domains.new_urbanization.microsim_scenario import (
    build_microsim_scenario,
)


class MicrosimSchemaTests(unittest.TestCase):
    """Keep the I3 scenario and experiment schemas executable."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        scenario_schema = json.loads(
            (
                cls.root
                / "schemas"
                / "domains"
                / "new_urbanization_microsim_scenario.schema.json"
            ).read_text(encoding="utf-8")
        )
        experiment_schema = json.loads(
            (cls.root / "schemas" / "experiment_run.schema.json").read_text(
                encoding="utf-8"
            )
        )
        cls.scenario_validator = Draft202012Validator(scenario_schema)
        cls.experiment_validator = Draft202012Validator(experiment_schema)

    def test_static_microsim_example_matches_schema(self) -> None:
        example = json.loads(
            (
                self.root
                / "examples"
                / "new_urbanization"
                / "microsim_pressure_scenario.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(list(self.scenario_validator.iter_errors(example)), [])
        self.assertEqual(run_scenario(example)["status"], "succeeded")

    def test_generated_microsim_scenario_matches_schema(self) -> None:
        scenario = build_microsim_scenario(
            "S8",
            pressures=("fiscal_tightening",),
            sample_size=200,
        )
        self.assertEqual(list(self.scenario_validator.iter_errors(scenario)), [])

    def test_experiment_result_matches_schema(self) -> None:
        scenario = build_microsim_scenario("S0", sample_size=200)
        result = run_experiment(scenario, repetitions=3)
        self.assertEqual(list(self.experiment_validator.iter_errors(result)), [])


if __name__ == "__main__":
    unittest.main()
