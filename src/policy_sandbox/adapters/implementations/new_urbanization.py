"""Synthetic aggregate fixture adapter for the new-urbanization domain."""

import hashlib
import json
import math
from typing import Any, Mapping

from policy_sandbox.adapters.base import (
    AggregateDataAdapter,
    AggregateDataAdapterDescriptor,
)
from policy_sandbox.adapters.registry import register_aggregate_adapter


INDICATOR_CATALOG: dict[str, dict[str, Any]] = {
    "total_population": {
        "outcome": "final_total_population",
        "unit": "person",
        "mode": "relative",
        "tolerance": 0.02,
    },
    "urbanization_rate": {
        "outcome": "final_urbanization_rate",
        "unit": "percent",
        "mode": "absolute",
        "tolerance": 1.0,
    },
    "employment_rate": {
        "outcome": "final_employment_rate",
        "unit": "percent",
        "mode": "absolute",
        "tolerance": 1.0,
    },
    "debt_to_revenue": {
        "outcome": "final_debt_to_revenue",
        "unit": "percent",
        "mode": "absolute",
        "tolerance": 5.0,
    },
    "education_capacity_per_1000": {
        "outcome": "final_education_capacity_per_1000",
        "unit": "capacity_per_1000_persons",
        "mode": "absolute",
        "tolerance": 2.0,
    },
    "health_capacity_per_1000": {
        "outcome": "final_health_capacity_per_1000",
        "unit": "capacity_per_1000_persons",
        "mode": "absolute",
        "tolerance": 0.5,
    },
    "housing_occupancy_rate": {
        "outcome": "final_housing_occupancy_rate",
        "unit": "percent",
        "mode": "absolute",
        "tolerance": 1.0,
    },
    "used_construction_land": {
        "outcome": "final_used_construction_land",
        "unit": "synthetic_area_unit",
        "mode": "absolute",
        "tolerance": 2.0,
    },
}


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


