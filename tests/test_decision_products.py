"""Decision brief and audit bundle tests."""

import json
import unittest

from policy_sandbox.application.compare_scenarios import (
    ComparisonValidationError,
    run_catalog_comparison,
)
from policy_sandbox.application.decision_products import (
    build_audit_bundle,
    build_decision_brief,
    build_decision_package,
    render_decision_brief_markdown,
)


def comparison_plan() -> dict:
    return {
        "schema_version": "1.0.0",
        "comparison_id": "test-decision-products",
        "name": "Test decision products",
        "comparison_mode": "policy",
        "baseline_key": "baseline",
        "context": {
            "archetype": "metropolitan_adjacent",
            "start_year": 2025,
            "sample_size": 100,
            "repetitions": 3,
            "base_seed": 8128,
            "horizon_years": 3,
        },
        "scenario_specs": [
            {"key": "baseline", "scenario_code": "S0", "pressures": []},
            {"key": "option-a", "scenario_code": "S6", "pressures": []},
            {"key": "option-b", "scenario_code": "S7", "pressures": []},
        ],
        "synthetic": True,
    }


class DecisionProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.comparison = run_catalog_comparison(comparison_plan())

    def test_brief_is_deterministic_and_has_no_hidden_recommendation(self) -> None:
        first = build_decision_brief(self.comparison)
        second = build_decision_brief(self.comparison)
        self.assertEqual(first, second)
        self.assertTrue(first["not_a_recommendation"])
        self.assertEqual(first["usage_level"], "Demo")
        self.assertNotIn("overall_score", json.dumps(first, sort_keys=True))

    def test_markdown_keeps_demo_and_boundary_labels_visible(self) -> None:
        brief = build_decision_brief(self.comparison)
        markdown = render_decision_brief_markdown(brief)
        self.assertIn("Demo / synthetic assumptions only", markdown)
        self.assertIn("Not a recommendation", markdown)
        self.assertIn("Pareto front", markdown)

    def test_markdown_escapes_caller_labels_and_collapses_line_breaks(self) -> None:
        brief = build_decision_brief(self.comparison)
        brief["title"] = "Expected title\n## Forged section"
        brief["headline"] = "<script>alert(1)</script>\n- forged item"
        brief["scenario_matrix"][0]["scenario_name"] = "baseline | injected"
        markdown = render_decision_brief_markdown(brief)

        self.assertNotIn("\n## Forged section", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn("\n- forged item", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertIn("baseline \\| injected", markdown)
        self.assertEqual(markdown.count("## Scenario matrix"), 1)

    def test_audit_bundle_records_versions_digests_and_unpassed_gates(self) -> None:
        audit = build_audit_bundle(self.comparison)
        self.assertEqual(audit["component_versions"]["open_policy_sandbox"], "0.7.0")
        self.assertEqual(
            audit["component_versions"]["engine_plugin"]["name"],
            "new_urbanization_microsim",
        )
        self.assertEqual(len(audit["scenario_traces"]), 3)
        gate_results = {item["gate_id"]: item["result"] for item in audit["gates"]}
        self.assertEqual(gate_results["NO_HIDDEN_COMPOSITE_SCORE"], "pass")
        self.assertEqual(gate_results["U6_EXTERNAL_CALIBRATION"], "not_passed")
        self.assertEqual(gate_results["U8_HUMAN_SIGNOFF"], "not_passed")

    def test_decision_package_digest_is_reproducible(self) -> None:
        first = build_decision_package(self.comparison)
        second = build_decision_package(self.comparison)
        self.assertEqual(first["package_digest"], second["package_digest"])
        self.assertTrue(first["synthetic"])

    def test_non_synthetic_comparison_is_rejected(self) -> None:
        invalid = dict(self.comparison)
        invalid["synthetic"] = False
        with self.assertRaises(ComparisonValidationError) as caught:
            build_decision_brief(invalid)
        self.assertEqual(caught.exception.code, "non_synthetic_comparison")


if __name__ == "__main__":
    unittest.main()
