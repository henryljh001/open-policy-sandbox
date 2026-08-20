"""Tests for plugin discovery and the synthetic baseline engine."""

import copy
import json
import unittest
from pathlib import Path

from policy_sandbox.application import run_scenario
from policy_sandbox.plugins import engines as _engines  # noqa: F401
from policy_sandbox.plugins.base import SimulationEngine
from policy_sandbox.plugins.registry import available_engines, register_engine


class RegistryAndBaselineTests(unittest.TestCase):
    """Verify strict registration and deterministic execution."""

    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.scenario = json.loads(
            (root / "examples" / "minimal_scenario.json").read_text(encoding="utf-8")
        )

    def test_builtin_engine_is_auto_discovered(self) -> None:
        self.assertIn("deterministic_baseline", available_engines())

    def test_run_is_reproducible(self) -> None:
        first = run_scenario(self.scenario)
        second = run_scenario(self.scenario)
        self.assertEqual(first, second)
        self.assertEqual(first["outcomes"]["service_coverage"], 68.5)
        self.assertEqual(first["outcomes"]["fiscal_cost"], 118.0)
        self.assertTrue(first["synthetic"])

    def test_nonfinite_baseline_and_effect_values_are_rejected(self) -> None:
        invalid_baseline = copy.deepcopy(self.scenario)
        invalid_baseline["baseline"]["service_coverage"] = float("nan")
        with self.assertRaises(ValueError):
            run_scenario(invalid_baseline)

        invalid_effect = copy.deepcopy(self.scenario)
        invalid_effect["interventions"][0]["parameters"]["service_coverage"] = float(
            "inf"
        )
        with self.assertRaises(ValueError):
            run_scenario(invalid_effect)

    def test_duplicate_registration_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "already registered"):

            @register_engine("deterministic_baseline")
            class DuplicateEngine(SimulationEngine):
                def run(self, scenario):  # type: ignore[no-untyped-def]
                    raise NotImplementedError


if __name__ == "__main__":
    unittest.main()
