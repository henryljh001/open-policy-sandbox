"""Direction and reproducibility tests for the packaged S0-S8 catalog."""

import unittest

from policy_sandbox.application import run_scenario
from policy_sandbox.domains.new_urbanization.scenario_catalog import (
    available_scenarios,
    build_catalog_scenario,
)


class PolicyScenarioTests(unittest.TestCase):
    """Verify nine scenarios and intended synthetic direction checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.results = {
            code: run_scenario(build_catalog_scenario(code))
            for code in available_scenarios()
        }

    def test_catalog_contains_and_runs_s0_through_s8(self) -> None:
        self.assertEqual(available_scenarios(), tuple(f"S{i}" for i in range(9)))
        self.assertEqual(set(self.results), {f"S{i}" for i in range(9)})
        for result in self.results.values():
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["outcomes"]["invariant_checks_passed"], 5.0)

    def test_catalog_run_is_reproducible(self) -> None:
        scenario = build_catalog_scenario("S6")
        self.assertEqual(run_scenario(scenario), run_scenario(scenario))

    def test_settlement_reduces_hukou_gap(self) -> None:
        self.assertLess(
            self.results["S1"]["outcomes"]["final_urban_hukou_gap"],
            self.results["S0"]["outcomes"]["final_urban_hukou_gap"],
        )

    def test_service_follows_people_increases_effective_capacity(self) -> None:
        self.assertGreater(
            self.results["S2"]["outcomes"]["final_education_capacity_per_1000"],
            self.results["S0"]["outcomes"]["final_education_capacity_per_1000"],
        )
        self.assertGreater(
            self.results["S2"]["outcomes"]["assumption_service_eligibility_gain_pp"],
            0.0,
        )

    def test_employment_support_increases_employment_rate(self) -> None:
        self.assertGreater(
            self.results["S3"]["outcomes"]["final_employment_rate"],
            self.results["S0"]["outcomes"]["final_employment_rate"],
        )

    def test_county_expansion_increases_housing_stock(self) -> None:
        self.assertGreater(
            self.results["S4"]["outcomes"]["final_housing_units"],
            self.results["S0"]["outcomes"]["final_housing_units"],
        )

    def test_stock_quality_accelerates_reuse(self) -> None:
        self.assertLess(
            self.results["S5"]["outcomes"]["final_reusable_stock_land"],
            self.results["S0"]["outcomes"]["final_reusable_stock_land"],
        )

    def test_integrated_scenario_improves_two_target_directions(self) -> None:
        self.assertLess(
            self.results["S6"]["outcomes"]["final_urban_hukou_gap"],
            self.results["S0"]["outcomes"]["final_urban_hukou_gap"],
        )
        self.assertGreater(
            self.results["S6"]["outcomes"]["final_employment_rate"],
            self.results["S0"]["outcomes"]["final_employment_rate"],
        )

    def test_high_investment_scenario_exposes_linkage_warning(self) -> None:
        codes = {warning["code"] for warning in self.results["S7"]["warnings"]}
        self.assertIn("CAPACITY_WITHOUT_EMPLOYMENT_LINKAGE", codes)

    def test_shrinking_adaptation_reduces_greenfield_and_raises_transfer(self) -> None:
        self.assertLess(
            self.results["S8"]["outcomes"]["final_used_construction_land"],
            self.results["S0"]["outcomes"]["final_used_construction_land"],
        )
        self.assertGreater(
            self.results["S8"]["outcomes"]["final_transfer_revenue"],
            self.results["S0"]["outcomes"]["final_transfer_revenue"],
        )


if __name__ == "__main__":
    unittest.main()

