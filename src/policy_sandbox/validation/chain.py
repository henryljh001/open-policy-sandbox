"""Cross-stage integrity checks for U6 and U7 preregistrations."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from policy_sandbox.validation.preregistration import (
    build_validation_preregistration_report,
)

VALIDATOR_NAME = "u6_u7_validation_registration_chain"
VALIDATOR_VERSION = "0.1.0"
_IMPLEMENTATION_FIELDS = (
    "repository_commit",
    "software_version",
    "engine_name",
    "engine_version",
    "config_digest",
    "parameter_bounds_digest",
    "implementation_freeze_digest",
)


class ValidationRegistrationChainError(ValueError):
    """Raised when the U6-to-U7 preregistration chain is inconsistent."""

    def __init__(self, report: Mapping[str, Any]) -> None:
        self.report = dict(report)
        count = report.get("summary", {}).get("error_count", "unknown")
        super().__init__(f"Validation registration chain failed: {count} errors")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _new_check(check_id: str) -> dict[str, Any]:
    return {"check_id": check_id, "status": "pass", "issues": []}


def _add_issue(
    check: dict[str, Any],
    *,
    code: str,
    path: str,
    message: str,
) -> None:
    check["issues"].append(
        {"code": code, "severity": "error", "path": path, "message": message}
    )
    check["status"] = "fail"


def _parsed_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _check_member_semantics(
    u6_document: Mapping[str, Any],
    u7_document: Mapping[str, Any],
    check: dict[str, Any],
) -> None:
    for label, document in (("u6", u6_document), ("u7", u7_document)):
        report = build_validation_preregistration_report(document)
        if report["summary"]["status"] != "pass":
            _add_issue(
                check,
                code=f"{label.upper()}_REGISTRATION_INVALID",
                path=label,
                message=(
                    f"{label.upper()} preregistration must pass its own semantic "
                    "validator before chain validation."
                ),
            )


def _check_stage_order(
    u6_document: Mapping[str, Any],
    u7_document: Mapping[str, Any],
    check: dict[str, Any],
) -> None:
    expected = (
        ("u6", u6_document, "u6_calibration"),
        ("u7", u7_document, "u7_holdout"),
    )
    for label, document, stage in expected:
        if document.get("registration_stage") != stage:
            _add_issue(
                check,
                code="INVALID_CHAIN_STAGE_ORDER",
                path=f"{label}.registration_stage",
                message=f"{label.upper()} chain member must use stage {stage}.",
            )
        if document.get("registration_status") != "sealed_pre_results":
            _add_issue(
                check,
                code="UNSEALED_CHAIN_MEMBER",
                path=f"{label}.registration_status",
                message="Both chain members must be sealed preregistrations.",
            )

    u6_time = _parsed_datetime(u6_document.get("registered_at"))
    u7_time = _parsed_datetime(u7_document.get("registered_at"))
    if u6_time is not None and u7_time is not None and u7_time <= u6_time:
        _add_issue(
            check,
            code="INVALID_REGISTRATION_TIME_ORDER",
            path="u7.registered_at",
            message="U7 must be registered after the U6 preregistration.",
        )


def _check_digest_references(
    u6_document: Mapping[str, Any],
    u7_document: Mapping[str, Any],
    check: dict[str, Any],
) -> None:
    u6_digest = u6_document.get("registration_digest")
    u6_prerequisites = _mapping(u6_document.get("prerequisites"))
    u7_prerequisites = _mapping(u7_document.get("prerequisites"))
    if u7_prerequisites.get("U6_registration_digest") != u6_digest:
        _add_issue(
            check,
            code="U6_REGISTRATION_REFERENCE_MISMATCH",
            path="u7.prerequisites.U6_registration_digest",
            message="U7 must reference the exact sealed U6 registration digest.",
        )
    if u7_prerequisites.get("U6_evidence_digest") == u6_digest:
        _add_issue(
            check,
            code="U6_EVIDENCE_REFERENCE_COLLISION",
            path="u7.prerequisites.U6_evidence_digest",
            message=(
                "U6 result evidence must be a distinct artifact from its preregistration."
            ),
        )
    if u7_prerequisites.get("I5b_evidence_digest") != u6_prerequisites.get(
        "I5b_evidence_digest"
    ):
        _add_issue(
            check,
            code="I5B_REFERENCE_DRIFT",
            path="u7.prerequisites.I5b_evidence_digest",
            message="U6 and U7 must reference the same I5b evidence package.",
        )


def _check_frozen_inputs(
    u6_document: Mapping[str, Any],
    u7_document: Mapping[str, Any],
    check: dict[str, Any],
) -> None:
    for field in ("scope", "data_freeze"):
        if u7_document.get(field) != u6_document.get(field):
            _add_issue(
                check,
                code=f"{field.upper()}_DRIFT",
                path=f"u7.{field}",
                message=f"U7 {field} must exactly match the sealed U6 registration.",
            )


def _check_implementation_continuity(
    u6_document: Mapping[str, Any],
    u7_document: Mapping[str, Any],
    check: dict[str, Any],
) -> None:
    u6_freeze = _mapping(u6_document.get("model_freeze"))
    u7_freeze = _mapping(u7_document.get("model_freeze"))
    for field in _IMPLEMENTATION_FIELDS:
        if u7_freeze.get(field) != u6_freeze.get(field):
            _add_issue(
                check,
                code="IMPLEMENTATION_FREEZE_DRIFT",
                path=f"u7.model_freeze.{field}",
                message=(
                    "U7 may add final calibration digests but cannot change the "
                    f"U6 implementation freeze field {field}."
                ),
            )


def build_validation_registration_chain_report(
    u6_document: Mapping[str, Any],
    u7_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two sealed registrations without reading data or result files."""

    if not isinstance(u6_document, Mapping) or not isinstance(u7_document, Mapping):
        raise TypeError("u6_document and u7_document must be objects")
    checks = {
        name: _new_check(name)
        for name in (
            "member_semantics",
            "stage_order",
            "digest_references",
            "frozen_inputs",
            "implementation_continuity",
        )
    }
    _check_member_semantics(u6_document, u7_document, checks["member_semantics"])
    _check_stage_order(u6_document, u7_document, checks["stage_order"])
    _check_digest_references(u6_document, u7_document, checks["digest_references"])
    _check_frozen_inputs(u6_document, u7_document, checks["frozen_inputs"])
    _check_implementation_continuity(
        u6_document,
        u7_document,
        checks["implementation_continuity"],
    )
    check_list = list(checks.values())
    issues = [issue for check in check_list for issue in check["issues"]]
    return {
        "schema_version": "1.0.0",
        "validator": {"name": VALIDATOR_NAME, "version": VALIDATOR_VERSION},
        "u6_registration_digest": u6_document.get("registration_digest"),
        "u7_registration_digest": u7_document.get("registration_digest"),
        "summary": {
            "status": "fail" if issues else "pass",
            "check_count": len(check_list),
            "error_count": len(issues),
        },
        "checks": check_list,
        "capability_effect": {
            "automatic_promotion": False,
            "I5b": "unchanged",
            "U6": "unchanged",
            "U7": "unchanged",
            "U8": "unchanged",
            "usage_level": "unchanged",
        },
    }


def validate_validation_registration_chain(
    u6_document: Mapping[str, Any],
    u7_document: Mapping[str, Any],
) -> dict[str, Any]:
    """Raise on any semantic or cross-stage preregistration inconsistency."""

    report = build_validation_registration_chain_report(u6_document, u7_document)
    if report["summary"]["status"] == "fail":
        raise ValidationRegistrationChainError(report)
    return report
