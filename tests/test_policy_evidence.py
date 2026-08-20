"""Contract tests for policy-lever scope evidence and parameter boundaries."""

import csv
import unittest
from pathlib import Path

from policy_sandbox.plugins.registry import available_interventions


class PolicyEvidenceTests(unittest.TestCase):
    """Ensure every registered lever has a public scope source, not an effect claim."""

    def test_registered_levers_have_scope_evidence(self) -> None:
        root = Path(__file__).resolve().parents[1]
        path = (
            root
            / "docs"
            / "domains"
            / "new_urbanization"
            / "policy_lever_evidence.csv"
        )
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(
            {row["intervention_name"] for row in rows},
            set(available_interventions()),
        )
        for row in rows:
            self.assertTrue(row["source_url"].startswith("https://"))
            self.assertIn("gov.cn", row["source_url"])
            self.assertEqual(
                row["effect_parameter_status"],
                "synthetic_not_from_policy",
            )


if __name__ == "__main__":
    unittest.main()
