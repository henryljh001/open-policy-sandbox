"""Deterministic semantic validation for aggregate dataset contracts."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from datetime import date
from typing import Any

from policy_sandbox.adapters.base import (
    AggregateDataAdapter,
    AggregateDataAdapterDescriptor,
)
from policy_sandbox.adapters.contracts import canonical_digest
from policy_sandbox.adapters.registry import AGGREGATE_ADAPTER_REGISTRY

VALIDATOR_NAME = "aggregate_dataset_v2_semantic"
VALIDATOR_VERSION = "0.1.0"
_SEMVER = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

INDICATOR_QUALITY_RULES: dict[str, dict[str, Any]] = {
    "total_population": {
        "unit": "person",
        "minimum": 0.0,
        "maximum": None,
        "real_data_eligibility": "conditional",
    },
    "urbanization_rate": {
        "unit": "percent",
        "minimum": 0.0,
        "maximum": 100.0,
        "real_data_eligibility": "conditional",
    },
    "employment_rate": {
        "unit": "percent",
        "minimum": 0.0,
        "maximum": 100.0,
        "real_data_eligibility": "conditional",
    },
    "debt_to_revenue": {
        "unit": "percent",
        "minimum": 0.0,
        "maximum": None,
        "real_data_eligibility": "conditional",
    },
    "education_capacity_per_1000": {
        "unit": "capacity_per_1000_persons",
        "minimum": 0.0,
        "maximum": None,
        "real_data_eligibility": "conditional",
    },
    "health_capacity_per_1000": {
        "unit": "capacity_per_1000_persons",
        "minimum": 0.0,
        "maximum": None,
        "real_data_eligibility": "conditional",
    },
    "housing_occupancy_rate": {
        "unit": "percent",
        "minimum": 0.0,
        "maximum": 100.0,
        "real_data_eligibility": "conditional",
    },
    "used_construction_land": {
        "unit": "synthetic_area_unit",
        "minimum": 0.0,
        "maximum": None,
        "real_data_eligibility": "blocked",
    },
}


class AggregateDataQualityError(ValueError):
    """Raised when a v2 dataset fails semantic validation."""

    def __init__(self, report: Mapping[str, Any]) -> None:
        self.report = dict(report)
        errors = report.get("summary", {}).get("error_count", "unknown")
        super().__init__(f"Aggregate dataset v2 semantic validation failed: {errors} errors")


def _new_check(check_id: str) -> dict[str, Any]:
    return {"check_id": check_id, "status": "pass", "issues": []}


def _add_issue(
    check: dict[str, Any],
    *,
    code: str,
    severity: str,
    path: str,
    message: str,
) -> None:
    check["issues"].append(
        {
            "code": code,
            "severity": severity,
            "path": path,
            "message": message,
        }
    )


def _finish_check(check: dict[str, Any]) -> None:
    severities = {issue["severity"] for issue in check["issues"]}
    if "error" in severities:
        check["status"] = "fail"
    elif "warning" in severities:
        check["status"] = "warning"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _objects(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _stable_unique(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _duplicates(values: list[Any]) -> list[str]:
    seen: set[Any] = set()
    duplicate: set[str] = set()
    for value in values:
        if value in seen:
            duplicate.add(str(value))
        seen.add(value)
    return sorted(duplicate)


def _safe_digest(value: Any) -> str | None:
    try:
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return canonical_digest(value)
    except (TypeError, ValueError):
        return None


def _parse_evaluation_date(value: str) -> date:
    if not isinstance(value, str):
        raise TypeError("evaluation_date must be an ISO date string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("evaluation_date must use YYYY-MM-DD") from exc


def build_aggregate_data_quality_report(
    dataset: Mapping[str, Any],
    *,
    evaluation_date: str,
) -> dict[str, Any]:
    """Return a deterministic report without reading files or external services."""

    if not isinstance(dataset, Mapping):
        raise TypeError("dataset must be an object")
    evaluated_on = _parse_evaluation_date(evaluation_date)
    checks = {
        name: _new_check(name)
        for name in (
            "root_contract",
            "state_consistency",
            "dataset_identity",
            "identifier_uniqueness",
            "provenance_references",
            "transformation_topology",
            "coverage_consistency",
            "indicator_values",
            "authorization_and_release",
            "real_data_eligibility",
        )
    }

    root_check = checks["root_contract"]
    schema_version = dataset.get("schema_version")
    if schema_version != "2.0.0":
        _add_issue(
            root_check,
            code="UNSUPPORTED_SCHEMA_VERSION",
            severity="error",
            path="schema_version",
            message="Semantic validation requires aggregate dataset schema 2.0.0.",
        )
    dataset_id_value = dataset.get("dataset_id")
    if not isinstance(dataset_id_value, str) or not dataset_id_value:
        _add_issue(
            root_check,
            code="INVALID_DATASET_ID",
            severity="error",
            path="dataset_id",
            message="dataset_id must be a non-empty string.",
        )
    root_synthetic_value = dataset.get("synthetic")
    if not isinstance(root_synthetic_value, bool):
        _add_issue(
            root_check,
            code="INVALID_SYNTHETIC_FLAG",
            severity="error",
            path="synthetic",
            message="synthetic must be boolean.",
        )
    publication_class = dataset.get("publication_class")
    if publication_class not in {
        "public_synthetic",
        "private_restricted",
        "public_aggregate",
    }:
        _add_issue(
            root_check,
            code="INVALID_PUBLICATION_CLASS",
            severity="error",
            path="publication_class",
            message="publication_class is not recognized.",
        )
    digest = _safe_digest(dataset)
    if digest is None:
        _add_issue(
            root_check,
            code="NON_JSON_DATASET",
            severity="error",
            path="$",
            message="Dataset must contain only JSON-serializable values.",
        )

    card = _mapping(dataset.get("data_card"))
    manifest = _mapping(dataset.get("source_manifest"))
    ledger = _mapping(dataset.get("transformation_ledger"))
    records_value = dataset.get("records")
    records = _objects(records_value)
    sources_value = manifest.get("sources")
    sources = _objects(sources_value)
    steps_value = ledger.get("steps")
    steps = _objects(steps_value)
    for value, path in (
        (dataset.get("data_card"), "data_card"),
        (dataset.get("source_manifest"), "source_manifest"),
        (dataset.get("transformation_ledger"), "transformation_ledger"),
    ):
        if not isinstance(value, Mapping):
            _add_issue(
                root_check,
                code="EXPECTED_OBJECT",
                severity="error",
                path=path,
                message=f"{path} must be an object.",
            )
    for value, path in (
        (records_value, "records"),
        (sources_value, "source_manifest.sources"),
        (steps_value, "transformation_ledger.steps"),
    ):
        if not isinstance(value, list) or not value:
            _add_issue(
                root_check,
                code="EXPECTED_NON_EMPTY_ARRAY",
                severity="error",
                path=path,
                message=f"{path} must be a non-empty array.",
            )
        elif len(_objects(value)) != len(value):
            _add_issue(
                root_check,
                code="EXPECTED_OBJECT_ITEMS",
                severity="error",
                path=path,
                message=f"Every item in {path} must be an object.",
            )

    synthetic = root_synthetic_value is True
    state_check = checks["state_consistency"]
    nested_flags: list[tuple[str, Any]] = [
        ("data_card.synthetic", card.get("synthetic")),
        ("source_manifest.synthetic", manifest.get("synthetic")),
        ("transformation_ledger.synthetic", ledger.get("synthetic")),
    ]
    nested_flags.extend(
        (f"source_manifest.sources[{index}].synthetic", item.get("synthetic"))
        for index, item in enumerate(sources)
    )
    nested_flags.extend(
        (f"transformation_ledger.steps[{index}].synthetic", item.get("synthetic"))
        for index, item in enumerate(steps)
    )
    nested_flags.extend(
        (f"records[{index}].synthetic", item.get("synthetic"))
        for index, item in enumerate(records)
    )
    for path, value in nested_flags:
        if value is not root_synthetic_value:
            _add_issue(
                state_check,
                code="SYNTHETIC_STATE_MISMATCH",
                severity="error",
                path=path,
                message="Nested synthetic state must equal the root state.",
            )
    expected_statuses = (
        {"synthetic_observation"}
        if synthetic
        else {"official_observation", "provisional_observation", "revised_observation"}
    )
    for index, record in enumerate(records):
        if record.get("status") not in expected_statuses:
            _add_issue(
                state_check,
                code="OBSERVATION_STATE_MISMATCH",
                severity="error",
                path=f"records[{index}].status",
                message="Observation status conflicts with the root synthetic state.",
            )
    expected_publication = "public_synthetic" if synthetic else None
    if expected_publication and publication_class != expected_publication:
        _add_issue(
            state_check,
            code="PUBLICATION_STATE_MISMATCH",
            severity="error",
            path="publication_class",
            message="Synthetic datasets must use public_synthetic.",
        )
    if not synthetic and publication_class == "public_synthetic":
        _add_issue(
            state_check,
            code="PUBLICATION_STATE_MISMATCH",
            severity="error",
            path="publication_class",
            message="Real datasets cannot use public_synthetic.",
        )

    identity_check = checks["dataset_identity"]
    for path, nested_id in (
        ("source_manifest.dataset_id", manifest.get("dataset_id")),
        ("transformation_ledger.dataset_id", ledger.get("dataset_id")),
    ):
        if nested_id != dataset_id_value:
            _add_issue(
                identity_check,
                code="DATASET_ID_MISMATCH",
                severity="error",
                path=path,
                message="Nested dataset_id must equal the root dataset_id.",
            )

    unique_check = checks["identifier_uniqueness"]
    identifier_groups = (
        ("source_id", [item.get("source_id") for item in sources]),
        ("step_id", [item.get("step_id") for item in steps]),
        ("record_id", [item.get("record_id") for item in records]),
    )
    for field, values in identifier_groups:
        invalid = [value for value in values if not isinstance(value, str) or not value]
        if invalid:
            _add_issue(
                unique_check,
                code="INVALID_IDENTIFIER",
                severity="error",
                path=field,
                message=f"Every {field} must be a non-empty string.",
            )
        duplicate = _duplicates(
            [value for value in values if isinstance(value, str) and value]
        )
        if duplicate:
            _add_issue(
                unique_check,
                code="DUPLICATE_IDENTIFIER",
                severity="error",
                path=field,
                message=f"Duplicate {field} values are not allowed.",
            )
    indicator_year_pairs = [
        (item.get("indicator_id"), item.get("reference_year"))
        for item in records
        if isinstance(item.get("indicator_id"), str)
        and isinstance(item.get("reference_year"), int)
        and not isinstance(item.get("reference_year"), bool)
    ]
    duplicate_pairs = _duplicates(indicator_year_pairs)
    if duplicate_pairs:
        _add_issue(
            unique_check,
            code="DUPLICATE_INDICATOR_YEAR",
            severity="error",
            path="records",
            message="Each indicator_id and reference_year pair must be unique.",
        )

    source_ids = {
        item.get("source_id")
        for item in sources
        if isinstance(item.get("source_id"), str) and item.get("source_id")
    }
    step_by_id = {
        item.get("step_id"): item
        for item in steps
        if isinstance(item.get("step_id"), str) and item.get("step_id")
    }
    provenance_check = checks["provenance_references"]
    for index, record in enumerate(records):
        if record.get("source_id") not in source_ids:
            _add_issue(
                provenance_check,
                code="DANGLING_SOURCE_REFERENCE",
                severity="error",
                path=f"records[{index}].source_id",
                message="Record source_id does not exist in the source manifest.",
            )
        transformation_refs = record.get("transformation_step_ids")
        if not isinstance(transformation_refs, list) or not transformation_refs:
            _add_issue(
                provenance_check,
                code="INVALID_TRANSFORMATION_REFERENCES",
                severity="error",
                path=f"records[{index}].transformation_step_ids",
                message="Record must reference at least one transformation step.",
            )
            continue
        for step_id in transformation_refs:
            if not isinstance(step_id, str) or not step_id:
                _add_issue(
                    provenance_check,
                    code="INVALID_TRANSFORMATION_REFERENCE",
                    severity="error",
                    path=f"records[{index}].transformation_step_ids",
                    message="Transformation references must be non-empty strings.",
                )
                continue
            step = step_by_id.get(step_id)
            if step is None:
                _add_issue(
                    provenance_check,
                    code="DANGLING_TRANSFORMATION_REFERENCE",
                    severity="error",
                    path=f"records[{index}].transformation_step_ids",
                    message="Record references an absent transformation step.",
                )
                continue
            output_fields = step.get("output_fields")
            if not isinstance(output_fields, list) or record.get(
                "indicator_id"
            ) not in output_fields:
                _add_issue(
                    provenance_check,
                    code="TRANSFORMATION_OUTPUT_MISMATCH",
                    severity="error",
                    path=f"records[{index}].transformation_step_ids",
                    message="Referenced transformation does not declare the record indicator.",
                )

    topology_check = checks["transformation_topology"]
    available_refs = set(source_ids)
    for index, step in enumerate(steps):
        input_refs = step.get("input_refs")
        if not isinstance(input_refs, list) or not input_refs:
            _add_issue(
                topology_check,
                code="INVALID_STEP_INPUTS",
                severity="error",
                path=f"transformation_ledger.steps[{index}].input_refs",
                message="Transformation step must declare at least one input reference.",
            )
        else:
            for input_ref in input_refs:
                if not isinstance(input_ref, str) or not input_ref:
                    _add_issue(
                        topology_check,
                        code="INVALID_STEP_INPUT_REFERENCE",
                        severity="error",
                        path=f"transformation_ledger.steps[{index}].input_refs",
                        message="Step input references must be non-empty strings.",
                    )
                    continue
                if input_ref not in available_refs:
                    _add_issue(
                        topology_check,
                        code="NON_TOPOLOGICAL_STEP_REFERENCE",
                        severity="error",
                        path=f"transformation_ledger.steps[{index}].input_refs",
                        message="Step input must reference a source or an earlier step.",
                    )
        step_id = step.get("step_id")
        if isinstance(step_id, str) and step_id:
            available_refs.add(step_id)

    coverage_check = checks["coverage_consistency"]
    coverage = _mapping(card.get("coverage"))
    actual_years = sorted(
        {
            value
            for value in (record.get("reference_year") for record in records)
            if isinstance(value, int) and not isinstance(value, bool)
        }
    )
    declared_years = coverage.get("reference_years")
    if declared_years != actual_years:
        _add_issue(
            coverage_check,
            code="REFERENCE_YEAR_COVERAGE_MISMATCH",
            severity="error",
            path="data_card.coverage.reference_years",
            message="Declared reference years must exactly match record years.",
        )
    actual_indicators = _stable_unique(
        [record.get("indicator_id") for record in records]
    )
    declared_indicators = coverage.get("indicator_ids")
    if declared_indicators != actual_indicators:
        _add_issue(
            coverage_check,
            code="INDICATOR_COVERAGE_MISMATCH",
            severity="error",
            path="data_card.coverage.indicator_ids",
            message="Declared indicators must match record indicators in stable order.",
        )

    value_check = checks["indicator_values"]
    for index, record in enumerate(records):
        indicator = record.get("indicator_id")
        rule = INDICATOR_QUALITY_RULES.get(str(indicator))
        if rule is None:
            _add_issue(
                value_check,
                code="UNKNOWN_INDICATOR",
                severity="error",
                path=f"records[{index}].indicator_id",
                message="Indicator is not in the v2 admission catalog.",
            )
            continue
        if record.get("unit") != rule["unit"]:
            _add_issue(
                value_check,
                code="UNIT_MISMATCH",
                severity="error",
                path=f"records[{index}].unit",
                message=f"Indicator requires unit {rule['unit']}.",
            )
        year = record.get("reference_year")
        if isinstance(year, bool) or not isinstance(year, int) or not 2000 <= year <= 2100:
            _add_issue(
                value_check,
                code="INVALID_REFERENCE_YEAR",
                severity="error",
                path=f"records[{index}].reference_year",
                message="reference_year must be an integer between 2000 and 2100.",
            )
        value = record.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _add_issue(
                value_check,
                code="NON_NUMERIC_VALUE",
                severity="error",
                path=f"records[{index}].value",
                message="Indicator value must be numeric.",
            )
            continue
        numeric = float(value)
        if not math.isfinite(numeric):
            _add_issue(
                value_check,
                code="NON_FINITE_VALUE",
                severity="error",
                path=f"records[{index}].value",
                message="Indicator value must be finite.",
            )
            continue
        minimum = rule["minimum"]
        maximum = rule["maximum"]
        if minimum is not None and numeric < minimum:
            _add_issue(
                value_check,
                code="VALUE_BELOW_MINIMUM",
                severity="error",
                path=f"records[{index}].value",
                message=f"Indicator value must be at least {minimum}.",
            )
        if maximum is not None and numeric > maximum:
            _add_issue(
                value_check,
                code="VALUE_ABOVE_MAXIMUM",
                severity="error",
                path=f"records[{index}].value",
                message=f"Indicator value must be at most {maximum}.",
            )

    authorization_check = checks["authorization_and_release"]
    authorization = _mapping(card.get("authorization"))
    license_info = _mapping(card.get("license"))
    if synthetic:
        expected = (
            ("data_card.authorization.status", authorization.get("status"), "synthetic_fixture"),
            (
                "data_card.authorization.public_outputs",
                authorization.get("public_outputs"),
                "synthetic_only",
            ),
            (
                "data_card.license.redistribution",
                license_info.get("redistribution"),
                "synthetic_fixture",
            ),
        )
        for path, actual, required in expected:
            if actual != required:
                _add_issue(
                    authorization_check,
                    code="SYNTHETIC_AUTHORIZATION_MISMATCH",
                    severity="error",
                    path=path,
                    message=f"Synthetic dataset requires {required}.",
                )
    else:
        if authorization.get("status") != "authorized":
            _add_issue(
                authorization_check,
                code="REAL_DATA_NOT_AUTHORIZED",
                severity="error",
                path="data_card.authorization.status",
                message="Real dataset requires explicit authorized status.",
            )
        expires_on = authorization.get("expires_on")
        if expires_on is not None:
            try:
                expiry = date.fromisoformat(str(expires_on))
            except ValueError:
                _add_issue(
                    authorization_check,
                    code="INVALID_AUTHORIZATION_EXPIRY",
                    severity="error",
                    path="data_card.authorization.expires_on",
                    message="Authorization expiry must use YYYY-MM-DD.",
                )
            else:
                if expiry < evaluated_on:
                    _add_issue(
                        authorization_check,
                        code="AUTHORIZATION_EXPIRED",
                        severity="error",
                        path="data_card.authorization.expires_on",
                        message="Authorization expired before the evaluation date.",
                    )
        if publication_class == "public_aggregate":
            if authorization.get("public_outputs") not in {
                "aggregate_only",
                "approved_fields",
            }:
                _add_issue(
                    authorization_check,
                    code="PUBLIC_OUTPUT_NOT_AUTHORIZED",
                    severity="error",
                    path="data_card.authorization.public_outputs",
                    message="Public aggregate output is not authorized.",
                )
            if license_info.get("redistribution") not in {
                "aggregate_only",
                "permitted",
            }:
                _add_issue(
                    authorization_check,
                    code="PUBLIC_REDISTRIBUTION_PROHIBITED",
                    severity="error",
                    path="data_card.license.redistribution",
                    message="License does not permit public aggregate redistribution.",
                )

    eligibility_check = checks["real_data_eligibility"]
    blocked_indicators: list[str] = []
    conditional_indicators: list[str] = []
    if not synthetic:
        for indicator in actual_indicators:
            rule = INDICATOR_QUALITY_RULES.get(str(indicator))
            if rule is None:
                continue
            if rule["real_data_eligibility"] == "blocked":
                blocked_indicators.append(str(indicator))
            else:
                conditional_indicators.append(str(indicator))
        if blocked_indicators:
            _add_issue(
                eligibility_check,
                code="REAL_INDICATOR_BLOCKED",
                severity="error",
                path="records",
                message=(
                    "Blocked real-data indicators: " + ", ".join(blocked_indicators) + "."
                ),
            )
        if conditional_indicators:
            _add_issue(
                eligibility_check,
                code="REAL_CALIBER_REVIEW_REQUIRED",
                severity="warning",
                path="data_card.geography.caliber",
                message="Conditional indicators require documented human caliber review.",
            )

    for check in checks.values():
        _finish_check(check)
    check_list = list(checks.values())
    all_issues = [issue for check in check_list for issue in check["issues"]]
    error_count = sum(issue["severity"] == "error" for issue in all_issues)
    warning_count = sum(issue["severity"] == "warning" for issue in all_issues)
    status = "fail" if error_count else "pass_with_warnings" if warning_count else "pass"
    if synthetic:
        readiness = "not_assessed_synthetic"
    elif blocked_indicators or error_count:
        readiness = "blocked"
    else:
        readiness = "requires_human_review"

    return {
        "schema_version": "1.0.0",
        "report_id": f"quality-{(digest or 'unavailable')[:16]}",
        "validator": {"name": VALIDATOR_NAME, "version": VALIDATOR_VERSION},
        "dataset": {
            "dataset_id": dataset_id_value if isinstance(dataset_id_value, str) else "unknown",
            "dataset_digest": digest,
            "input_schema_version": str(schema_version or "unknown"),
            "publication_class": str(publication_class or "unknown"),
            "evaluation_date": evaluation_date,
            "synthetic": synthetic,
        },
        "summary": {
            "status": status,
            "check_count": len(check_list),
            "error_count": error_count,
            "warning_count": warning_count,
            "record_count": len(records),
            "indicator_count": len(actual_indicators),
            "reference_year_count": len(actual_years),
            "source_count": len(sources),
            "transformation_step_count": len(steps),
        },
        "checks": check_list,
        "real_data_readiness": {
            "status": readiness,
            "blocked_indicators": blocked_indicators,
            "conditional_indicators": conditional_indicators,
            "I5b_status": "not_assessed",
            "U6_status": "not_passed",
        },
        "usage_level": "Demo",
        "synthetic": synthetic,
    }


def validate_aggregate_dataset_v2_semantics(
    dataset: Mapping[str, Any],
    *,
    evaluation_date: str,
) -> dict[str, Any]:
    """Validate cross-object semantics after JSON Schema validation."""

    report = build_aggregate_data_quality_report(
        dataset,
        evaluation_date=evaluation_date,
    )
    if report["summary"]["status"] == "fail":
        raise AggregateDataQualityError(report)
    return report


def build_adapter_conformance_report() -> dict[str, Any]:
    """Check registered adapter descriptors without instantiating private readers."""

    adapters: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for registry_name, adapter_class in sorted(AGGREGATE_ADAPTER_REGISTRY.items()):
        descriptor = getattr(adapter_class, "descriptor", None)
        entry = {
            "registry_name": registry_name,
            "class_name": getattr(adapter_class, "__name__", type(adapter_class).__name__),
            "status": "pass",
        }
        adapter_issues: list[dict[str, str]] = []
        is_adapter_class = isinstance(adapter_class, type) and issubclass(
            adapter_class,
            AggregateDataAdapter,
        )
        if not is_adapter_class:
            adapter_issues.append(
                {
                    "code": "INVALID_ADAPTER_CLASS",
                    "message": "Registered class must inherit AggregateDataAdapter.",
                }
            )
        if not isinstance(descriptor, AggregateDataAdapterDescriptor):
            adapter_issues.append(
                {
                    "code": "MISSING_ADAPTER_DESCRIPTOR",
                    "message": "Adapter must expose AggregateDataAdapterDescriptor.",
                }
            )
        else:
            if descriptor.name != registry_name:
                adapter_issues.append(
                    {
                        "code": "ADAPTER_NAME_MISMATCH",
                        "message": "Descriptor name must equal the registry name.",
                    }
                )
            if not _SEMVER.fullmatch(descriptor.version):
                adapter_issues.append(
                    {
                        "code": "INVALID_ADAPTER_VERSION",
                        "message": "Adapter version must use MAJOR.MINOR.PATCH.",
                    }
                )
            if not descriptor.domain or descriptor.domain.startswith("_"):
                adapter_issues.append(
                    {
                        "code": "INVALID_ADAPTER_DOMAIN",
                        "message": "Adapter domain must be public and non-empty.",
                    }
                )
            versions = descriptor.accepted_schema_versions
            if (
                not isinstance(versions, tuple)
                or not versions
                or len(set(versions)) != len(versions)
            ):
                adapter_issues.append(
                    {
                        "code": "INVALID_ACCEPTED_SCHEMA_VERSIONS",
                        "message": "Accepted schema versions must be non-empty and unique.",
                    }
                )
            elif any(not _SEMVER.fullmatch(version) for version in versions):
                adapter_issues.append(
                    {
                        "code": "INVALID_ACCEPTED_SCHEMA_VERSION",
                        "message": "Accepted schema versions must use MAJOR.MINOR.PATCH.",
                    }
                )
            if not isinstance(descriptor.accepts_real_data, bool):
                adapter_issues.append(
                    {
                        "code": "INVALID_REAL_DATA_CAPABILITY",
                        "message": "accepts_real_data must be boolean.",
                    }
                )
        if adapter_issues:
            entry["status"] = "fail"
        entry["issues"] = adapter_issues
        adapters.append(entry)
        issues.extend(
            {
                "adapter": registry_name,
                "code": issue["code"],
                "message": issue["message"],
            }
            for issue in adapter_issues
        )
    return {
        "schema_version": "1.0.0",
        "status": "fail" if issues else "pass",
        "adapter_count": len(adapters),
        "registry_digest": canonical_digest(adapters),
        "adapters": adapters,
        "issues": issues,
        "real_adapter_count": sum(
            bool(getattr(getattr(item, "descriptor", None), "accepts_real_data", False))
            for item in AGGREGATE_ADAPTER_REGISTRY.values()
        ),
        "usage_level": "Demo",
    }
