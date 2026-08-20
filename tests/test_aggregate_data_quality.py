"""Semantic quality, provenance, authorization, and conformance tests."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from policy_sandbox.adapters import (
    AggregateDataAdapter,
    AggregateDataAdapterDescriptor,
    AggregateDataQualityError,
    build_adapter_conformance_report,
    build_aggregate_data_quality_report,
    validate_aggregate_dataset_v2_semantics,
)
from policy_sandbox.adapters.registry import AGGREGATE_ADAPTER_REGISTRY


class AggregateDataQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.dataset = json.loads(
            (
                cls.root
                / "examples"
                / "new_urbanization"
                / "synthetic_aggregate_calibration_v2.json"
            ).read_text(encoding="utf-8")
        )
        cls.report_schema = json.loads(
            (
                cls.root / "schemas" / "aggregate_data_quality_report.schema.json"
            ).read_text(encoding="utf-8")
        )
        cls.report_validator = Draft202012Validator(cls.report_schema)

    def report(self, dataset=None):  # type: ignore[no-untyped-def]
        return build_aggregate_data_quality_report(
            self.dataset if dataset is None else dataset,
            evaluation_date="2026-08-20",
        )

    @staticmethod
    def issue_codes(report: dict) -> set[str]:
        return {
            issue["code"]
            for check in report["checks"]
            for issue in check["issues"]
        }

    def make_real_dataset(self) -> dict:
        dataset = copy.deepcopy(self.dataset)
        dataset["synthetic"] = False
        dataset["publication_class"] = "private_restricted"
        card = dataset["data_card"]
        card["source_kind"] = "official_statistics"
        card["authorization"]["status"] = "authorized"
        card["authorization"]["public_outputs"] = "none"
        card["license"]["redistribution"] = "prohibited"
        card["geography"]["level"] = "county"
        card["synthetic"] = False
        manifest = dataset["source_manifest"]
        manifest["synthetic"] = False
        source = manifest["sources"][0]
        source["synthetic"] = False
        source["acquired_on"] = "2026-08-20"
        source["locator"] = {
            "kind": "https_url",
            "value": "https://example.gov.cn/aggregate-data.json",
        }
        ledger = dataset["transformation_ledger"]
        ledger["synthetic"] = False
        ledger["steps"][0]["synthetic"] = False
        for record in dataset["records"]:
            record.update(status="official_observation", synthetic=False)
        return dataset

    def test_synthetic_fixture_passes_and_report_matches_schema(self) -> None:
        report = self.report()
        self.report_validator.validate(report)
        self.assertEqual(report["summary"]["status"], "pass")
        self.assertEqual(report["summary"]["error_count"], 0)
        self.assertEqual(
            report["real_data_readiness"]["status"],
            "not_assessed_synthetic",
        )
        self.assertEqual(report["real_data_readiness"]["U6_status"], "not_passed")
        self.assertEqual(report["usage_level"], "Demo")

    def test_report_is_deterministic_and_validator_returns_it(self) -> None:
        first = self.report()
        second = self.report()
        self.assertEqual(first, second)
        self.assertEqual(
            first,
            validate_aggregate_dataset_v2_semantics(
                self.dataset,
                evaluation_date="2026-08-20",
            ),
        )

    def test_dataset_id_mismatch_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["source_manifest"]["dataset_id"] = "unrelated"
        invalid["transformation_ledger"]["dataset_id"] = "other"
        report = self.report(invalid)
        self.assertIn("DATASET_ID_MISMATCH", self.issue_codes(report))
        with self.assertRaises(AggregateDataQualityError) as captured:
            validate_aggregate_dataset_v2_semantics(
                invalid, evaluation_date="2026-08-20"
            )
        self.assertEqual(captured.exception.report["summary"]["status"], "fail")

    def test_dangling_record_provenance_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["records"][0]["source_id"] = "missing-source"
        invalid["records"][0]["transformation_step_ids"] = ["missing-step"]
        codes = self.issue_codes(self.report(invalid))
        self.assertIn("DANGLING_SOURCE_REFERENCE", codes)
        self.assertIn("DANGLING_TRANSFORMATION_REFERENCE", codes)

    def test_non_topological_step_input_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["transformation_ledger"]["steps"][0]["input_refs"] = ["future-step"]
        self.assertIn(
            "NON_TOPOLOGICAL_STEP_REFERENCE",
            self.issue_codes(self.report(invalid)),
        )

    def test_malformed_reference_items_report_errors_without_crashing(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["records"][0]["transformation_step_ids"] = [{"bad": "reference"}]
        invalid["transformation_ledger"]["steps"][0]["input_refs"] = [
            {"bad": "input"}
        ]
        invalid["transformation_ledger"]["steps"][0]["output_fields"] = "bad"
        codes = self.issue_codes(self.report(invalid))
        self.assertIn("INVALID_TRANSFORMATION_REFERENCE", codes)
        self.assertIn("INVALID_STEP_INPUT_REFERENCE", codes)
        self.assertIn("TRANSFORMATION_OUTPUT_MISMATCH", codes)

    def test_duplicate_ids_and_indicator_year_are_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        duplicate = copy.deepcopy(invalid["records"][0])
        invalid["records"].append(duplicate)
        codes = self.issue_codes(self.report(invalid))
        self.assertIn("DUPLICATE_IDENTIFIER", codes)
        self.assertIn("DUPLICATE_INDICATOR_YEAR", codes)

    def test_declared_coverage_must_match_records(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["data_card"]["coverage"]["indicator_ids"] = ["total_population"]
        invalid["data_card"]["coverage"]["reference_years"] = [2029]
        codes = self.issue_codes(self.report(invalid))
        self.assertIn("INDICATOR_COVERAGE_MISMATCH", codes)
        self.assertIn("REFERENCE_YEAR_COVERAGE_MISMATCH", codes)

    def test_non_finite_out_of_range_and_unit_values_are_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["records"][0]["value"] = float("nan")
        invalid["records"][1]["value"] = 101.0
        invalid["records"][2]["unit"] = "ratio"
        report = self.report(invalid)
        codes = self.issue_codes(report)
        self.report_validator.validate(report)
        self.assertIsNone(report["dataset"]["dataset_digest"])
        self.assertIn("NON_JSON_DATASET", codes)
        self.assertIn("NON_FINITE_VALUE", codes)
        self.assertIn("VALUE_ABOVE_MAXIMUM", codes)
        self.assertIn("UNIT_MISMATCH", codes)

    def test_real_blocked_indicator_and_expired_authorization_fail(self) -> None:
        invalid = self.make_real_dataset()
        invalid["data_card"]["authorization"]["expires_on"] = "2026-08-19"
        report = self.report(invalid)
        codes = self.issue_codes(report)
        self.assertIn("AUTHORIZATION_EXPIRED", codes)
        self.assertIn("REAL_INDICATOR_BLOCKED", codes)
        self.assertEqual(report["real_data_readiness"]["status"], "blocked")
        self.assertEqual(report["real_data_readiness"]["I5b_status"], "not_assessed")

    def test_public_real_output_rechecks_authorization_and_license(self) -> None:
        invalid = self.make_real_dataset()
        invalid["publication_class"] = "public_aggregate"
        codes = self.issue_codes(self.report(invalid))
        self.assertIn("PUBLIC_OUTPUT_NOT_AUTHORIZED", codes)
        self.assertIn("PUBLIC_REDISTRIBUTION_PROHIBITED", codes)

    def test_conditional_real_indicators_require_human_review(self) -> None:
        dataset = self.make_real_dataset()
        dataset["records"] = dataset["records"][:-1]
        dataset["data_card"]["coverage"]["indicator_ids"] = dataset["data_card"][
            "coverage"
        ]["indicator_ids"][:-1]
        report = self.report(dataset)
        self.assertEqual(report["summary"]["status"], "pass_with_warnings")
        self.assertEqual(
            report["real_data_readiness"]["status"],
            "requires_human_review",
        )
        self.assertIn("REAL_CALIBER_REVIEW_REQUIRED", self.issue_codes(report))
        self.assertEqual(report["real_data_readiness"]["U6_status"], "not_passed")

    def test_invalid_evaluation_date_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            build_aggregate_data_quality_report(
                self.dataset,
                evaluation_date="20-08-2026",
            )

    def test_builtin_adapter_descriptor_conforms(self) -> None:
        report = build_adapter_conformance_report()
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["adapter_count"], 1)
        self.assertEqual(report["real_adapter_count"], 0)
        self.assertEqual(report["usage_level"], "Demo")

    def test_descriptor_registry_name_mismatch_is_reported(self) -> None:
        class MismatchedAdapter(AggregateDataAdapter):
            descriptor = AggregateDataAdapterDescriptor(
                name="different-name",
                version="1.0.0",
                domain="new_urbanization",
                accepted_schema_versions=("2.0.0",),
                accepts_real_data=False,
            )

            def adapt(self, dataset):  # type: ignore[no-untyped-def]
                return dict(dataset)

        AGGREGATE_ADAPTER_REGISTRY["mismatched"] = MismatchedAdapter
        try:
            report = build_adapter_conformance_report()
        finally:
            AGGREGATE_ADAPTER_REGISTRY.pop("mismatched")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["issues"][0]["code"], "ADAPTER_NAME_MISMATCH")

    def test_non_class_registry_entry_is_reported_without_crashing(self) -> None:
        AGGREGATE_ADAPTER_REGISTRY["invalid-object"] = object()  # type: ignore[assignment]
        try:
            report = build_adapter_conformance_report()
        finally:
            AGGREGATE_ADAPTER_REGISTRY.pop("invalid-object")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["issues"][0]["adapter"], "invalid-object")
        self.assertEqual(report["issues"][0]["code"], "INVALID_ADAPTER_CLASS")


if __name__ == "__main__":
    unittest.main()
