"""Fair multi-scenario comparison tests."""

import copy
import json
import unittest

from policy_sandbox.application.compare_scenarios import (
    ComparisonValidationError,
    run_catalog_comparison,
)


def comparison_plan() -> dict:
    return {
        "schema_version": "1.0.0",
        "comparison_id": "test-policy-comparison",
        "name": "Test policy comparison",
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


class ScenarioComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = comparison_plan()
        cls.result = run_catalog_comparison(cls.plan)

    def test_comparison_is_reproducible_and_uses_common_random_numbers(self) -> None:
        second = run_catalog_comparison(self.plan)
        self.assertEqual(self.result, second)
        self.assertTrue(self.result["reproducible"])
        self.assertEqual(self.result["base_seed"], 8128)
        self.assertEqual(self.result["repetitions"], 3)

    def test_baseline_deltas_are_zero(self) -> None:
        baseline = self.result["baseline_scenario_id"]
        for metric in self.result["metric_comparison"].values():
            self.assertAlmostEqual(metric["scenarios"][baseline]["delta_from_baseline"], 0.0)

    def test_output_has_unweighted_pareto_front_without_overall_score(self) -> None:
        front = set(self.result["non_dominated_scenario_ids"])
        self.assertTrue(front)
        self.assertTrue(front.issubset(set(self.result["scenario_order"])))
        serialized = json.dumps(self.result, sort_keys=True)
        self.assertNotIn("overall_score", serialized)
        warning_codes = {item["code"] for item in self.result["warnings"]}
        self.assertIn("NO_COMPOSITE_SCORE", warning_codes)

    def test_group_disparities_and_resource_ledgers_cover_every_scenario(self) -> None:
        expected = set(self.result["scenario_order"])
        self.assertEqual(set(self.result["group_disparities"]), expected)
        self.assertEqual(set(self.result["resource_risk_ledger"]), expected)
        for scenario_id in expected:
            self.assertIn("zone", self.result["group_disparities"][scenario_id])
            self.assertIn("risk_flags", self.result["resource_risk_ledger"][scenario_id])

    def test_policy_mode_rejects_different_pressure_packages(self) -> None:
        plan = comparison_plan()
        plan["scenario_specs"][1]["pressures"] = ["migration_surge"]
        with self.assertRaises(ComparisonValidationError) as caught:
            run_catalog_comparison(plan)
        self.assertEqual(caught.exception.code, "comparison_context_mismatch")
        self.assertIn("error", caught.exception.to_mapping())

    def test_stress_mode_allows_pressure_changes_for_same_policy(self) -> None:
        plan = comparison_plan()
        plan["comparison_id"] = "test-stress-comparison"
        plan["comparison_mode"] = "stress"
        plan["scenario_specs"] = [
            {"key": "baseline", "scenario_code": "S6", "pressures": []},
            {
                "key": "downturn",
                "scenario_code": "S6",
                "pressures": ["employment_downturn"],
            },
        ]
        result = run_catalog_comparison(plan)
        self.assertEqual(result["comparison_mode"], "stress")
        self.assertEqual(len(result["scenario_order"]), 2)

    def test_explicit_threshold_override_is_visible(self) -> None:
        plan = copy.deepcopy(self.plan)
        plan["comparison_id"] = "test-risk-threshold"
        plan["risk_thresholds"] = {"max_fiscal_expenditure_ratio_pct": 1.0}
        result = run_catalog_comparison(plan)
        self.assertEqual(result["risk_thresholds"]["max_fiscal_expenditure_ratio_pct"], 1.0)
        self.assertTrue(
            all(
                item["risk_flag_count"] >= 1
                for item in result["resource_risk_ledger"].values()
            )
        )

    def test_multiplicative_workload_is_rejected_before_execution(self) -> None:
        plan = comparison_plan()
        plan["context"].update(
            {"sample_size": 100_000, "repetitions": 1_000, "horizon_years": 15}
        )
        with self.assertRaises(ComparisonValidationError) as caught:
            run_catalog_comparison(plan)
        self.assertEqual(caught.exception.code, "work_budget_exceeded")
        details = {item["field"]: item["code"] for item in caught.exception.details}
        self.assertGreater(int(details["estimated_work_units"]), int(details["max_work_units"]))


if __name__ == "__main__":
    unittest.main()
