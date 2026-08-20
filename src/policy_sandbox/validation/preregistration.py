"""Deterministic pre-result contracts for U6 calibration and U7 holdout validation."""

from __future__ import annotations

import copy
import json
import math
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from policy_sandbox.adapters.contracts import canonical_digest

VALIDATOR_NAME = "u6_u7_validation_preregistration_semantic"
VALIDATOR_VERSION = "0.1.0"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_COMMIT = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

ELIGIBLE_INDICATORS = frozenset(
    {
        "total_population",
        "urbanization_rate",
        "employment_rate",
        "debt_to_revenue",
        "education_capacity_per_1000",
        "health_capacity_per_1000",
        "housing_occupancy_rate",
    }
)
BLOCKED_INDICATORS = frozenset({"used_construction_land"})
REGISTERED_MOMENT_RULES = {
    "total_population": ("final_total_population", "person"),
    "urbanization_rate": ("final_urbanization_rate", "percent"),
    "employment_rate": ("final_employment_rate", "percent"),
    "debt_to_revenue": ("final_debt_to_revenue", "percent"),
    "education_capacity_per_1000": (
        "final_education_capacity_per_1000",
        "capacity_per_1000_persons",
    ),
    "health_capacity_per_1000": (
        "final_health_capacity_per_1000",
        "capacity_per_1000_persons",
    ),
    "housing_occupancy_rate": ("final_housing_occupancy_rate", "percent"),
}


