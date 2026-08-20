"""Synthetic aggregate calibration pipeline and schema tests."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from policy_sandbox.application.run_calibration import run_calibration
from policy_sandbox.domains.new_urbanization.microsim_scenario import (
    build_microsim_scenario,
)


class CalibrationPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.dataset = json.loads(
            (
                cls.root
                / "examples"
                / "new_urbanization"
                / "synthetic_aggregate_calibration.json"
            ).read_text(encoding="utf-8")
        )
        cls.scenario = build_microsim_scenario(
            "S0",
            archetype="metropolitan_adjacent",
            sample_size=100,
            random_seed=20260819,
        )

    def run_fixture(self, dataset=None):  # type: ignore[no-untyped-def]
        return run_calibration(
            self.scenario,
            dataset or self.dataset,
            adapter_name="new_urbanization_synthetic_aggregate_v1",
            adapter_config={"expected_reference_year": 2030},
            repetitions=3,
            base_seed=20260819,
        )

    def validate(self, name: str, instance: dict) -> None:
        schema = json.loads((self.root / "schemas" / name).read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(instance)

    def test_static_aggregate_fixture_matches_schema(self) -> None:
        self.validate("aggregate_calibration_dataset.schema.json", self.dataset)

    def test_calibration_run_is_reproducible_and_matches_schema(self) -> None:
        first = self.run_fixture()
        second = self.run_fixture()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "synthetic_fixture_passed")
        self.assertEqual(first["assessment"]["passed"], 8)
        self.validate("calibration_run.schema.json", first)

    def test_synthetic_pass_never_promotes_u6(self) -> None:
        result = self.run_fixture()
        self.assertEqual(result["U6_status"], "not_passed")
        self.assertEqual(result["usage_level"], "Demo")
        warning_codes = {item["code"] for item in result["warnings"]}
        self.assertIn("SYNTHETIC_CALIBRATION_FIXTURE", warning_codes)
        self.assertIn("U6_NOT_PASSED", warning_codes)

    def test_failed_fixture_is_explicit_and_still_reproducible(self) -> None:
        shifted = copy.deepcopy(self.dataset)
        shifted["records"][0]["value"] = 900000.0
        result = self.run_fixture(shifted)
        self.assertEqual(result["status"], "synthetic_fixture_failed")
        self.assertFalse(result["assessment"]["all_passed"])
        self.assertEqual(result["U6_status"], "not_passed")


if __name__ == "__main__":
    unittest.main()
