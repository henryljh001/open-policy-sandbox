"""Aggregate data adapter contracts, registry, factory, and discovery."""

from policy_sandbox.adapters.base import (
    AggregateDataAdapter,
    AggregateDataAdapterDescriptor,
)
from policy_sandbox.adapters.contracts import (
    canonical_digest,
    migrate_aggregate_dataset_v1_to_v2,
)
from policy_sandbox.adapters.quality import (
    AggregateDataQualityError,
    build_adapter_conformance_report,
    build_aggregate_data_quality_report,
    validate_aggregate_dataset_v2_semantics,
)
from policy_sandbox.adapters.registry import (
    AGGREGATE_ADAPTER_REGISTRY,
    AggregateDataAdapterFactory,
    available_aggregate_adapters,
    register_aggregate_adapter,
)

from policy_sandbox.adapters import implementations as _implementations  # noqa: E402,F401

__all__ = [
    "AGGREGATE_ADAPTER_REGISTRY",
    "AggregateDataAdapter",
    "AggregateDataAdapterDescriptor",
    "AggregateDataAdapterFactory",
    "AggregateDataQualityError",
    "available_aggregate_adapters",
    "build_adapter_conformance_report",
    "build_aggregate_data_quality_report",
    "canonical_digest",
    "migrate_aggregate_dataset_v1_to_v2",
    "register_aggregate_adapter",
    "validate_aggregate_dataset_v2_semantics",
]
