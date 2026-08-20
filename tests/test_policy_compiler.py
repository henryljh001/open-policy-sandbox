"""Tests for policy-package compilation, warnings, and hard conflicts."""

import copy
import unittest

from policy_sandbox.domains.new_urbanization.compiler import (
    PolicyCompilationError,
    compile_policy_package,
)
from policy_sandbox.domains.new_urbanization.scenario_catalog import (
    build_catalog_scenario,
)
from policy_sandbox.domains.new_urbanization.state import BaselineRates


class PolicyCompilerTests(unittest.TestCase):
    """Verify explicit assumptions, bounded rates, and combination warnings."""

    def _compile(self, code: str):  # type: ignore[no-untyped-def]
        scenario = build_catalog_scenario(code)
        baseline = BaselineRates.from_mapping(scenario["baseline_rates"])
        return compile_policy_package(scenario["policy_package"], baseline)

    def test_settlement_only_emits_capacity_warning(self) -> None:
        compiled = self._compile("S1")
        codes = {warning["code"] for warning in compiled.warnings}
        self.assertIn("SETTLEMENT_WITHOUT_CAPACITY_SUPPORT", codes)

    def test_integrated_citizenization_resolves_settlement_warning(self) -> None:
        compiled = self._compile("S6")
        codes = {warning["code"] for warning in compiled.warnings}
        self.assertNotIn("SETTLEMENT_WITHOUT_CAPACITY_SUPPORT", codes)

    def test_high_investment_without_jobs_emits_warning(self) -> None:
        compiled = self._compile("S7")
        codes = {warning["code"] for warning in compiled.warnings}
        self.assertIn("CAPACITY_WITHOUT_EMPLOYMENT_LINKAGE", codes)

    def test_duplicate_lever_is_a_hard_conflict(self) -> None:
        scenario = build_catalog_scenario("S6")
        package = copy.deepcopy(scenario["policy_package"])
        duplicate = copy.deepcopy(package["interventions"][0])
        duplicate["intervention_id"] = "duplicate-id"
        package["interventions"].append(duplicate)
        baseline = BaselineRates.from_mapping(scenario["baseline_rates"])
        with self.assertRaisesRegex(PolicyCompilationError, "duplicate intervention name"):
            compile_policy_package(package, baseline)

    def test_out_of_bound_combination_is_rejected(self) -> None:
        scenario = build_catalog_scenario("S1")
        package = copy.deepcopy(scenario["policy_package"])
        package["interventions"][0]["config"]["rate_deltas"][
            "hukou_conversion_rate"
        ] = 2.0
        baseline = BaselineRates.from_mapping(scenario["baseline_rates"])
        with self.assertRaisesRegex(PolicyCompilationError, "hukou_conversion_rate"):
            compile_policy_package(package, baseline)


if __name__ == "__main__":
    unittest.main()

