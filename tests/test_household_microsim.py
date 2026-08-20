"""Tests for synthetic households, allocation constraints, and pressure direction."""

import unittest

from policy_sandbox.application import run_scenario
from policy_sandbox.domains.new_urbanization.microsim.generator import (
    SyntheticHouseholdFactory,
)
from policy_sandbox.domains.new_urbanization.microsim_scenario import (
    build_microsim_scenario,
)


class HouseholdMicrosimTests(unittest.TestCase):
    """Verify household reproducibility, grouping, and capacity accounting."""

    def test_default_ten_thousand_household_cohort_is_reproducible(self) -> None:
        config = {
            "archetype": "metropolitan_adjacent",
            "target_population": 500000.0,
            "random_seed": 20260819,
            "synthetic": True,
        }
        first = SyntheticHouseholdFactory(config).create()
        second = SyntheticHouseholdFactory(config).create()
        self.assertEqual(first, second)
        self.assertEqual(first.sample_households, 10000)
        self.assertAlmostEqual(first.represented_population, 500000.0)
        identifiers = [household.household_id for household in first.households]
        self.assertTrue(all(identifier.startswith("syn-hh-") for identifier in identifiers))

    def test_different_seed_changes_cohort(self) -> None:
        config = {
            "archetype": "population_losing",
            "sample_size": 200,
            "target_population": 260000.0,
            "random_seed": 1,
            "synthetic": True,
        }
        first = SyntheticHouseholdFactory(config).create()
        config["random_seed"] = 2
        second = SyntheticHouseholdFactory(config).create()
        self.assertNotEqual(first.households, second.households)

    def test_microsim_run_is_reproducible_and_grouped(self) -> None:
        scenario = build_microsim_scenario("S6", sample_size=400)
        first = run_scenario(scenario)
        second = run_scenario(scenario)
        self.assertEqual(first, second)
        self.assertEqual(first["outcomes"]["invariant_checks_passed"], 10.0)
        self.assertIn("skill:low", first["group_outcomes"])
        self.assertIn("origin:migrant", first["group_outcomes"])
        self.assertIn("family:with_children", first["group_outcomes"])

    def test_micro_allocations_do_not_exceed_aggregate_capacity(self) -> None:
        result = run_scenario(build_microsim_scenario("S4", sample_size=500))
        outcomes = result["outcomes"]
        secure_households = (
            outcomes["micro_represented_households"]
            * outcomes["micro_housing_security_rate_pct"]
            / 100.0
        )
        self.assertLessEqual(
            outcomes["micro_represented_employed_adults"],
            outcomes["final_jobs"] + 1e-6,
        )
        self.assertLessEqual(secure_households, outcomes["final_housing_units"] + 1e-6)
        self.assertLessEqual(
            outcomes["micro_represented_education_users"],
            outcomes["final_education_capacity"] + 1e-6,
        )

    def test_integrated_policy_improves_stable_citizenization_direction(self) -> None:
        baseline = run_scenario(build_microsim_scenario("S0", sample_size=1000))
        integrated = run_scenario(build_microsim_scenario("S6", sample_size=1000))
        self.assertGreater(
            integrated["outcomes"]["micro_stable_citizenization_rate_pct"],
            baseline["outcomes"]["micro_stable_citizenization_rate_pct"],
        )

    def test_pressure_directions_are_exposed(self) -> None:
        baseline = run_scenario(build_microsim_scenario("S0", sample_size=1000))
        employment = run_scenario(
            build_microsim_scenario(
                "S0",
                pressures=("employment_downturn",),
                sample_size=1000,
            )
        )
        fiscal = run_scenario(
            build_microsim_scenario(
                "S0",
                pressures=("fiscal_tightening",),
                sample_size=1000,
            )
        )
        migration = run_scenario(
            build_microsim_scenario(
                "S0",
                pressures=("migration_surge",),
                sample_size=1000,
            )
        )
        aging = run_scenario(
            build_microsim_scenario(
                "S0",
                pressures=("population_aging",),
                sample_size=1000,
            )
        )
        self.assertLess(
            employment["outcomes"]["micro_employment_rate_pct"],
            baseline["outcomes"]["micro_employment_rate_pct"],
        )
        self.assertLess(
            fiscal["outcomes"]["final_transfer_revenue"],
            baseline["outcomes"]["final_transfer_revenue"],
        )
        self.assertGreater(
            migration["outcomes"]["final_total_population"],
            baseline["outcomes"]["final_total_population"],
        )
        self.assertGreater(
            aging["outcomes"]["micro_elderly_share_pct"],
            baseline["outcomes"]["micro_elderly_share_pct"],
        )


if __name__ == "__main__":
    unittest.main()
