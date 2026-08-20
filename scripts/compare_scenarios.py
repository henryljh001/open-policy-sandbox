"""Run a synthetic scenario comparison and emit decision-ready artifacts."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from policy_sandbox.application.compare_scenarios import (
    ComparisonValidationError,
    run_catalog_comparison,
)
from policy_sandbox.application.decision_products import build_decision_package


def _load_plan(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ComparisonValidationError(
            "invalid_plan_document",
            "comparison plan must be a JSON object",
        )
    return value


def _write_package(package: Mapping[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, tuple[str, Any]] = {
        "comparison": ("comparison.json", package["comparison"]),
        "decision_brief": ("decision_brief.json", package["decision_brief"]),
        "decision_brief_markdown": (
            "decision_brief.md",
            package["decision_brief_markdown"],
        ),
        "audit_bundle": ("audit_bundle.json", package["audit_bundle"]),
    }
    manifest: dict[str, str] = {}
    for key, (name, value) in artifacts.items():
        path = output_dir / name
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(
                json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        manifest[key] = str(path.resolve())
    return manifest


def main() -> None:
    """Validate a plan, run fair repetitions, and emit four decision artifacts."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        comparison = run_catalog_comparison(_load_plan(args.plan))
        package = build_decision_package(comparison)
    except (ComparisonValidationError, json.JSONDecodeError, OSError) as error:
        if isinstance(error, ComparisonValidationError):
            envelope = error.to_mapping()
        else:
            envelope = {
                "error": {
                    "code": "plan_io_error",
                    "message": str(error),
                    "details": [],
                }
            }
        print(json.dumps(envelope, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2) from error

    if args.output_dir is None:
        print(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True))
        return
    manifest = _write_package(package, args.output_dir)
    print(
        json.dumps(
            {
                "comparison_id": comparison["comparison_id"],
                "package_digest": package["package_digest"],
                "artifacts": manifest,
                "usage_level": "Demo",
                "synthetic": True,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
