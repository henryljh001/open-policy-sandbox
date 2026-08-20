"""U6/U7 pre-result registration, freeze, and one-time holdout tests."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from policy_sandbox.validation import (
    ValidationPreregistrationError,
    ValidationRegistrationChainError,
    build_validation_registration_chain_report,
    build_validation_preregistration_report,
    seal_validation_preregistration,
    validate_validation_registration_chain,
    validate_validation_preregistration_semantics,
)


MOMENTS = (
    (
        "total_population",
        "final_total_population",
        "person",
        "relative",
        0.02,
    ),
    (
        "urbanization_rate",
        "final_urbanization_rate",
        "percent",
        "absolute",
        1.0,
    ),
    (
        "employment_rate",
        "final_employment_rate",
        "percent",
        "absolute",
        1.0,
    ),
    (
        "debt_to_revenue",
        "final_debt_to_revenue",
        "percent",
        "absolute",
        5.0,
    ),
    (
        "education_capacity_per_1000",
        "final_education_capacity_per_1000",
        "capacity_per_1000_persons",
        "absolute",
        2.0,
    ),
    (
        "health_capacity_per_1000",
        "final_health_capacity_per_1000",
        "capacity_per_1000_persons",
        "absolute",
        0.5,
    ),
    (
        "housing_occupancy_rate",
        "final_housing_occupancy_rate",
        "percent",
        "absolute",
        1.0,
    ),
)


class ValidationPreregistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.u6_template = json.loads(
            (
                cls.root
                / "docs"
                / "domains"
                / "new_urbanization"
                / "U6_CALIBRATION_PREREGISTRATION_TEMPLATE.json"
            ).read_text(encoding="utf-8")
        )
        cls.u7_template = json.loads(
            (
                cls.root
                / "docs"
                / "domains"
                / "new_urbanization"
                / "U7_HOLDOUT_PREREGISTRATION_TEMPLATE.json"
            ).read_text(encoding="utf-8")
        )
        cls.template = cls.u6_template
        schema = json.loads(
            (
                cls.root / "schemas" / "validation_preregistration.schema.json"
            ).read_text(encoding="utf-8")
        )
        cls.schema_validator = Draft202012Validator(schema)

    @staticmethod
    def issue_codes(report: dict) -> set[str]:
        return {
            issue["code"]
            for check in report["checks"]
            for issue in check["issues"]
        }

    def make_preseal(self) -> dict:
        document = copy.deepcopy(self.template)
        document.update(
            registration_id="synthetic-u6-freeze",
            registration_version="1.0.0",
            registration_status="sealed_pre_results",
            registered_at="2026-08-20T18:00:00+08:00",
        )
        document["scope"] = {
            "geographic_level": "county",
            "calibration_window": {"start_year": 2020, "end_year": 2024},
            "holdout_kind": "historical_period",
            "indicator_ids": [item[0] for item in MOMENTS],
        }
        document["prerequisites"] = {
            "I5b_evidence_digest": "9" * 64,
            "U6_registration_digest": None,
            "U6_evidence_digest": None,
        }
        document["data_freeze"] = {
            "calibration_dataset_digest": "1" * 64,
            "holdout_dataset_digest": "2" * 64,
            "data_partition_digest": "3" * 64,
            "authorization_evidence_digest": "4" * 64,
            "quality_report_digest": "5" * 64,
        }
        document["model_freeze"] = {
            "repository_commit": "a" * 40,
            "software_version": "0.6.0",
            "engine_name": "new_urbanization_microsim",
            "engine_version": "0.1.0",
            "config_digest": "6" * 64,
            "parameter_bounds_digest": "7" * 64,
            "implementation_freeze_digest": "8" * 64,
            "calibrated_parameters_digest": None,
            "validated_model_freeze_digest": None,
        }
        document["u6_plan"] = {
            "acceptance_rule": "all_registered_moments_within_tolerance",
            "moments": [
                {
                    "indicator_id": indicator,
                    "model_outcome": outcome,
                    "unit": unit,
                    "mode": mode,
                    "tolerance": tolerance,
                }
                for indicator, outcome, unit, mode, tolerance in MOMENTS
            ],
            "parameter_bounds": [
                {"parameter_id": "migration_response", "minimum": 0.0, "maximum": 1.0}
            ],
            "sensitivity_checks": [
                {
                    "check_id": "migration-response-oat",
                    "method": "one_at_a_time",
                    "parameters": ["migration_response"],
                    "decision_rule": "registered moments retain their pass direction",
                }
            ],
            "failure_policy": "retain_all_attempts_and_report",
            "maximum_calibration_attempts": 20,
        }
        return document

    def make_u7_preseal(self) -> dict:
        document = copy.deepcopy(self.u7_template)
        u6_document = self.make_preseal()
        document.update(
            registration_id="synthetic-u7-freeze",
            registration_version="1.0.0",
            registration_status="sealed_pre_results",
            registered_at="2026-08-20T19:00:00+08:00",
        )
        document["scope"] = copy.deepcopy(u6_document["scope"])
        document["data_freeze"] = copy.deepcopy(u6_document["data_freeze"])
        document["prerequisites"] = {
            "I5b_evidence_digest": "9" * 64,
            "U6_registration_digest": "a" * 64,
            "U6_evidence_digest": "b" * 64,
        }
        document["model_freeze"] = copy.deepcopy(u6_document["model_freeze"])
        document["model_freeze"]["calibrated_parameters_digest"] = "c" * 64
        document["model_freeze"]["validated_model_freeze_digest"] = "d" * 64
        document["u7_plan"] = {
            "acceptance_rule": "all_primary_metrics_meet_thresholds",
            "primary_metrics": [
                {
                    "metric_id": "mean_absolute_scaled_error",
                    "direction": "maximum",
                    "threshold": 1.0,
                    "aggregation": "overall",
                },
                {
                    "metric_id": "directional_accuracy",
                    "direction": "minimum",
                    "threshold": 0.7,
                    "aggregation": "by_period",
                },
            ],
            "externality_boundary": "county archetypes represented by the frozen split",
            "independent_validator_role": "independent validation reviewer",
            "one_time_access": copy.deepcopy(
                self.u7_template["u7_plan"]["one_time_access"]
            ),
        }
        document["result_access"]["calibration_results_viewed"] = True
        return document

    def make_valid_chain(self) -> tuple[dict, dict]:
        u6_document = seal_validation_preregistration(self.make_preseal())
        u7_document = self.make_u7_preseal()
        u7_document["prerequisites"]["U6_registration_digest"] = u6_document[
            "registration_digest"
        ]
        return u6_document, seal_validation_preregistration(u7_document)

    def test_public_template_matches_schema_and_semantics(self) -> None:
        for template in (self.u6_template, self.u7_template):
            self.schema_validator.validate(template)
            report = validate_validation_preregistration_semantics(template)
            self.assertEqual(report["summary"]["status"], "pass")
            self.assertFalse(report["capability_effect"]["automatic_promotion"])
            self.assertEqual(report["capability_effect"]["U6"], "unchanged")
            self.assertEqual(report["capability_effect"]["U7"], "unchanged")
            self.assertEqual(report["capability_effect"]["usage_level"], "unchanged")

    def test_public_template_contains_no_freeze_or_result_evidence(self) -> None:
        for template in (self.u6_template, self.u7_template):
            self.assertIsNone(template["registration_digest"])
            self.assertTrue(all(value is None for value in template["data_freeze"].values()))
            self.assertTrue(all(value is None for value in template["model_freeze"].values()))
            self.assertTrue(all(value is None for value in template["prerequisites"].values()))
            self.assertEqual(template["u6_plan"]["moments"], [])
            self.assertEqual(template["u7_plan"]["primary_metrics"], [])
            self.assertFalse(template["contains_results"])

    def test_complete_synthetic_registration_seals_deterministically(self) -> None:
        first = seal_validation_preregistration(self.make_preseal())
        second = seal_validation_preregistration(self.make_preseal())
        self.assertEqual(first, second)
        self.schema_validator.validate(first)
        report = validate_validation_preregistration_semantics(first)
        self.assertEqual(report["summary"]["status"], "pass")
        self.assertRegex(first["registration_digest"], r"^[a-f0-9]{64}$")

    def test_u7_freeze_seals_after_u6_and_before_holdout(self) -> None:
        sealed = seal_validation_preregistration(self.make_u7_preseal())
        self.schema_validator.validate(sealed)
        report = validate_validation_preregistration_semantics(sealed)
        self.assertEqual(report["summary"]["status"], "pass")
        self.assertTrue(sealed["result_access"]["calibration_results_viewed"])
        self.assertFalse(sealed["result_access"]["holdout_results_viewed"])

    def test_content_change_after_sealing_breaks_digest(self) -> None:
        sealed = seal_validation_preregistration(self.make_preseal())
        sealed["u6_plan"]["moments"][0]["tolerance"] = 0.03
        report = build_validation_preregistration_report(sealed)
        self.assertIn("REGISTRATION_DIGEST_MISMATCH", self.issue_codes(report))

    def test_calibration_and_holdout_must_be_distinct(self) -> None:
        invalid = self.make_preseal()
        invalid["data_freeze"]["holdout_dataset_digest"] = invalid["data_freeze"][
            "calibration_dataset_digest"
        ]
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid)
        self.assertIn(
            "CALIBRATION_HOLDOUT_NOT_SEPARATED",
            self.issue_codes(captured.exception.report),
        )

    def test_blocked_indicator_cannot_enter_u6_scope(self) -> None:
        invalid = self.make_preseal()
        invalid["scope"]["indicator_ids"].append("used_construction_land")
        invalid["u6_plan"]["moments"].append(
            {
                "indicator_id": "used_construction_land",
                "model_outcome": "final_used_construction_land",
                "unit": "synthetic_area_unit",
                "mode": "absolute",
                "tolerance": 2.0,
            }
        )
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid)
        self.assertIn("BLOCKED_REAL_INDICATOR", self.issue_codes(captured.exception.report))

    def test_indicator_outcome_and_unit_binding_cannot_drift(self) -> None:
        invalid = self.make_preseal()
        invalid["u6_plan"]["moments"][0]["model_outcome"] = "other_population"
        invalid["u6_plan"]["moments"][0]["unit"] = "household"
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid)
        self.assertIn(
            "U6_MOMENT_BINDING_MISMATCH",
            self.issue_codes(captured.exception.report),
        )

    def test_result_access_or_consumed_holdout_fails_closed(self) -> None:
        sealed = seal_validation_preregistration(self.make_u7_preseal())
        sealed["result_access"]["holdout_results_viewed"] = True
        sealed["u7_plan"]["one_time_access"]["consumed"] = True
        report = build_validation_preregistration_report(sealed)
        codes = self.issue_codes(report)
        self.assertIn("RESULT_ACCESS_STAGE_MISMATCH", codes)
        self.assertIn("HOLDOUT_ACCESS_NOT_PRISTINE", codes)
        self.assertIn("REGISTRATION_DIGEST_MISMATCH", codes)

    def test_each_stage_requires_its_own_registered_plan(self) -> None:
        invalid_u6 = self.make_preseal()
        invalid_u6["u6_plan"]["sensitivity_checks"] = []
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid_u6)
        self.assertIn(
            "MISSING_SENSITIVITY_PLAN",
            self.issue_codes(captured.exception.report),
        )
        invalid_u7 = self.make_u7_preseal()
        invalid_u7["u7_plan"]["primary_metrics"] = []
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid_u7)
        self.assertIn(
            "INVALID_U7_PRIMARY_METRICS",
            self.issue_codes(captured.exception.report),

        )

    def test_u7_requires_u6_evidence_and_final_model_freeze(self) -> None:
        invalid = self.make_u7_preseal()
        invalid["prerequisites"]["U6_registration_digest"] = None
        invalid["model_freeze"]["calibrated_parameters_digest"] = None
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid)
        codes = self.issue_codes(captured.exception.report)
        self.assertIn("MISSING_U6_PREREQUISITE_REFERENCE", codes)
        self.assertIn("MISSING_FINAL_MODEL_FREEZE", codes)

    def test_inactive_stage_plan_must_remain_blank(self) -> None:
        invalid_u6 = self.make_preseal()
        invalid_u6["u7_plan"]["primary_metrics"] = [
            {
                "metric_id": "premature_metric",
                "direction": "maximum",
                "threshold": 1.0,
                "aggregation": "overall",
            }
        ]
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid_u6)
        self.assertIn("U7_PLAN_MUST_WAIT_FOR_U6", self.issue_codes(captured.exception.report))
        invalid_u7 = self.make_u7_preseal()
        invalid_u7["u6_plan"]["moments"] = copy.deepcopy(
            self.make_preseal()["u6_plan"]["moments"][:1]
        )
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid_u7)
        self.assertIn(
            "U7_MUST_REFERENCE_FROZEN_U6", self.issue_codes(captured.exception.report)
        )

    def test_valid_u6_u7_chain_passes_without_promotion(self) -> None:
        u6_document, u7_document = self.make_valid_chain()
        report = validate_validation_registration_chain(u6_document, u7_document)
        self.assertEqual(report["summary"]["status"], "pass")
        self.assertEqual(report["summary"]["check_count"], 5)
        self.assertFalse(report["capability_effect"]["automatic_promotion"])
        self.assertEqual(report["capability_effect"]["U7"], "unchanged")

    def test_chain_requires_exact_u6_digest_reference(self) -> None:
        u6_document, u7_document = self.make_valid_chain()
        u7_document["prerequisites"]["U6_registration_digest"] = "f" * 64
        report = build_validation_registration_chain_report(
            u6_document, u7_document
        )
        self.assertIn(
            "U6_REGISTRATION_REFERENCE_MISMATCH", self.issue_codes(report)
        )
        self.assertIn("U7_REGISTRATION_INVALID", self.issue_codes(report))

    def test_chain_rejects_scope_data_and_implementation_drift(self) -> None:
        u6_document = seal_validation_preregistration(self.make_preseal())
        u7_preseal = self.make_u7_preseal()
        u7_preseal["prerequisites"]["U6_registration_digest"] = u6_document[
            "registration_digest"
        ]
        u7_preseal["scope"]["geographic_level"] = "city"
        u7_preseal["data_freeze"]["quality_report_digest"] = "e" * 64
        u7_preseal["model_freeze"]["config_digest"] = "f" * 64
        u7_document = seal_validation_preregistration(u7_preseal)
        with self.assertRaises(ValidationRegistrationChainError) as captured:
            validate_validation_registration_chain(u6_document, u7_document)
        codes = self.issue_codes(captured.exception.report)
        self.assertIn("SCOPE_DRIFT", codes)
        self.assertIn("DATA_FREEZE_DRIFT", codes)
        self.assertIn("IMPLEMENTATION_FREEZE_DRIFT", codes)

    def test_chain_rejects_i5b_drift_and_invalid_time_order(self) -> None:
        u6_document = seal_validation_preregistration(self.make_preseal())
        u7_preseal = self.make_u7_preseal()
        u7_preseal["registered_at"] = "2026-08-20T17:00:00+08:00"
        u7_preseal["prerequisites"]["U6_registration_digest"] = u6_document[
            "registration_digest"
        ]
        u7_preseal["prerequisites"]["I5b_evidence_digest"] = "e" * 64
        u7_document = seal_validation_preregistration(u7_preseal)
        report = build_validation_registration_chain_report(
            u6_document, u7_document
        )
        codes = self.issue_codes(report)
        self.assertIn("I5B_REFERENCE_DRIFT", codes)
        self.assertIn("INVALID_REGISTRATION_TIME_ORDER", codes)
    def test_final_model_and_u6_evidence_digests_must_be_distinct(self) -> None:
        invalid_u7 = self.make_u7_preseal()
        invalid_u7["model_freeze"]["validated_model_freeze_digest"] = invalid_u7[
            "model_freeze"
        ]["calibrated_parameters_digest"]
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid_u7)
        self.assertIn(
            "FINAL_MODEL_DIGEST_COLLISION", self.issue_codes(captured.exception.report)
        )

        u6_document, u7_document = self.make_valid_chain()
        u7_document["prerequisites"]["U6_evidence_digest"] = u6_document[
            "registration_digest"
        ]
        report = build_validation_registration_chain_report(
            u6_document, u7_document
        )
        self.assertIn(
            "U6_EVIDENCE_REFERENCE_COLLISION", self.issue_codes(report)
        )

    def test_direct_semantic_report_fails_closed_on_unhashable_ids(self) -> None:
        invalid = self.make_preseal()
        invalid["scope"]["indicator_ids"] = [{"unexpected": "object"}]
        invalid["u6_plan"]["moments"][0]["indicator_id"] = ["unexpected"]
        invalid["u6_plan"]["parameter_bounds"][0]["parameter_id"] = {
            "unexpected": "object"
        }
        invalid["u6_plan"]["sensitivity_checks"][0]["check_id"] = ["unexpected"]
        report = build_validation_preregistration_report(invalid)
        codes = self.issue_codes(report)
        self.assertIn("INVALID_INDICATOR_SCOPE", codes)
        self.assertIn("INVALID_U6_MOMENTS", codes)
        self.assertIn("INVALID_PARAMETER_BOUNDS", codes)
        self.assertIn("MISSING_SENSITIVITY_PLAN", codes)

    def test_timestamp_and_tolerance_are_explicit(self) -> None:
        invalid = self.make_preseal()
        invalid["registered_at"] = "2026-08-20T18:00:00"
        invalid["u6_plan"]["moments"][0]["tolerance"] = 0.0
        with self.assertRaises(ValidationPreregistrationError) as captured:
            seal_validation_preregistration(invalid)
        codes = self.issue_codes(captured.exception.report)
        self.assertIn("INVALID_REGISTRATION_TIMESTAMP", codes)
        self.assertIn("INVALID_PREREGISTERED_TOLERANCE", codes)

    def test_seal_rejects_template_and_existing_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "sealed_pre_results"):
            seal_validation_preregistration(self.template)
        sealed = seal_validation_preregistration(self.make_preseal())
        with self.assertRaisesRegex(ValueError, "must be null"):
            seal_validation_preregistration(sealed)

    def test_non_finite_values_cannot_be_hashed(self) -> None:
        invalid = self.make_preseal()
        invalid["u6_plan"]["moments"][0]["tolerance"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Out of range float values"):
            seal_validation_preregistration(invalid)


if __name__ == "__main__":
    unittest.main()
