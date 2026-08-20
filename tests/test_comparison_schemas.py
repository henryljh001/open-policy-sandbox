"""Generated I4 artifact schema tests."""

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from policy_sandbox.application.compare_scenarios import run_catalog_comparison
from policy_sandbox.application.decision_products import (
    build_audit_bundle,
    build_decision_brief,
)


class ComparisonSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.plan = json.loads(
            (
                cls.root
                / "examples"
                / "new_urbanization"
                / "comparison_plan.json"
            ).read_text(encoding="utf-8")
        )
        cls.plan["context"]["sample_size"] = 100
        cls.plan["context"]["repetitions"] = 2
        cls.comparison = run_catalog_comparison(cls.plan)

    def validate(self, schema_path: Path, instance: dict) -> None:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(instance)

    def test_static_plan_validates(self) -> None:
        self.validate(
            self.root
            / "schemas"
            / "domains"
            / "new_urbanization_comparison_plan.schema.json",
            self.plan,
        )

    def test_generated_comparison_validates(self) -> None:
        self.validate(
            self.root / "schemas" / "comparison_run.schema.json",
            self.comparison,
        )

    def test_generated_decision_brief_validates(self) -> None:
        self.validate(
            self.root / "schemas" / "decision_brief.schema.json",
            build_decision_brief(self.comparison),
        )

    def test_generated_audit_bundle_validates(self) -> None:
        self.validate(
            self.root / "schemas" / "audit_bundle.schema.json",
            build_audit_bundle(self.comparison),
        )


if __name__ == "__main__":
    unittest.main()
