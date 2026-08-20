"""Tests for strict pressure registration, catalogs, and compilation."""

import unittest

from policy_sandbox.domain.models import PressureDescriptor, PressureEffect
from policy_sandbox.domains.new_urbanization.pressure_catalog import (
    available_catalog_pressures,
    build_pressure_package,
)
from policy_sandbox.domains.new_urbanization.pressure_compiler import (
    PressureCompilationError,
    compile_pressure_package,
)
from policy_sandbox.domains.new_urbanization.state import BaselineRates
from policy_sandbox.plugins.base import PressureScenario
from policy_sandbox.plugins.registry import (
    PressureScenarioFactory,
    available_pressures,
    register_pressure,
)


class PressureRegistryTests(unittest.TestCase):
    """Verify discovery and strict failure behavior for five pressures."""

    def test_five_pressures_are_auto_discovered(self) -> None:
        expected = {
            "employment_downturn",
            "fiscal_tightening",
            "migration_surge",
            "population_aging",
            "extreme_disruption",
        }
        self.assertEqual(set(available_pressures()), expected)
        self.assertEqual(set(available_catalog_pressures()), expected)

    def test_unknown_pressure_fails_with_available_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown pressure scenario"):
            PressureScenarioFactory("not_registered", {})

    def test_duplicate_registration_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "already registered"):

            @register_pressure("employment_downturn")
            class DuplicatePressure(PressureScenario):
                descriptor = PressureDescriptor(
                    name="employment_downturn",
                    version="test",
                    domain="new_urbanization",
                    title="duplicate",
                )

                def compile(self) -> PressureEffect:
                    return PressureEffect()

    def test_duplicate_package_entry_fails(self) -> None:
        package = build_pressure_package(["migration_surge"])
        package["pressures"].append(dict(package["pressures"][0]))
        with self.assertRaisesRegex(PressureCompilationError, "duplicate"):
            compile_pressure_package(package, BaselineRates())

    def test_non_synthetic_pressure_fails(self) -> None:
        package = build_pressure_package(["migration_surge"])
        package["pressures"][0]["config"]["synthetic_assumption"] = False
        with self.assertRaisesRegex(PressureCompilationError, "synthetic_assumption"):
            compile_pressure_package(package, BaselineRates())


if __name__ == "__main__":
    unittest.main()