class ValidationPreregistrationError(ValueError):
    """Raised when a preregistration fails pre-result semantic checks."""

    def __init__(self, report: Mapping[str, Any]) -> None:
        self.report = dict(report)
        count = report.get("summary", {}).get("error_count", "unknown")
        super().__init__(f"Validation preregistration failed: {count} errors")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _objects(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strict_digest(value: Any) -> str:
    json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return canonical_digest(value)


def calculate_validation_registration_digest(document: Mapping[str, Any]) -> str:
    """Hash the complete registration with its digest slot normalized to null."""

    if not isinstance(document, Mapping):
        raise TypeError("document must be an object")
    payload = copy.deepcopy(dict(document))
    payload["registration_digest"] = None
    return _strict_digest(payload)


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _is_finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _is_timezone_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


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


def _check_common(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    if document.get("schema_version") != "1.0.0":
        _add_issue(
            check,
            code="UNSUPPORTED_SCHEMA_VERSION",
            path="schema_version",
            message="Preregistration semantics require schema version 1.0.0.",
        )
    if document.get("domain") != "new_urbanization":
        _add_issue(
            check,
            code="UNSUPPORTED_DOMAIN",
            path="domain",
            message="This preregistration contract is frozen for new_urbanization.",
        )
    if document.get("purpose") != "pre_results_registration_only":
        _add_issue(
            check,
            code="INVALID_PURPOSE",
            path="purpose",
            message="The document must remain a pre-results registration.",
        )
    if document.get("contains_results") is not False:
        _add_issue(
            check,
            code="RESULT_CONTENT_FORBIDDEN",
            path="contains_results",
            message="Preregistration documents cannot contain validation results.",
        )

    stage = document.get("registration_stage")
    if stage not in {"u6_calibration", "u7_holdout"}:
        _add_issue(
            check,
            code="INVALID_REGISTRATION_STAGE",
            path="registration_stage",
            message="Registration stage must be u6_calibration or u7_holdout.",
        )

    effect = _mapping(document.get("capability_effect"))
    expected = {
        "automatic_promotion": False,
        "I5b": "unchanged",
        "U6": "unchanged",
        "U7": "unchanged",
        "U8": "unchanged",
        "usage_level": "unchanged",
    }
    for field, required in expected.items():
        if effect.get(field) != required:
            _add_issue(
                check,
                code="CAPABILITY_PREMATURE_PROMOTION",
                path=f"capability_effect.{field}",
                message=f"Preregistration must leave {field} {required!r}.",
            )


def _check_pre_result_access(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    access = _mapping(document.get("result_access"))
    status = document.get("registration_status")
    stage = document.get("registration_stage")
    expected_calibration_access = (
        stage == "u7_holdout" and status == "sealed_pre_results"
    )
    expected = {
        "calibration_results_viewed": expected_calibration_access,
        "holdout_results_viewed": False,
    }
    for field, required in expected.items():
        if access.get(field) is not required:
            _add_issue(
                check,
                code="RESULT_ACCESS_STAGE_MISMATCH",
                path=f"result_access.{field}",
                message="Result-access state conflicts with the registration stage.",
            )

    one_time = _mapping(_mapping(document.get("u7_plan")).get("one_time_access"))
    expected = {
        "maximum_executions": 1,
        "consumed": False,
        "consumed_at": None,
        "attempt_id": None,
        "result_digest": None,
    }
    for field, required in expected.items():
        if one_time.get(field) != required:
            _add_issue(
                check,
                code="HOLDOUT_ACCESS_NOT_PRISTINE",
                path=f"u7_plan.one_time_access.{field}",
                message="The one-time holdout slot must be pristine before validation.",
            )


def _check_template(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    if document.get("synthetic") is not True:
        _add_issue(
            check,
            code="PUBLIC_TEMPLATE_MUST_BE_SYNTHETIC",
            path="synthetic",
            message="The public blank template must set synthetic=true.",
        )
    expected = {
        "registration_version": "0.0.0",
        "registered_at": None,
        "registration_digest": None,
    }
    for field, required in expected.items():
        if document.get(field) != required:
            _add_issue(
                check,
                code="TEMPLATE_FIELD_NOT_BLANK",
                path=field,
                message=f"Template field {field} must remain {required!r}.",
            )

    prerequisites = _mapping(document.get("prerequisites"))
    for field in (
        "I5b_evidence_digest",
        "U6_registration_digest",
        "U6_evidence_digest",
    ):
        if prerequisites.get(field) is not None:
            _add_issue(
                check,
                code="TEMPLATE_PREREQUISITE_NOT_BLANK",
                path=f"prerequisites.{field}",
                message="Public template prerequisite digests must remain null.",
            )

    scope = _mapping(document.get("scope"))
    for field in ("geographic_level", "calibration_window", "holdout_kind"):
        if scope.get(field) is not None:
            _add_issue(
                check,
                code="TEMPLATE_SCOPE_NOT_BLANK",
                path=f"scope.{field}",
                message="Public template scope fields must remain null.",
            )
    if scope.get("indicator_ids") != []:
        _add_issue(
            check,
            code="TEMPLATE_SCOPE_NOT_BLANK",
            path="scope.indicator_ids",
            message="Public template indicator scope must remain empty.",
        )

    for section_name in ("data_freeze", "model_freeze"):
        section = _mapping(document.get(section_name))
        for field, value in section.items():
            if value is not None:
                _add_issue(
                    check,
                    code="TEMPLATE_FREEZE_NOT_BLANK",
                    path=f"{section_name}.{field}",
                    message="Public template freeze identifiers must remain null.",
                )

    u6_plan = _mapping(document.get("u6_plan"))
    for field in ("moments", "parameter_bounds", "sensitivity_checks"):
        if u6_plan.get(field) != []:
            _add_issue(
                check,
                code="TEMPLATE_U6_PLAN_NOT_BLANK",
                path=f"u6_plan.{field}",
                message="Public template U6 plan arrays must remain empty.",
            )
    if u6_plan.get("maximum_calibration_attempts") is not None:
        _add_issue(
            check,
            code="TEMPLATE_U6_PLAN_NOT_BLANK",
            path="u6_plan.maximum_calibration_attempts",
            message="Public template attempt limit must remain null.",
        )

    u7_plan = _mapping(document.get("u7_plan"))
    for field in ("primary_metrics",):
        if u7_plan.get(field) != []:
            _add_issue(
                check,
                code="TEMPLATE_U7_PLAN_NOT_BLANK",
                path=f"u7_plan.{field}",
                message="Public template U7 metric list must remain empty.",
            )
    for field in ("externality_boundary", "independent_validator_role"):
        if u7_plan.get(field) is not None:
            _add_issue(
                check,
                code="TEMPLATE_U7_PLAN_NOT_BLANK",
                path=f"u7_plan.{field}",
                message="Public template U7 responsibility fields must remain null.",
            )
    amendment = _mapping(document.get("amendment_policy"))
    if amendment.get("change_log") != []:
        _add_issue(
            check,
            code="TEMPLATE_AMENDMENT_LOG_NOT_BLANK",
            path="amendment_policy.change_log",
            message="Public template amendment log must remain empty.",
        )


def _check_freezes(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    data_freeze = _mapping(document.get("data_freeze"))
    for field in (
        "calibration_dataset_digest",
        "holdout_dataset_digest",
        "data_partition_digest",
        "authorization_evidence_digest",
        "quality_report_digest",
    ):
        if not _is_digest(data_freeze.get(field)):
            _add_issue(
                check,
                code="MISSING_DATA_FREEZE_DIGEST",
                path=f"data_freeze.{field}",
                message="A sealed registration requires a lowercase SHA-256 digest.",
            )
    if data_freeze.get("calibration_dataset_digest") == data_freeze.get(
        "holdout_dataset_digest"
    ):
        _add_issue(
            check,
            code="CALIBRATION_HOLDOUT_NOT_SEPARATED",
            path="data_freeze.holdout_dataset_digest",
            message="Calibration and holdout datasets must have distinct digests.",
        )

    stage = document.get("registration_stage")
    model_freeze = _mapping(document.get("model_freeze"))
    if not isinstance(model_freeze.get("repository_commit"), str) or not _COMMIT.fullmatch(
        str(model_freeze.get("repository_commit"))
    ):
        _add_issue(
            check,
            code="INVALID_REPOSITORY_COMMIT",
            path="model_freeze.repository_commit",
            message="Model freeze requires a 40- or 64-character lowercase commit hash.",
        )
    for field in ("software_version", "engine_version"):
        value = model_freeze.get(field)
        if not isinstance(value, str) or _SEMVER.fullmatch(value) is None:
            _add_issue(
                check,
                code="INVALID_MODEL_VERSION",
                path=f"model_freeze.{field}",
                message="Frozen software and engine versions must use MAJOR.MINOR.PATCH.",
            )
    if not isinstance(model_freeze.get("engine_name"), str) or not model_freeze.get(
        "engine_name"
    ):
        _add_issue(
            check,
            code="MISSING_ENGINE_NAME",
            path="model_freeze.engine_name",
            message="A sealed registration requires the engine name.",
        )
    for field in (
        "config_digest",
        "parameter_bounds_digest",
        "implementation_freeze_digest",
    ):
        if not _is_digest(model_freeze.get(field)):
            _add_issue(
                check,
                code="MISSING_MODEL_FREEZE_DIGEST",
                path=f"model_freeze.{field}",
                message="A sealed registration requires a lowercase SHA-256 digest.",
            )
    for field in ("calibrated_parameters_digest", "validated_model_freeze_digest"):
        value = model_freeze.get(field)
        if stage == "u6_calibration" and value is not None:
            _add_issue(
                check,
                code="U6_FINAL_MODEL_NOT_AVAILABLE",
                path=f"model_freeze.{field}",
                message="U6 preregistration cannot claim a post-calibration model freeze.",
            )
        if stage == "u7_holdout" and not _is_digest(value):
            _add_issue(
                check,
                code="MISSING_FINAL_MODEL_FREEZE",
                path=f"model_freeze.{field}",
                message="U7 preregistration requires final calibrated model digests.",
            )
    if (
        stage == "u7_holdout"
        and model_freeze.get("calibrated_parameters_digest")
        == model_freeze.get("validated_model_freeze_digest")
    ):
        _add_issue(
            check,
            code="FINAL_MODEL_DIGEST_COLLISION",
            path="model_freeze.validated_model_freeze_digest",
            message="Parameters and the final model freeze must be distinct artifacts.",
        )


def _check_prerequisites(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    stage = document.get("registration_stage")
    prerequisites = _mapping(document.get("prerequisites"))
    i5b_digest = prerequisites.get("I5b_evidence_digest")
    u6_registration = prerequisites.get("U6_registration_digest")
    u6_evidence = prerequisites.get("U6_evidence_digest")
    if not _is_digest(i5b_digest):
        _add_issue(
            check,
            code="MISSING_I5B_EVIDENCE_REFERENCE",
            path="prerequisites.I5b_evidence_digest",
            message="A sealed registration must reference the separate I5b evidence package.",
        )
    if stage == "u6_calibration":
        for field, value in (
            ("U6_registration_digest", u6_registration),
            ("U6_evidence_digest", u6_evidence),
        ):
            if value is not None:
                _add_issue(
                    check,
                    code="U6_CANNOT_REFERENCE_FUTURE_EVIDENCE",
                    path=f"prerequisites.{field}",
                    message="U6 preregistration cannot reference future U6 evidence.",
                )
    elif stage == "u7_holdout":
        for field, value in (
            ("U6_registration_digest", u6_registration),
            ("U6_evidence_digest", u6_evidence),
        ):
            if not _is_digest(value):
                _add_issue(
                    check,
                    code="MISSING_U6_PREREQUISITE_REFERENCE",
                    path=f"prerequisites.{field}",
                    message="U7 preregistration must reference U6 registration and evidence.",
                )


def _check_scope(document: Mapping[str, Any], check: dict[str, Any]) -> list[Any]:
    scope = _mapping(document.get("scope"))
    if scope.get("holdout_kind") not in {"historical_period", "geographic_region"}:
        _add_issue(
            check,
            code="MISSING_HOLDOUT_KIND",
            path="scope.holdout_kind",
            message="Sealed registration requires a historical or geographic holdout.",
        )
    window = scope.get("calibration_window")
    if not isinstance(window, Mapping):
        _add_issue(
            check,
            code="MISSING_CALIBRATION_WINDOW",
            path="scope.calibration_window",
            message="Sealed registration requires a calibration time window.",
        )
    else:
        start = window.get("start_year")
        end = window.get("end_year")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start > end
        ):
            _add_issue(
                check,
                code="INVALID_CALIBRATION_WINDOW",
                path="scope.calibration_window",
                message="Calibration window requires integer start_year <= end_year.",
            )
    if not isinstance(scope.get("geographic_level"), str) or not scope.get(
        "geographic_level"
    ):
        _add_issue(
            check,
            code="MISSING_GEOGRAPHIC_LEVEL",
            path="scope.geographic_level",
            message="Sealed registration requires an explicit geographic level.",
        )

    indicator_ids = scope.get("indicator_ids")
    declared = indicator_ids if isinstance(indicator_ids, list) else []
    valid_strings = [item for item in declared if isinstance(item, str)]
    if (
        not declared
        or len(valid_strings) != len(declared)
        or len(set(valid_strings)) != len(valid_strings)
    ):
        _add_issue(
            check,
            code="INVALID_INDICATOR_SCOPE",
            path="scope.indicator_ids",
            message="A sealed registration requires a non-empty unique indicator scope.",
        )
    declared_set = set(valid_strings)
    unknown = sorted(declared_set - ELIGIBLE_INDICATORS - BLOCKED_INDICATORS)
    blocked = sorted(declared_set & BLOCKED_INDICATORS)
    if unknown:
        _add_issue(
            check,
            code="UNKNOWN_REGISTERED_INDICATOR",
            path="scope.indicator_ids",
            message="Unknown preregistered indicators: " + ", ".join(unknown) + ".",
        )
    if blocked:
        _add_issue(
            check,
            code="BLOCKED_REAL_INDICATOR",
            path="scope.indicator_ids",
            message="Blocked indicators cannot enter validation: "
            + ", ".join(blocked)
            + ".",
        )
    return valid_strings


def _check_u6_plan(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    declared = _check_scope(document, check)

    u6_plan = _mapping(document.get("u6_plan"))
    moments = _objects(u6_plan.get("moments"))
    moment_ids = [item.get("indicator_id") for item in moments]
    valid_moment_ids = [item for item in moment_ids if isinstance(item, str)]
    if (
        not moments
        or len(valid_moment_ids) != len(moment_ids)
        or len(set(valid_moment_ids)) != len(valid_moment_ids)
    ):
        _add_issue(
            check,
            code="INVALID_U6_MOMENTS",
            path="u6_plan.moments",
            message="U6 moments must be non-empty and unique by indicator_id.",
        )
    if set(valid_moment_ids) != set(declared):
        _add_issue(
            check,
            code="U6_SCOPE_MOMENT_MISMATCH",
            path="u6_plan.moments",
            message="U6 moment indicators must exactly match the frozen scope.",
        )
    for index, moment in enumerate(moments):
        indicator = moment.get("indicator_id")
        expected = REGISTERED_MOMENT_RULES.get(str(indicator))
        if expected is not None and (
            moment.get("model_outcome") != expected[0]
            or moment.get("unit") != expected[1]
        ):
            _add_issue(
                check,
                code="U6_MOMENT_BINDING_MISMATCH",
                path=f"u6_plan.moments[{index}]",
                message="Indicator must retain its frozen model outcome and unit binding.",
            )
        tolerance = moment.get("tolerance")
        if not _is_finite_number(tolerance) or float(tolerance) <= 0:
            _add_issue(
                check,
                code="INVALID_PREREGISTERED_TOLERANCE",
                path=f"u6_plan.moments[{index}].tolerance",
                message="Preregistered tolerances must be finite and greater than zero.",
            )
        if moment.get("mode") not in {"absolute", "relative"}:
            _add_issue(
                check,
                code="INVALID_TOLERANCE_MODE",
                path=f"u6_plan.moments[{index}].mode",
                message="Tolerance mode must be absolute or relative.",
            )

    bounds = _objects(u6_plan.get("parameter_bounds"))
    bound_ids = [item.get("parameter_id") for item in bounds]
    valid_bound_ids = [item for item in bound_ids if isinstance(item, str)]
    if (
        not bounds
        or len(valid_bound_ids) != len(bound_ids)
        or len(set(valid_bound_ids)) != len(valid_bound_ids)
    ):
        _add_issue(
            check,
            code="INVALID_PARAMETER_BOUNDS",
            path="u6_plan.parameter_bounds",
            message="Sealed calibration requires unique, non-empty parameter bounds.",
        )
    for index, bound in enumerate(bounds):
        minimum = bound.get("minimum")
        maximum = bound.get("maximum")
        if (
            not _is_finite_number(minimum)
            or not _is_finite_number(maximum)
            or float(minimum) >= float(maximum)
        ):
            _add_issue(
                check,
                code="INVALID_PARAMETER_INTERVAL",
                path=f"u6_plan.parameter_bounds[{index}]",
                message="Each parameter interval requires finite minimum < maximum.",
            )

    sensitivity = _objects(u6_plan.get("sensitivity_checks"))
    sensitivity_ids = [item.get("check_id") for item in sensitivity]
    valid_sensitivity_ids = [item for item in sensitivity_ids if isinstance(item, str)]
    if (
        not sensitivity
        or len(valid_sensitivity_ids) != len(sensitivity_ids)
        or len(set(valid_sensitivity_ids)) != len(valid_sensitivity_ids)
    ):
        _add_issue(
            check,
            code="MISSING_SENSITIVITY_PLAN",
            path="u6_plan.sensitivity_checks",
            message="Sealed U6 registration requires unique sensitivity checks.",
        )
    attempts = u6_plan.get("maximum_calibration_attempts")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        _add_issue(
            check,
            code="INVALID_CALIBRATION_ATTEMPT_LIMIT",
            path="u6_plan.maximum_calibration_attempts",
            message="Calibration attempt limit must be a positive integer.",
        )


def _check_u7_plan(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    _check_scope(document, check)

    u7_plan = _mapping(document.get("u7_plan"))
    metrics = _objects(u7_plan.get("primary_metrics"))
    metric_ids = [item.get("metric_id") for item in metrics]
    valid_metric_ids = [item for item in metric_ids if isinstance(item, str)]
    if (
        not metrics
        or len(valid_metric_ids) != len(metric_ids)
        or len(set(valid_metric_ids)) != len(valid_metric_ids)
    ):
        _add_issue(
            check,
            code="INVALID_U7_PRIMARY_METRICS",
            path="u7_plan.primary_metrics",
            message="U7 primary metrics must be non-empty and unique.",
        )
    for index, metric in enumerate(metrics):
        if metric.get("direction") not in {"maximum", "minimum"}:
            _add_issue(
                check,
                code="INVALID_U7_METRIC_DIRECTION",
                path=f"u7_plan.primary_metrics[{index}].direction",
                message="Metric direction must be maximum or minimum.",
            )
        if not _is_finite_number(metric.get("threshold")):
            _add_issue(
                check,
                code="INVALID_U7_THRESHOLD",
                path=f"u7_plan.primary_metrics[{index}].threshold",
                message="U7 thresholds must be finite numbers.",
            )
    for field in ("externality_boundary", "independent_validator_role"):
        if not isinstance(u7_plan.get(field), str) or not u7_plan.get(field):
            _add_issue(
                check,
                code="MISSING_U7_RESPONSIBILITY_FIELD",
                path=f"u7_plan.{field}",
                message="Sealed U7 registration requires explicit boundary and responsibility.",
            )


def _check_inactive_stage_plan(
    document: Mapping[str, Any],
    check: dict[str, Any],
) -> None:
    stage = document.get("registration_stage")
    if stage == "u6_calibration":
        u7_plan = _mapping(document.get("u7_plan"))
        if u7_plan.get("primary_metrics") != []:
            _add_issue(
                check,
                code="U7_PLAN_MUST_WAIT_FOR_U6",
                path="u7_plan.primary_metrics",
                message="The U7 plan is sealed only after U6 calibration is complete.",
            )
        for field in ("externality_boundary", "independent_validator_role"):
            if u7_plan.get(field) is not None:
                _add_issue(
                    check,
                    code="U7_PLAN_MUST_WAIT_FOR_U6",
                    path=f"u7_plan.{field}",
                    message="The U7 plan is sealed only after U6 calibration is complete.",
                )
    elif stage == "u7_holdout":
        u6_plan = _mapping(document.get("u6_plan"))
        for field in ("moments", "parameter_bounds", "sensitivity_checks"):
            if u6_plan.get(field) != []:
                _add_issue(
                    check,
                    code="U7_MUST_REFERENCE_FROZEN_U6",
                    path=f"u6_plan.{field}",
                    message="U7 must reference U6 digests instead of restating its plan.",
                )
        if u6_plan.get("maximum_calibration_attempts") is not None:
            _add_issue(
                check,
                code="U7_MUST_REFERENCE_FROZEN_U6",
                path="u6_plan.maximum_calibration_attempts",
                message="U7 must reference U6 digests instead of restating its plan.",
            )


def _check_sealed(document: Mapping[str, Any], check: dict[str, Any]) -> None:
    registration_id = document.get("registration_id")
    if not isinstance(registration_id, str) or not registration_id:
        _add_issue(
            check,
            code="MISSING_REGISTRATION_ID",
            path="registration_id",
            message="Sealed registration requires a non-empty registration_id.",
        )
    version = document.get("registration_version")
    if not isinstance(version, str) or _SEMVER.fullmatch(version) is None or version == "0.0.0":
        _add_issue(
            check,
            code="INVALID_REGISTRATION_VERSION",
            path="registration_version",
            message="Sealed registration requires a non-zero semantic version.",
        )
    if not _is_timezone_datetime(document.get("registered_at")):
        _add_issue(
            check,
            code="INVALID_REGISTRATION_TIMESTAMP",
            path="registered_at",
            message="registered_at must be an explicit timezone-aware ISO timestamp.",
        )
    digest = document.get("registration_digest")
    if not _is_digest(digest):
        _add_issue(
            check,
            code="MISSING_REGISTRATION_DIGEST",
            path="registration_digest",
            message="Sealed registration requires its computed SHA-256 digest.",
        )
    else:
        try:
            expected = calculate_validation_registration_digest(document)
        except (TypeError, ValueError):
            expected = None
        if expected is None or digest != expected:
            _add_issue(
                check,
                code="REGISTRATION_DIGEST_MISMATCH",
                path="registration_digest",
                message="Registration content changed after the digest was computed.",
            )

    stage = document.get("registration_stage")
    _check_freezes(document, check)
    _check_prerequisites(document, check)
    _check_inactive_stage_plan(document, check)
    if stage == "u6_calibration":
        _check_u6_plan(document, check)
    elif stage == "u7_holdout":
        _check_u7_plan(document, check)


def build_validation_preregistration_report(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Return deterministic pre-result semantic checks without reading any data."""

    if not isinstance(document, Mapping):
        raise TypeError("document must be an object")
    checks = {
        name: _new_check(name)
        for name in (
            "common_contract",
            "pre_result_access",
            "registration_state",
        )
    }
    _check_common(document, checks["common_contract"])
    _check_pre_result_access(document, checks["pre_result_access"])

    status = document.get("registration_status")
    if status == "template_only":
        _check_template(document, checks["registration_state"])
    elif status == "sealed_pre_results":
        _check_sealed(document, checks["registration_state"])
    else:
        _add_issue(
            checks["registration_state"],
            code="INVALID_REGISTRATION_STATUS",
            path="registration_status",
            message="registration_status must be template_only or sealed_pre_results.",
        )

    check_list = list(checks.values())
    issues = [issue for check in check_list for issue in check["issues"]]
    error_count = len(issues)
    return {
        "schema_version": "1.0.0",
        "validator": {"name": VALIDATOR_NAME, "version": VALIDATOR_VERSION},
        "registration_id": str(document.get("registration_id") or "unknown"),
        "registration_status": str(status or "unknown"),
        "registration_stage": str(document.get("registration_stage") or "unknown"),
        "registration_digest": document.get("registration_digest"),
        "summary": {
            "status": "fail" if error_count else "pass",
            "check_count": len(check_list),
            "error_count": error_count,
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
        "synthetic": document.get("synthetic") is True,
    }


def validate_validation_preregistration_semantics(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate pre-result semantics after JSON Schema validation."""

    report = build_validation_preregistration_report(document)
    if report["summary"]["status"] == "fail":
        raise ValidationPreregistrationError(report)
    return report


def seal_validation_preregistration(document: Mapping[str, Any]) -> dict[str, Any]:
    """Compute a one-way registration digest for a complete pre-result document."""

    if not isinstance(document, Mapping):
        raise TypeError("document must be an object")
    candidate = copy.deepcopy(dict(document))
    if candidate.get("registration_status") != "sealed_pre_results":
        raise ValueError("Only sealed_pre_results documents can be sealed")
    if candidate.get("registration_digest") is not None:
        raise ValueError("registration_digest must be null before sealing")
    candidate["registration_digest"] = calculate_validation_registration_digest(candidate)
    validate_validation_preregistration_semantics(candidate)
    return candidate
