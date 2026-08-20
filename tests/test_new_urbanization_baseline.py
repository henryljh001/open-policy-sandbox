"""Tests for synthetic county generation, accounting, and engine execution."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from policy_sandbox.application import run_scenario
from policy_sandbox.domains.new_urbanization import (
    BaselineRates,
    SyntheticCountyFactory,
    advance_one_year,
    state_issues,
    transition_issues,
)
from policy_sandbox.plugins.registry import available_engines


class NewUrbanizationBaselineTests(unittest.TestCase):
    """Verify portable resources, conservation, and reproducibility."""

    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.scenario = json.loads(
            (root / "examples" / "new_urbanization" / "baseline_scenario.json").read_text(
                encoding="utf-8"
            )
        )

    def test_all_five_archetypes_are_valid(self) -> None:
        expected = {
            "metropolitan_adjacent",
            "specialized_function",
            "agricultural_main_production",
            "key_ecological_function",
            "population_losing",
        }
        self.assertEqual(set(SyntheticCountyFactory.available_archetypes()), expected)
        for name in expected:
            state = SyntheticCountyFactory({"archetype": name, "start_year": 2025}).create()
            self.assertEqual(state_issues(state), ())

    def test_population_and_land_reconcile_after_one_year(self) -> None:
        state = SyntheticCountyFactory(
            {"archetype": "metropolitan_adjacent", "start_year": 2025}
        ).create()
        rates = BaselineRates.from_mapping(self.scenario["baseline_rates"])
        current, flow = advance_one_year(state, rates)
        self.assertEqual(transition_issues(state, current, flow), ())
        expected_population = (
            state.total_population + flow.births - flow.deaths + flow.net_migration
        )
        self.assertAlmostEqual(current.total_population, expected_population)
        self.assertAlmostEqual(
            state.used_construction_land
            + state.developable_land
            + state.ecological_protected_land,
            current.used_construction_land
            + current.developable_land
            + current.ecological_protected_land,
        )

    def test_population_losing_baseline_declines(self) -> None:
        state = SyntheticCountyFactory(
            {"archetype": "population_losing", "start_year": 2025}
        ).create()
        rates = BaselineRates.from_mapping(
            {"birth_rate": 0.005, "death_rate": 0.01, "net_migration_rate": -0.015}
        )
        current, _ = advance_one_year(state, rates)
        self.assertLess(current.total_population, state.total_population)

    def test_packaged_resource_is_independent_of_working_directory(self) -> None:
        original = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                state = SyntheticCountyFactory(
                    {"archetype": "specialized_function", "start_year": 2030}
                ).create()
            finally:
                os.chdir(original)
        self.assertEqual(state.year, 2030)

    def test_engine_is_discovered_and_reproducible(self) -> None:
        self.assertIn("new_urbanization_baseline", available_engines())
        first = run_scenario(self.scenario)
        second = run_scenario(self.scenario)
        self.assertEqual(first, second)
        self.assertEqual(first["outcomes"]["years_simulated"], 5.0)
        self.assertEqual(first["outcomes"]["invariant_checks_passed"], 5.0)
        self.assertTrue(first["synthetic"])

    def test_engine_rejects_non_synthetic_scenario(self) -> None:
        invalid = dict(self.scenario)
        invalid["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "only synthetic=true"):
            run_scenario(invalid)


if __name__ == "__main__":
    unittest.main()
