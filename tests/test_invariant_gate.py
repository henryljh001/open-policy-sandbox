"""Tests for non-bypassable accounting gates."""

import unittest

from policy_sandbox.plugins import engines as _engines  # noqa: F401
from policy_sandbox.plugins.registry import SimulationEngineFactory


class InvariantGateTests(unittest.TestCase):
    """Ensure public engine configuration cannot disable conservation checks."""

    def test_invariant_gate_cannot_be_disabled(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot be disabled"):
            SimulationEngineFactory(
                "new_urbanization_baseline",
                {"strict_invariants": False},
            )


if __name__ == "__main__":
    unittest.main()
