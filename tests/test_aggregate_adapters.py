"""Aggregate adapter registry and strict-validation tests."""

import copy
import json
import unittest
from pathlib import Path

from policy_sandbox.adapters import (
    AggregateDataAdapter,
    AggregateDataAdapterFactory,
    available_aggregate_adapters,
    register_aggregate_adapter,
)


class AggregateAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1]
        cls.dataset = json.loads(
            (
                root
                / "examples"
                / "new_urbanization"
                / "synthetic_aggregate_calibration.json"
            ).read_text(encoding="utf-8")
        )

    def adapter(self):  # type: ignore[no-untyped-def]
        return AggregateDataAdapterFactory(
            "new_urbanization_synthetic_aggregate_v1",
            {"expected_reference_year": 2030},
        )

    def test_builtin_adapter_is_auto_discovered(self) -> None:
        self.assertIn(
            "new_urbanization_synthetic_aggregate_v1",
            available_aggregate_adapters(),
        )

    def test_valid_fixture_adapts_reproducibly_with_provenance(self) -> None:
        first = self.adapter().adapt(self.dataset)
        second = self.adapter().adapt(self.dataset)
        self.assertEqual(first, second)
        self.assertEqual(len(first["calibration_targets"]), 8)
        self.assertEqual(
            first["target_provenance"]["final_total_population"]["record_id"],
            "SYN-2030-POP",
        )
        self.assertFalse(first["adapter"]["accepts_real_data"])

    def test_non_synthetic_dataset_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["synthetic"] = False
        with self.assertRaisesRegex(ValueError, "synthetic=true"):
            self.adapter().adapt(invalid)

    def test_unit_mismatch_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["records"][0]["unit"] = "thousand_persons"
        with self.assertRaisesRegex(ValueError, "Unit mismatch"):
            self.adapter().adapt(invalid)

    def test_duplicate_indicator_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.dataset)
        invalid["records"][1]["indicator_id"] = "total_population"
        invalid["records"][1]["unit"] = "person"
        with self.assertRaisesRegex(ValueError, "Duplicate indicator_id"):
            self.adapter().adapt(invalid)

    def test_incomplete_fixture_can_be_explicitly_allowed(self) -> None:
        partial = copy.deepcopy(self.dataset)
        partial["records"] = partial["records"][:2]
        adapter = AggregateDataAdapterFactory(
            "new_urbanization_synthetic_aggregate_v1",
            {"expected_reference_year": 2030, "require_complete": False},
        )
        result = adapter.adapt(partial)
        self.assertEqual(len(result["calibration_targets"]), 2)
        self.assertEqual(result["warnings"][0]["code"], "INCOMPLETE_SYNTHETIC_TARGETS")

    def test_unknown_adapter_fails_with_available_names(self) -> None:
        with self.assertRaisesRegex(ValueError, "Available"):
            AggregateDataAdapterFactory("missing", {})

    def test_duplicate_registration_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "already registered"):

            @register_aggregate_adapter("new_urbanization_synthetic_aggregate_v1")
            class DuplicateAdapter(AggregateDataAdapter):
                def adapt(self, dataset):  # type: ignore[no-untyped-def]
                    return dict(dataset)


if __name__ == "__main__":
    unittest.main()
