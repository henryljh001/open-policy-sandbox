"""Framework-neutral aggregate data-adapter contract."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AggregateDataAdapterDescriptor:
    """Public identity and compatibility envelope of an aggregate adapter."""

    name: str
    version: str
    domain: str
    accepted_schema_versions: tuple[str, ...]
    accepts_real_data: bool


class AggregateDataAdapter(ABC):
    """Convert a documented aggregate dataset to calibration targets."""

    descriptor: AggregateDataAdapterDescriptor

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.cfg = dict(cfg)

    @abstractmethod
    def adapt(self, dataset: Mapping[str, Any]) -> dict[str, Any]:
        """Validate one dataset and return targets plus provenance."""

        raise NotImplementedError
