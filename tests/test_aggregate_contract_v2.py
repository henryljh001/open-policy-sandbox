"""Version-two aggregate contract and deterministic migration tests."""

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from policy_sandbox.adapters import (
    canonical_digest,
    migrate_aggregate_dataset_v1_to_v2,
)


class AggregateContractV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.v1 = json.loads(
            (
                cls.root
                / "examples"
                / "new_urbanization"
                / "synthetic_aggregate_calibration.json"
            ).read_text(encoding="utf-8")
        )
        cls.v2_example = json.loads(
            (
                cls.root
                / "examples"
                / "new_urbanization"
                / "synthetic_aggregate_calibration_v2.json"
            ).read_text(encoding="utf-8")
        )
        cls.schemas = {
            name: json.loads((cls.root / "schemas" / name).read_text(encoding="utf-8"))
            for name in (
                "aggregate_calibration_dataset.v2.schema.json",
                "source_manifest.schema.json",
                "transformation_ledger.schema.json",
            )
        }
        cls.registry = Registry().with_resources(
            (
                schema["$id"],
                Resource.from_contents(schema),
            )
            for schema in cls.schemas.values()
        )

    def validate(self, name: str, instance: dict) -> None:
        Draft202012Validator(
            self.schemas[name],
            registry=self.registry,
        ).validate(instance)

    def make_real_dataset(self) -> dict:
        dataset = copy.deepcopy(self.v2_example)
        dataset["synthetic"] = False
        dataset["publication_class"] = "public_aggregate"
        card = dataset["data_card"]
        card["source_kind"] = "official_statistics"
        card["authorization"]["status"] = "authorized"
        card["authorization"]["public_outputs"] = "aggregate_only"
        card["license"]["redistribution"] = "aggregate_only"
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
        dataset["transformation_ledger"]["synthetic"] = False
        dataset["transformation_ledger"]["steps"][0]["synthetic"] = False
        for record in dataset["records"]:
            record.update(status="official_observation", synthetic=False)
        return dataset

    def test_migration_is_deterministic_and_preserves_values(self) -> None:
        original = copy.deepcopy(self.v1)
        first = migrate_aggregate_dataset_v1_to_v2(self.v1)
        second = migrate_aggregate_dataset_v1_to_v2(self.v1)
        self.assertEqual(first, second)
        self.assertEqual(self.v1, original)
        self.assertEqual(
            [record["value"] for record in first["records"]],
            [record["value"] for record in self.v1["records"]],
        )
        self.assertEqual(
            first["source_manifest"]["sources"][0]["content_sha256"],
            canonical_digest(self.v1),
        )

    def test_migrated_dataset_and_subcontracts_validate(self) -> None:
        migrated = migrate_aggregate_dataset_v1_to_v2(self.v1)
        self.validate("aggregate_calibration_dataset.v2.schema.json", migrated)
        self.validate("source_manifest.schema.json", migrated["source_manifest"])
        self.validate(
            "transformation_ledger.schema.json",
            migrated["transformation_ledger"],
        )

    def test_static_v2_example_is_exact_migration_output(self) -> None:
        migrated = migrate_aggregate_dataset_v1_to_v2(self.v1)
        self.assertEqual(self.v2_example, migrated)
        self.validate("aggregate_calibration_dataset.v2.schema.json", self.v2_example)

    def test_migration_never_infers_real_authorization(self) -> None:
        migrated = migrate_aggregate_dataset_v1_to_v2(self.v1)
        self.assertTrue(migrated["synthetic"])
        self.assertEqual(migrated["publication_class"], "public_synthetic")
        self.assertEqual(
            migrated["data_card"]["authorization"]["status"],
            "synthetic_fixture",
        )
        self.assertEqual(
            migrated["data_card"]["authorization"]["public_outputs"],
            "synthetic_only",
        )

    def test_non_synthetic_v1_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "synthetic=true"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_unknown_version_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["schema_version"] = "9.0.0"
        with self.assertRaisesRegex(ValueError, "Only aggregate dataset"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_year_conflict_is_rejected_instead_of_repaired(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["records"][0]["reference_year"] = 2029
        with self.assertRaisesRegex(ValueError, "reference_year conflicts"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_out_of_range_year_is_rejected_before_migration(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["data_card"]["coverage"]["reference_year"] = 2101
        for record in invalid["records"]:
            record["reference_year"] = 2101
        with self.assertRaisesRegex(ValueError, "between 2000 and 2100"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_record_order_conflict_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["records"][0], invalid["records"][1] = (
            invalid["records"][1],
            invalid["records"][0],
        )
        with self.assertRaisesRegex(ValueError, "record indicator order"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_non_finite_value_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["records"][0]["value"] = float("nan")
        with self.assertRaisesRegex(ValueError, "must be finite"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_duplicate_record_id_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["records"][1]["record_id"] = invalid["records"][0]["record_id"]
        with self.assertRaisesRegex(ValueError, "Duplicate record_id"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_unit_mismatch_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.v1)
        invalid["records"][0]["unit"] = "thousand_persons"
        with self.assertRaisesRegex(ValueError, "Unit mismatch"):
            migrate_aggregate_dataset_v1_to_v2(invalid)

    def test_real_dataset_cannot_keep_synthetic_publication_fields(self) -> None:
        invalid = migrate_aggregate_dataset_v1_to_v2(self.v1)
        invalid["synthetic"] = False
        invalid["data_card"]["synthetic"] = False
        invalid["source_manifest"]["synthetic"] = False
        invalid["transformation_ledger"]["synthetic"] = False
        for record in invalid["records"]:
            record["synthetic"] = False
        with self.assertRaises(ValidationError):
            self.validate("aggregate_calibration_dataset.v2.schema.json", invalid)

    def test_authorized_public_aggregate_combination_validates(self) -> None:
        dataset = self.make_real_dataset()
        self.validate("aggregate_calibration_dataset.v2.schema.json", dataset)

    def test_public_aggregate_requires_authorized_public_outputs(self) -> None:
        invalid = self.make_real_dataset()
        invalid["data_card"]["authorization"]["public_outputs"] = "none"
        with self.assertRaises(ValidationError):
            self.validate("aggregate_calibration_dataset.v2.schema.json", invalid)

    def test_public_aggregate_requires_redistribution_permission(self) -> None:
        invalid = self.make_real_dataset()
        invalid["data_card"]["license"]["redistribution"] = "prohibited"
        with self.assertRaises(ValidationError):
            self.validate("aggregate_calibration_dataset.v2.schema.json", invalid)

    def test_private_restricted_may_prohibit_public_outputs(self) -> None:
        dataset = self.make_real_dataset()
        dataset["publication_class"] = "private_restricted"
        dataset["data_card"]["authorization"]["public_outputs"] = "none"
        dataset["data_card"]["license"]["redistribution"] = "prohibited"
        self.validate("aggregate_calibration_dataset.v2.schema.json", dataset)

    def test_source_manifest_rejects_local_path_locator(self) -> None:
        manifest = copy.deepcopy(self.v2_example["source_manifest"])
        manifest["synthetic"] = False
        source = manifest["sources"][0]
        source["synthetic"] = False
        source["acquired_on"] = "2026-08-20"
        windows_separator = chr(92)
        local_path = "C:" + windows_separator + "private" + windows_separator + "source.xlsx"
        source["locator"] = {
            "kind": "https_url",
            "value": local_path,
        }
        with self.assertRaises(ValidationError):
            self.validate("source_manifest.schema.json", manifest)


if __name__ == "__main__":
    unittest.main()
