"""Negative and legitimate-control tests for the release isolation gate."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


def _load_checker():
    root = Path(__file__).resolve().parents[1]
    checker_path = root / "scripts" / "check_isolation.py"
    spec = importlib.util.spec_from_file_location("policy_sandbox_isolation_check", checker_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load isolation checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IsolationScanTests(unittest.TestCase):
    """Ensure the gate rejects bypass forms without blocking ordinary source text."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.checker = _load_checker()

    def _scan(self, files: dict[str, bytes | str]) -> list[dict[str, str]]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidates = []
            for name, content in files.items():
                relative = Path(name)
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(content, bytes):
                    path.write_bytes(content)
                else:
                    path.write_text(content, encoding="utf-8")
                candidates.append(relative)
            return self.checker.scan_candidate_files(root, candidates)

    def test_ordinary_source_and_https_urls_pass(self) -> None:
        violations = self._scan(
            {
                "README.md": "See https://example.org/policy and use synthetic inputs.\n",
                "docs/table.csv": "key,value\nmode,demo\n",
            }
        )
        self.assertEqual(violations, [])

    def test_provider_token_and_generic_password_are_rejected(self) -> None:
        provider_token = "gh" + "p_" + ("A" * 36)
        password = "correct" + "-horse-battery"
        violations = self._scan(
            {"config.txt": f"token={provider_token}\npassword={password}\n"}
        )
        reasons = {item["reason"] for item in violations}
        self.assertIn("possible secret (github_token)", reasons)
        self.assertIn("possible secret (generic_credential_assignment)", reasons)

    def test_cross_platform_absolute_paths_are_rejected(self) -> None:
        windows_path = "G:" + "\\private\\input.csv"
        posix_path = "/" + "home/researcher/private/input.csv"
        violations = self._scan(
            {"notes.md": f"windows={windows_path}\nposix={posix_path}\n"}
        )
        reasons = {item["reason"] for item in violations}
        self.assertIn("local absolute path (windows_drive_path)", reasons)
        self.assertIn("local absolute path (posix_local_path)", reasons)

    def test_prohibited_directory_is_rejected_even_when_candidate_is_explicit(self) -> None:
        violations = self._scan({"data/private/respondents.csv": "id,name\n1,A\n"})
        self.assertEqual(
            violations[0]["reason"],
            "prohibited private/generated directory",
        )

    def test_unknown_binary_representation_fails_closed(self) -> None:
        violations = self._scan({"payload.bin": b"\x01\x02\x03"})
        self.assertEqual(violations[0]["reason"], "unsupported candidate file type")


if __name__ == "__main__":
    unittest.main()
