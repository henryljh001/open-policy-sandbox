"""Versioned aggregate-dataset contracts and deterministic migrations."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any

V1_INDICATOR_UNITS = {
    "total_population": "person",
    "urbanization_rate": "percent",
    "employment_rate": "percent",
    "debt_to_revenue": "percent",
    "education_capacity_per_1000": "capacity_per_1000_persons",
    "health_capacity_per_1000": "capacity_per_1000_persons",
    "housing_occupancy_rate": "percent",
    "used_construction_land": "synthetic_area_unit",
}


def canonical_digest(value: Any) -> str:
    """Return the stable SHA-256 used by public adapter contracts."""

    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be an object")
    return value


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _exact_fields(value: Mapping[str, Any], expected: set[str], field: str) -> None:
    unknown = sorted(str(item) for item in set(value) - expected)
    missing = sorted(expected - set(value))
    if unknown:
        raise ValueError(f"Unknown {field} fields: {', '.join(unknown)}")
    if missing:
        raise ValueError(f"Missing {field} fields: {', '.join(missing)}")


def migrate_aggregate_dataset_v1_to_v2(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate the released synthetic v1 contract without inventing real-data facts."""

    source = _mapping(dataset, "dataset")
    _exact_fields(
        source,
        {"schema_version", "dataset_id", "data_card", "records", "synthetic"},
        "dataset",
    )
    if source.get("schema_version") != "1.0.0":
        raise ValueError("Only aggregate dataset schema_version 1.0.0 can be migrated")
    if source.get("synthetic") is not True:
        raise ValueError("The v1 migration only accepts synthetic=true datasets")

    dataset_id = _non_empty_string(source.get("dataset_id"), "dataset_id")
    card = _mapping(source.get("data_card"), "data_card")
    _exact_fields(
        card,
        {
            "schema_version",
            "title",
            "publisher",
            "source_kind",
            "authorization",
            "license",
            "geography",
            "coverage",
            "transformations",
            "limitations",
            "synthetic",
        },
        "data_card",
    )
    if card.get("schema_version") != "1.0.0" or card.get("synthetic") is not True:
        raise ValueError("v1 data_card must use schema_version 1.0.0 and synthetic=true")
    if card.get("source_kind") != "synthetic_fixture":
        raise ValueError("v1 migration requires source_kind=synthetic_fixture")
    if card.get("authorization") != "synthetic_fixture":
        raise ValueError("v1 migration requires authorization=synthetic_fixture")

    title = _non_empty_string(card.get("title"), "data_card.title")
    publisher = _non_empty_string(card.get("publisher"), "data_card.publisher")
    license_id = _non_empty_string(card.get("license"), "data_card.license")
    geography = _mapping(card.get("geography"), "data_card.geography")
    _exact_fields(geography, {"level", "region_id"}, "data_card.geography")
    if geography.get("level") != "synthetic_county":
        raise ValueError("v1 migration requires geography.level=synthetic_county")
    region_id = _non_empty_string(geography.get("region_id"), "geography.region_id")

    coverage = _mapping(card.get("coverage"), "data_card.coverage")
    _exact_fields(coverage, {"reference_year", "indicator_ids"}, "data_card.coverage")
    reference_year = coverage.get("reference_year")
    if isinstance(reference_year, bool) or not isinstance(reference_year, int):
        raise TypeError("data_card.coverage.reference_year must be an integer")
    if not 2000 <= reference_year <= 2100:
        raise ValueError("data_card.coverage.reference_year must be between 2000 and 2100")
    indicator_ids = coverage.get("indicator_ids")
    if not isinstance(indicator_ids, list) or not indicator_ids:
        raise ValueError("data_card.coverage.indicator_ids must be a non-empty array")
    if any(not isinstance(item, str) or not item for item in indicator_ids):
        raise ValueError("indicator_ids must contain non-empty strings")
    if len(set(indicator_ids)) != len(indicator_ids):
        raise ValueError("indicator_ids must be unique")

    transformations = card.get("transformations")
    limitations = card.get("limitations")
    if not isinstance(transformations, list) or any(
        not isinstance(item, str) for item in transformations
    ):
        raise TypeError("data_card.transformations must be an array of strings")
    if not isinstance(limitations, list) or not limitations or any(
        not isinstance(item, str) or not item for item in limitations
    ):
        raise ValueError("data_card.limitations must be a non-empty array of strings")

    records = source.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a non-empty array")
    source_id = f"source-{canonical_digest(source)[:16]}"
    step_id = "migrate-v1-to-v2"
    migrated_records: list[dict[str, Any]] = []
    observed_indicators: list[str] = []
    observed_record_ids: set[str] = set()
    for index, raw_record in enumerate(records):
        record = _mapping(raw_record, f"records[{index}]")
        _exact_fields(
            record,
            {
                "record_id",
                "indicator_id",
                "value",
                "unit",
                "reference_year",
                "status",
                "synthetic",
            },
            f"records[{index}]",
        )
        if record.get("synthetic") is not True:
            raise ValueError(f"records[{index}] must set synthetic=true")
        if record.get("status") != "synthetic_observation":
            raise ValueError(f"records[{index}] must use synthetic_observation")
        if record.get("reference_year") != reference_year:
            raise ValueError(f"records[{index}] reference_year conflicts with data_card")
        indicator_id = _non_empty_string(
            record.get("indicator_id"), f"records[{index}].indicator_id"
        )
        if indicator_id not in V1_INDICATOR_UNITS:
            raise ValueError(f"Unsupported v1 indicator_id: {indicator_id}")
        unit = _non_empty_string(record.get("unit"), f"records[{index}].unit")
        if unit != V1_INDICATOR_UNITS[indicator_id]:
            raise ValueError(
                f"Unit mismatch for {indicator_id}: expected {V1_INDICATOR_UNITS[indicator_id]}"
            )
        value = record.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"records[{index}].value must be numeric")
        if not math.isfinite(float(value)):
            raise ValueError(f"records[{index}].value must be finite")
        record_id = _non_empty_string(
            record.get("record_id"), f"records[{index}].record_id"
        )
        if record_id in observed_record_ids:
            raise ValueError(f"Duplicate record_id: {record_id}")
        observed_record_ids.add(record_id)
        observed_indicators.append(indicator_id)
        migrated_records.append(
            {
                "record_id": record_id,
                "indicator_id": indicator_id,
                "value": value,
                "unit": unit,
                "reference_year": reference_year,
                "status": "synthetic_observation",
                "source_id": source_id,
                "transformation_step_ids": [step_id],
                "synthetic": True,
            }
        )
    if observed_indicators != indicator_ids:
        raise ValueError("record indicator order must match data_card.coverage.indicator_ids")

    return {
        "schema_version": "2.0.0",
        "dataset_id": dataset_id,
        "publication_class": "public_synthetic",
        "data_card": {
            "schema_version": "2.0.0",
            "title": title,
            "publisher": publisher,
            "source_kind": "synthetic_fixture",
            "authorization": {
                "status": "synthetic_fixture",
                "responsible_party": publisher,
                "allowed_purposes": ["software_testing", "synthetic_demonstration"],
                "expires_on": None,
                "public_outputs": "synthetic_only",
            },
            "license": {
                "identifier": license_id,
                "terms_uri": None,
                "redistribution": "synthetic_fixture",
            },
            "geography": {
                "level": "synthetic_county",
                "region_id": region_id,
                "boundary_version": "synthetic-v1-unspecified",
                "caliber": "synthetic_county_aggregate_v1",
            },
            "coverage": {
                "reference_years": [reference_year],
                "indicator_ids": list(indicator_ids),
            },
            "limitations": list(limitations)
            + ["Migrated from synthetic v1; no real authorization facts were inferred"],
            "synthetic": True,
        },
        "source_manifest": {
            "schema_version": "1.0.0",
            "manifest_id": f"{dataset_id}-sources-v2",
            "dataset_id": dataset_id,
            "sources": [
                {
                    "source_id": source_id,
                    "title": title,
                    "publisher": publisher,
                    "locator": {"kind": "embedded_fixture", "value": dataset_id},
                    "content_sha256": canonical_digest(source),
                    "license_id": license_id,
                    "acquired_on": None,
                    "synthetic": True,
                }
            ],
            "synthetic": True,
        },
        "transformation_ledger": {
            "schema_version": "1.0.0",
            "ledger_id": f"{dataset_id}-transformations-v2",
            "dataset_id": dataset_id,
            "steps": [
                {
                    "step_id": step_id,
                    "operation": "identity",
                    "input_refs": [source_id],
                    "output_fields": list(indicator_ids),
                    "parameters": {
                        "source_schema_version": "1.0.0",
                        "target_schema_version": "2.0.0",
                        "value_change": "none",
                        "legacy_transformations": list(transformations),
                    },
                    "implementation": (
                        "policy_sandbox.adapters.contracts:"
                        "migrate_aggregate_dataset_v1_to_v2"
                    ),
                    "implementation_version": "1.0.0",
                    "synthetic": True,
                }
            ],
            "synthetic": True,
        },
        "records": migrated_records,
        "synthetic": True,
    }
