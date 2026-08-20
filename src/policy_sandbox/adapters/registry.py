"""Strict registry and factory for aggregate calibration-data adapters."""

from collections.abc import Callable
from typing import Any, Mapping, TypeVar

from policy_sandbox.adapters.base import AggregateDataAdapter

AdapterType = TypeVar("AdapterType", bound=type[AggregateDataAdapter])

AGGREGATE_ADAPTER_REGISTRY: dict[str, type[AggregateDataAdapter]] = {}


def register_aggregate_adapter(name: str) -> Callable[[AdapterType], AdapterType]:
    """Register one aggregate adapter class under a unique public name."""

    if not name or name.startswith("_"):
        raise ValueError("Aggregate adapter registration name must be public and non-empty.")

    def decorator(cls: AdapterType) -> AdapterType:
        if name in AGGREGATE_ADAPTER_REGISTRY:
            raise ValueError(f"Aggregate data adapter '{name}' is already registered.")
        AGGREGATE_ADAPTER_REGISTRY[name] = cls
        return cls

    return decorator


def AggregateDataAdapterFactory(
    adapter_name: str,
    cfg: Mapping[str, Any],
) -> AggregateDataAdapter:
    """Create a configured aggregate adapter or fail with available names."""

    adapter_cls = AGGREGATE_ADAPTER_REGISTRY.get(adapter_name)
    if adapter_cls is None:
        available = ", ".join(sorted(AGGREGATE_ADAPTER_REGISTRY)) or "<none>"
        raise ValueError(
            f"Unknown aggregate data adapter '{adapter_name}'. Available: {available}"
        )
    return adapter_cls(cfg)


def available_aggregate_adapters() -> tuple[str, ...]:
    """Return registered aggregate adapter names in stable order."""

    return tuple(sorted(AGGREGATE_ADAPTER_REGISTRY))
