"""Abstract plugin contracts."""

from abc import ABC, abstractmethod
from typing import Any, Mapping

from policy_sandbox.domain.models import (
    DomainDescriptor,
    EngineDescriptor,
    InterventionDescriptor,
    PolicyEffect,
    PressureDescriptor,
    PressureEffect,
    SimulationResult,
)


class SimulationEngine(ABC):
    """Config-driven interface implemented by every simulation engine."""

    descriptor: EngineDescriptor

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.cfg = dict(cfg)

    @abstractmethod
    def run(self, scenario: Mapping[str, Any]) -> SimulationResult:
        """Run a scenario and return a domain result."""

        raise NotImplementedError


class DomainPlugin(ABC):
    """Config-driven declaration of a policy domain and its constraints."""

    descriptor: DomainDescriptor

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.cfg = dict(cfg)

    @abstractmethod
    def policy_dimensions(self) -> tuple[str, ...]:
        """Return stable dimensions exposed to scenario builders."""

        raise NotImplementedError

    @abstractmethod
    def validate_config(self) -> tuple[str, ...]:
        """Return domain configuration issues without reading private data."""

        raise NotImplementedError


class PolicyIntervention(ABC):
    """Config-driven policy lever that compiles to explicit synthetic effects."""

    descriptor: InterventionDescriptor

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.cfg = dict(cfg)

    @abstractmethod
    def compile(self) -> PolicyEffect:
        """Validate configuration and return an auditable synthetic effect."""

        raise NotImplementedError


class PressureScenario(ABC):
    """Config-driven exogenous pressure compiled from explicit assumptions."""

    descriptor: PressureDescriptor

    def __init__(self, cfg: Mapping[str, Any]) -> None:
        self.cfg = dict(cfg)

    @abstractmethod
    def compile(self) -> PressureEffect:
        """Validate configuration and return an auditable pressure effect."""

        raise NotImplementedError
