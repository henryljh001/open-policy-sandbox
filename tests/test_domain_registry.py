"""Tests for policy domain registration and new urbanization configuration."""

import json
import unittest
from pathlib import Path

from policy_sandbox.plugins.registry import DomainPluginFactory, available_domains


class DomainRegistryTests(unittest.TestCase):
    """Verify domain discovery, metadata, and strict configuration checks."""

    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.config = json.loads(
            (root / "examples" / "new_urbanization" / "domain_config.json").read_text(
                encoding="utf-8"
            )
        )

    def test_new_urbanization_is_auto_discovered(self) -> None:
        self.assertIn("new_urbanization", available_domains())

    def test_factory_returns_demo_domain(self) -> None:
        domain = DomainPluginFactory("new_urbanization", self.config)
        self.assertEqual(domain.descriptor.status, "demo")
        self.assertIn("citizenization", domain.policy_dimensions())

    def test_invalid_time_step_fails(self) -> None:
        invalid = dict(self.config)
        invalid["time_step"] = "monthly"
        with self.assertRaisesRegex(ValueError, "time_step must be annual"):
            DomainPluginFactory("new_urbanization", invalid)

    def test_unknown_domain_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown policy domain"):
            DomainPluginFactory("not_registered", self.config)


if __name__ == "__main__":
    unittest.main()
