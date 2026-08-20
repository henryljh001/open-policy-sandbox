"""Validate policy scenario examples and the generated catalog."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from policy_sandbox.domains.new_urbanization.scenario_catalog import (
    available_scenarios,
    build_catalog_scenario,
)


class PolicyScenarioSchemaTests(unittest.TestCase):
    """Keep static and generated policy scenarios aligned with the schema."""

    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.schema = json.loads(
            (
                root
                / "schemas"
                / "domains"
                / "new_urbanization_policy_scenario.schema.json"
            ).read_text(encoding="utf-8")
        )
        cls.validator = Draft202012Validator(cls.schema)
        cls.example = json.loads(
            (
                root
                / "examples"
                / "new_urbanization"
                / "policy_package_scenario.json"
            ).read_text(encoding="utf-8")
        )

    def test_static_example_matches_schema(self) -> None:
        self.assertEqual(list(self.validator.iter_errors(self.example)), [])

    def test_all_catalog_scenarios_match_schema(self) -> None:
        for code in available_scenarios():
            errors = list(self.validator.iter_errors(build_catalog_scenario(code)))
            self.assertEqual(errors, [], code)


if __name__ == "__main__":
    unittest.main()
