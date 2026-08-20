"""Low-dependency repository contract tests."""

import json
import unittest
from pathlib import Path


class RepositoryContractTests(unittest.TestCase):
    """Verify schemas, examples, and open-source governance files."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]

    def test_all_schemas_are_json_objects(self) -> None:
        schema_paths = sorted((self.root / "schemas").rglob("*.schema.json"))
        self.assertEqual(len(schema_paths), 18)
        for path in schema_paths:
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(value["type"], "object")

    def test_examples_are_explicitly_synthetic(self) -> None:
        example_paths = sorted((self.root / "examples").rglob("*.json"))
        self.assertEqual(len(example_paths), 8)
        for path in example_paths:
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(value["synthetic"], path)

    def test_examples_use_registered_engine_names(self) -> None:
        baseline = json.loads(
            (self.root / "examples" / "minimal_scenario.json").read_text(
                encoding="utf-8"
            )
        )
        microsim = json.loads(
            (
                self.root
                / "examples"
                / "new_urbanization"
                / "microsim_pressure_scenario.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(baseline["engine"]["name"], "deterministic_baseline")
        self.assertEqual(microsim["engine"]["name"], "new_urbanization_microsim")

    def test_open_source_governance_files_exist(self) -> None:
        required = ("LICENSE", "NOTICE", "CONTRIBUTING.md", "SECURITY.md", "GOVERNANCE.md")
        for name in required:
            self.assertTrue((self.root / name).is_file(), name)
        license_text = (self.root / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Apache License", license_text)
        self.assertIn("Version 2.0, January 2004", license_text)


if __name__ == "__main__":
    unittest.main()
