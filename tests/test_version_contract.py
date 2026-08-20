from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

import policy_sandbox


ROOT = Path(__file__).resolve().parents[1]


class VersionContractTests(unittest.TestCase):
    def test_public_version_surfaces_are_synchronized(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project_version = tomllib.load(handle)["project"]["version"]

        self.assertEqual(project_version, policy_sandbox.__version__)
        self.assertIn(f"当前版本为 `{project_version}`", (ROOT / "README.md").read_text("utf-8"))
        self.assertIn(f"应用版本：`{project_version}`", (ROOT / "CURRENT_STATE.md").read_text("utf-8"))
        self.assertIn(f"## {project_version} —", (ROOT / "CHANGELOG.md").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
