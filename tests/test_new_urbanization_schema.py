"""Validate the public new-urbanization example against its JSON Schema."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


class NewUrbanizationSchemaTests(unittest.TestCase):
    """Keep the synthetic domain scenario and schema mutually consistent."""

    def test_baseline_scenario_matches_schema(self) -> None:
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (
                root
                / "schemas"
                / "domains"
                / "new_urbanization_scenario.schema.json"
            ).read_text(encoding="utf-8")
        )
        scenario = json.loads(
            (
                root
                / "examples"
                / "new_urbanization"
                / "baseline_scenario.json"
            ).read_text(encoding="utf-8")
        )
        errors = sorted(Draft202012Validator(schema).iter_errors(scenario), key=str)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()