@register_aggregate_adapter("new_urbanization_synthetic_aggregate_v1")
class NewUrbanizationSyntheticAggregateAdapter(AggregateDataAdapter):
    """Adapt a strict synthetic aggregate fixture; never accepts real records."""

    descriptor = AggregateDataAdapterDescriptor(
        name="new_urbanization_synthetic_aggregate_v1",
        version="0.1.0",
        domain="new_urbanization",
        accepted_schema_versions=("1.0.0",),
        accepts_real_data=False,
    )

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        super().__init__(cfg)
        unknown = sorted(
            set(self.cfg)
            - {"expected_reference_year", "require_complete", "tolerance_overrides"}
        )
        if unknown:
            raise ValueError("Unknown adapter config fields: " + ", ".join(unknown))
        year = self.cfg.get("expected_reference_year")
        if year is not None and (isinstance(year, bool) or not isinstance(year, int)):
            raise TypeError("expected_reference_year must be an integer")
        complete = self.cfg.get("require_complete", True)
        if not isinstance(complete, bool):
            raise TypeError("require_complete must be boolean")
        self.expected_reference_year = year
        self.require_complete = complete
        self.tolerances = self._build_tolerances(
            self.cfg.get("tolerance_overrides", {})
        )

    def _build_tolerances(self, overrides: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(overrides, Mapping):
            raise TypeError("tolerance_overrides must be an object")
        unknown = sorted(set(overrides) - set(INDICATOR_CATALOG))
        if unknown:
            raise ValueError("Unknown tolerance indicators: " + ", ".join(unknown))
        values = {
            indicator: {
                "mode": specification["mode"],
                "tolerance": float(specification["tolerance"]),
            }
            for indicator, specification in INDICATOR_CATALOG.items()
        }
        for indicator, override in overrides.items():
            if not isinstance(override, Mapping):
                raise TypeError(f"tolerance override {indicator} must be an object")
            extra = sorted(set(override) - {"mode", "tolerance"})
            if extra:
                raise ValueError(
                    f"Unknown tolerance fields for {indicator}: {', '.join(extra)}"
                )
            mode = override.get("mode", values[indicator]["mode"])
            if mode not in {"absolute", "relative"}:
                raise ValueError(f"{indicator}.mode must be absolute or relative")
            tolerance = _number(
                override.get("tolerance", values[indicator]["tolerance"]),
                f"{indicator}.tolerance",
            )
            if tolerance < 0:
                raise ValueError(f"{indicator}.tolerance must be non-negative")
            values[indicator] = {"mode": mode, "tolerance": tolerance}
        return values

    def adapt(self, dataset: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and convert one synthetic aggregate dataset."""

        allowed = {"schema_version", "dataset_id", "data_card", "records", "synthetic"}
        unknown = sorted(set(dataset) - allowed)
        if unknown:
            raise ValueError("Unknown aggregate dataset fields: " + ", ".join(unknown))
        if dataset.get("schema_version") not in self.descriptor.accepted_schema_versions:
            raise ValueError("Unsupported aggregate dataset schema_version")
        if dataset.get("synthetic") is not True:
            raise ValueError("Synthetic aggregate adapter requires synthetic=true")
        dataset_id = dataset.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id:
            raise ValueError("dataset_id must be non-empty")
        data_card = dataset.get("data_card")
        if not isinstance(data_card, Mapping) or data_card.get("synthetic") is not True:
            raise ValueError("data_card must be an object with synthetic=true")
        if data_card.get("authorization") != "synthetic_fixture":
            raise ValueError("synthetic adapter requires authorization=synthetic_fixture")
        records = dataset.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError("records must be a non-empty array")

        targets: dict[str, dict[str, Any]] = {}
        provenance: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for index, record in enumerate(records):
            if not isinstance(record, Mapping):
                raise TypeError(f"records[{index}] must be an object")
            record_allowed = {
                "record_id",
                "indicator_id",
                "value",
                "unit",
                "reference_year",
                "status",
                "synthetic",
            }
            extra = sorted(set(record) - record_allowed)
            if extra:
                raise ValueError(
                    f"Unknown fields in records[{index}]: {', '.join(extra)}"
                )
            if record.get("synthetic") is not True:
                raise ValueError(f"records[{index}] must set synthetic=true")
            indicator = record.get("indicator_id")
            if indicator not in INDICATOR_CATALOG:
                raise ValueError(f"Unsupported indicator_id: {indicator}")
            if indicator in seen:
                raise ValueError(f"Duplicate indicator_id: {indicator}")
            seen.add(str(indicator))
            specification = INDICATOR_CATALOG[str(indicator)]
            if record.get("unit") != specification["unit"]:
                raise ValueError(
                    f"Unit mismatch for {indicator}: expected {specification['unit']}"
                )
            reference_year = record.get("reference_year")
            if isinstance(reference_year, bool) or not isinstance(reference_year, int):
                raise TypeError(f"reference_year must be an integer for {indicator}")
            if (
                self.expected_reference_year is not None
                and reference_year != self.expected_reference_year
            ):
                raise ValueError(
                    f"Reference year mismatch for {indicator}: "
                    f"expected {self.expected_reference_year}"
                )
            if record.get("status") != "synthetic_observation":
                raise ValueError(
                    f"Synthetic fixture status required for {indicator}"
                )
            outcome = str(specification["outcome"])
            tolerance = self.tolerances[str(indicator)]
            targets[outcome] = {
                "target": _number(record.get("value"), f"{indicator}.value"),
                "tolerance": tolerance["tolerance"],
                "mode": tolerance["mode"],
            }
            provenance[outcome] = {
                "record_id": record.get("record_id"),
                "indicator_id": indicator,
                "unit": record.get("unit"),
                "reference_year": reference_year,
                "status": record.get("status"),
            }

        missing = sorted(set(INDICATOR_CATALOG) - seen)
        if missing and self.require_complete:
            raise ValueError("Missing required indicators: " + ", ".join(missing))
        warnings = []
        if missing:
            warnings.append(
                {
                    "code": "INCOMPLETE_SYNTHETIC_TARGETS",
                    "severity": "warning",
                    "message": "Missing indicators: " + ", ".join(missing),
                }
            )
        return {
            "schema_version": "1.0.0",
            "adapter": {
                "name": self.descriptor.name,
                "version": self.descriptor.version,
                "domain": self.descriptor.domain,
                "accepts_real_data": self.descriptor.accepts_real_data,
            },
            "dataset_id": dataset_id,
            "input_digest": _digest(dataset),
            "data_card_digest": _digest(data_card),
            "calibration_targets": targets,
            "target_provenance": provenance,
            "warnings": warnings,
            "usage_level": "Demo",
            "synthetic": True,
        }
