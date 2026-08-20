"""Tests for policy intervention registration and explicit effect compilation."""

import unittest

from policy_sandbox.plugins.base import PolicyIntervention
from policy_sandbox.plugins.registry import (
    PolicyInterventionFactory,
    available_interventions,
    register_intervention,
)


class InterventionRegistryTests(unittest.TestCase):
    """Verify seven strict, config-driven new-urbanization interventions."""

    def test_seven_mvp_interventions_are_discovered(self) -> None:
        self.assertEqual(
            set(available_interventions()),
            {
                "settlement_threshold",
                "resident_based_service_eligibility",
                "skills_and_employment_support",
                "affordable_housing",
                "county_service_expansion",
                "citizenization_transfer",
                "land_capacity_bundle",
            },
        )

    def test_intensity_scales_only_explicit_effects(self) -> None:
        intervention = PolicyInterventionFactory(
            "settlement_threshold",
            {
                "intensity": 0.5,
                "synthetic_assumption": True,
                "rate_deltas": {"hukou_conversion_rate": 0.1},
                "tracked_adjustments": {"settlement_access_gain_pp": 10.0},
            },
        )
        effect = intervention.compile()
        self.assertEqual(effect.rate_deltas["hukou_conversion_rate"], 0.05)
        self.assertEqual(effect.tracked_adjustments["settlement_access_gain_pp"], 5.0)

    def test_non_synthetic_effect_is_rejected(self) -> None:
        intervention = PolicyInterventionFactory(
            "citizenization_transfer",
            {
                "intensity": 1.0,
                "synthetic_assumption": False,
                "rate_deltas": {"transfer_growth_rate": 0.02},
                "tracked_adjustments": {},
            },
        )
        with self.assertRaisesRegex(ValueError, "synthetic_assumption=true"):
            intervention.compile()

    def test_unknown_effect_field_is_rejected(self) -> None:
        intervention = PolicyInterventionFactory(
            "affordable_housing",
            {
                "intensity": 1.0,
                "synthetic_assumption": True,
                "rate_deltas": {"unknown_rate": 0.02},
                "tracked_adjustments": {},
            },
        )
        with self.assertRaisesRegex(ValueError, "unsupported rate_deltas"):
            intervention.compile()

    def test_duplicate_intervention_registration_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "already registered"):

            @register_intervention("settlement_threshold")
            class DuplicateIntervention(PolicyIntervention):
                def compile(self):  # type: ignore[no-untyped-def]
                    raise NotImplementedError


if __name__ == "__main__":
    unittest.main()

