"""Fail closed when public-repository boundaries are violated."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

MAX_TEXT_BYTES = 5 * 1024 * 1024
PROHIBITED_PREFIXES = (
    ("data", "private"),
    ("data", "raw"),
    ("artifacts",),
    ("outputs",),
    ("_versions",),
    ("_复盘",),
)
FORBIDDEN_DATA_SUFFIXES = {
    ".7z",
    ".avro",
    ".crt",
    ".db",
    ".doc",
    ".docx",
    ".duckdb",
    ".feather",
    ".geojson",
    ".gpkg",
    ".gz",
    ".jpeg",
    ".jpg",
    ".key",
    ".kml",
    ".parquet",
    ".pdf",
    ".pem",
    ".pfx",
    ".pickle",
    ".pkl",
    ".png",
    ".rar",
    ".sav",
    ".shp",
    ".sqlite",
    ".tar",
    ".tif",
    ".tiff",
    ".xls",
    ".xlsx",
    ".zip",
}
TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "LICENSE",
    "NOTICE",
}


def _joined(*parts: str) -> str:
    """Build sensitive detector literals without embedding example credentials."""

    return "".join(parts)


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_token", re.compile(_joined(r"s", r"k-[A-Za-z0-9_-]{20,}"))),
    (
        "github_token",
        re.compile(_joined(r"(?:gh", r"[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ),
    ("aws_access_key", re.compile(_joined(r"AK", r"IA[0-9A-Z]{16}"))),
    ("google_api_key", re.compile(_joined(r"AI", r"za[0-9A-Za-z_-]{35}"))),
    ("slack_token", re.compile(_joined(r"xo", r"x[baprs]-[A-Za-z0-9-]{20,}"))),
    (
        "private_key",
        re.compile(_joined(r"-----BEGIN ", r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ),
    (
        "generic_credential_assignment",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?key|client[_-]?secret|password|passwd|secret|token)\b"
            r"\s*[:=]\s*[\"']?[A-Za-z0-9+/=_-]{12,}"
        ),
    ),
)

ABSOLUTE_PATH_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("windows_drive_path", re.compile(r"(?i)(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/])")),
    ("windows_unc_path", re.compile(r"(?<![\\])\\\\[^\s\\/]+[\\/][^\s\\/]+")),
    (
        "posix_local_path",
        re.compile(r"(?<![:A-Za-z0-9])/(?:home|Users|var|tmp|opt|mnt|Volumes)/[^\s`'\"]+"),
    ),
    ("home_relative_path", re.compile(r"(?<![A-Za-z0-9])~[\\/][^\s`'\"]+")),
    ("file_uri", re.compile(r"(?i)\bfile://")),
)


def candidate_manifest(root: Path, *, staged_only: bool = False) -> tuple[Path, ...]:
    """Return the exact tracked plus non-ignored untracked Git candidate set."""

    command = ["git", "-C", str(root), "ls-files", "--cached"]
    if not staged_only:
        command.extend(["--others", "--exclude-standard"])
    command.append("-z")
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git candidate manifest failed: {message or 'unknown error'}")
    entries = {
        Path(os.fsdecode(raw))
        for raw in completed.stdout.split(b"\0")
        if raw
    }
    return tuple(sorted(entries, key=lambda item: item.as_posix()))


def _is_prohibited(relative: Path) -> bool:
    folded = tuple(part.casefold() for part in relative.parts)
    return any(folded[: len(prefix)] == prefix for prefix in PROHIBITED_PREFIXES)


def _is_reparse_point(path: Path) -> bool:
    metadata = path.lstat()
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return path.is_symlink() or bool(reparse_flag and attributes & reparse_flag)


def _add(violations: list[dict[str, str]], relative: Path, reason: str) -> None:
    violations.append({"path": relative.as_posix(), "reason": reason})


def _scan_text(
    relative: Path,
    text: str,
    violations: list[dict[str, str]],
) -> None:
    for rule, pattern in ABSOLUTE_PATH_PATTERNS:
        if pattern.search(text):
            _add(violations, relative, f"local absolute path ({rule})")
    for rule, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            _add(violations, relative, f"possible secret ({rule})")


def scan_candidate_files(root: Path, candidates: Iterable[Path]) -> list[dict[str, str]]:
    """Inspect every candidate file and fail closed on unsupported representations."""

    root_resolved = root.resolve()
    violations: list[dict[str, str]] = []
    for relative in candidates:
        if relative.is_absolute() or ".." in relative.parts:
            _add(violations, relative, "candidate path escapes repository")
            continue
        if _is_prohibited(relative):
            _add(violations, relative, "prohibited private/generated directory")
            continue
        if relative.name == ".env" or (
            relative.name.startswith(".env.") and relative.name != ".env.example"
        ):
            _add(violations, relative, "environment secret file")
            continue

        path = root / relative
        if not path.exists() or not path.is_file():
            _add(violations, relative, "missing or non-regular candidate")
            continue
        if _is_reparse_point(path):
            _add(violations, relative, "symlink or reparse-point candidate")
            continue
        try:
            path.resolve(strict=True).relative_to(root_resolved)
        except (OSError, ValueError):
            _add(violations, relative, "candidate resolves outside repository")
            continue

        suffix = path.suffix.casefold()
        if suffix in FORBIDDEN_DATA_SUFFIXES:
            _add(violations, relative, "forbidden binary/data suffix")
            continue
        if suffix not in TEXT_SUFFIXES and path.name not in TEXT_FILENAMES:
            _add(violations, relative, "unsupported candidate file type")
            continue

        payload = path.read_bytes()
        if len(payload) > MAX_TEXT_BYTES:
            _add(violations, relative, "candidate text exceeds scan size limit")
            continue
        if b"\0" in payload:
            _add(violations, relative, "binary content in text candidate")
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            _add(violations, relative, "candidate text is not UTF-8")
            continue
        _scan_text(relative, text, violations)
    return violations


def _governance_checks(
    root: Path,
    candidates: Sequence[Path],
    violations: list[dict[str, str]],
) -> dict[str, str]:
    names = {item.as_posix() for item in candidates}
    for required in ("LICENSE", "NOTICE"):
        if required not in names:
            _add(violations, Path(required), "missing from candidate manifest")

    license_path = root / "LICENSE"
    license_status = "missing"
    if license_path.is_file():
        license_text = license_path.read_text(encoding="utf-8", errors="strict")
        if "Apache License" in license_text and "Version 2.0, January 2004" in license_text:
            license_status = "apache-2.0"
        else:
            license_status = "unrecognized"
            _add(violations, Path("LICENSE"), "license text conflicts with Apache-2.0 declaration")

    notice_path = root / "NOTICE"
    notice_status = "present" if notice_path.is_file() and notice_path.stat().st_size else "missing"
    if notice_status == "missing":
        _add(violations, Path("NOTICE"), "NOTICE is missing or empty")
    return {"license": license_status, "notice": notice_status}


def run_check(root: Path, *, staged_only: bool = False) -> dict[str, object]:
    """Run the exact candidate-manifest release boundary check."""

    try:
        candidates = candidate_manifest(root, staged_only=staged_only)
    except RuntimeError as exc:
        return {
            "check": "repository_isolation",
            "status": "fail",
            "manifest_mode": "staged" if staged_only else "candidate",
            "candidate_manifest_count": 0,
            "candidate_manifest_sha256": None,
            "governance": {"license": "unknown", "notice": "unknown"},
            "violations": [{"path": ".git", "reason": str(exc)}],
        }

    manifest_payload = "\n".join(item.as_posix() for item in candidates).encode("utf-8")
    violations = scan_candidate_files(root, candidates)
    governance = _governance_checks(root, candidates, violations)
    return {
        "check": "repository_isolation",
        "status": "pass" if not violations else "fail",
        "manifest_mode": "staged" if staged_only else "candidate",
        "candidate_manifest_count": len(candidates),
        "candidate_manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
        "governance": governance,
        "violations": violations,
    }


def main() -> int:
    """Print the machine-readable result and return nonzero on violations."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="scan only the Git index")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = run_check(root, staged_only=args.staged)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
