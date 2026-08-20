"""Aggregate data adapter contracts, registry, factory, and discovery."""

from policy_sandbox.adapters.base import (
    AggregateDataAdapter,
    AggregateDataAdapterDescriptor,
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
    "available_aggregate_adapters",
    "register_aggregate_adapter",
]
